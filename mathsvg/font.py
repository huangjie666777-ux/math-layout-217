"""Font access layer: real glyph outlines, advances and MATH table metrics."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from .errors import FormulaError


@dataclass(frozen=True)
class AssemblyPart:
    glyph: str
    full_advance: int
    start_connector: int
    end_connector: int
    is_extender: bool


@dataclass(frozen=True)
class Delimiter:
    """Stretchy delimiter: one variant glyph or assembled MATH parts.

    parts is a tuple of (glyph_name, y_offset) in font units, bottom first;
    height and width are in font units.
    """

    parts: tuple
    height: int
    width: int


class MathFont:
    def __init__(self, path: str):
        self.font = TTFont(path)
        self.upem = self.font["head"].unitsPerEm
        self.glyph_set = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        math = self.font["MATH"].table
        self.constants = {}
        for name in dir(math.MathConstants):
            if name.startswith("_"):
                continue
            value = getattr(math.MathConstants, name)
            if hasattr(value, "Value"):
                self.constants[name] = value.Value
            elif isinstance(value, (int, float)):
                self.constants[name] = value
        self._build_variants(math)
        self._build_italics(math)

    def _build_variants(self, math):
        self.variants = {}
        self.assemblies = {}
        variants = math.MathVariants
        coverage = variants.VertGlyphCoverage.glyphs
        for glyph, construction in zip(coverage, variants.VertGlyphConstruction):
            records = [(r.VariantGlyph, r.AdvanceMeasurement)
                       for r in construction.MathGlyphVariantRecord]
            if records:
                self.variants[glyph] = records
            assembly = construction.GlyphAssembly
            if assembly is not None and assembly.PartRecords:
                self.assemblies[glyph] = tuple(
                    AssemblyPart(p.glyph, p.FullAdvance, p.StartConnectorLength,
                                 p.EndConnectorLength, bool(p.PartFlags & 1))
                    for p in assembly.PartRecords)

    def _build_italics(self, math):
        self.italics = {}
        info = math.MathGlyphInfo
        if info is None or info.MathItalicsCorrectionInfo is None:
            return
        ital = info.MathItalicsCorrectionInfo
        for glyph, record in zip(ital.Coverage.glyphs, ital.ItalicsCorrection):
            if record is not None:
                self.italics[glyph] = record.Value

    def constant(self, name: str) -> int:
        if name not in self.constants:
            raise FormulaError("font misses MATH constant " + name)
        return self.constants[name]

    def glyph_for_char(self, char: str) -> str:
        glyph = self.cmap.get(ord(char))
        if glyph is None or glyph not in self.glyph_set:
            raise FormulaError("character not covered by font: %r" % char)
        return glyph

    def advance(self, glyph: str) -> int:
        return int(round(self.glyph_set[glyph].width))

    def italic_correction(self, glyph: str) -> int:
        return self.italics.get(glyph, 0)

    @lru_cache(maxsize=None)
    def path_data(self, glyph: str) -> str:
        pen = SVGPathPen(self.glyph_set)
        self.glyph_set[glyph].draw(pen)
        return pen.getCommands()

    @lru_cache(maxsize=None)
    def ink_bounds(self, glyph: str):
        pen = BoundsPen(self.glyph_set)
        self.glyph_set[glyph].draw(pen)
        if pen.bounds is None:
            return (0, 0, 0, 0)
        return pen.bounds

    def delimiter(self, glyph: str, target: int) -> Delimiter:
        """Smallest variant covering target font units, else assembled from
        MATH parts; outlines are never vertically stretched."""
        for variant, advance in self.variants.get(glyph, []):
            if advance >= target:
                return Delimiter(parts=((variant, 0),), height=advance,
                                 width=self.advance(variant))
        if glyph in self.assemblies:
            return self._assemble(glyph, target)
        records = self.variants.get(glyph)
        if records:
            variant, advance = records[-1]
        else:
            variant, advance = glyph, self.advance(glyph)
        return Delimiter(parts=((variant, 0),), height=advance,
                         width=self.advance(variant))

    def _assemble(self, glyph: str, target: int) -> Delimiter:
        parts = list(self.assemblies[glyph])
        extenders = [p for p in parts if p.is_extender]
        if not extenders:
            height = sum(p.full_advance for p in parts)
            return Delimiter(parts=tuple((p.glyph, 0) for p in parts),
                             height=height,
                             width=max(self.advance(p.glyph) for p in parts))
        sequence = []
        ext_count = 0
        for part in parts:
            if part.is_extender:
                sequence.append((ext_count, part))
                ext_count += 1
            else:
                sequence.append((None, part))

        def total_height(seq):
            total = 0
            prev = None
            for _, part in seq:
                overlap = 0
                if prev is not None:
                    overlap = min(prev.end_connector, part.start_connector)
                total += part.full_advance - overlap
                prev = part
            return total

        # Repeat extenders round-robin until the assembly reaches the target.
        first_ext = next(i for i, (idx, _) in enumerate(sequence)
                         if idx is not None)
        guard = 0
        while total_height(sequence) < target and guard < 512:
            sequence.insert(first_ext,
                            (ext_count, extenders[ext_count % len(extenders)]))
            ext_count += 1
            guard += 1

        placed = []
        cursor = 0
        prev = None
        for _, part in sequence:
            overlap = 0
            if prev is not None:
                overlap = min(prev.end_connector, part.start_connector)
            placed.append((part.glyph, cursor))
            cursor += part.full_advance - overlap
            prev = part
        width = max(self.advance(g) for g, _ in placed)
        return Delimiter(parts=tuple(placed), height=cursor, width=width)

