"""Recursive layout: turns a validated node tree into positioned boxes.

All dimensions are in output units (the requested font size equals the
font units-per-em at script level 0). y grows upward from the baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import FormulaError
from .font import MathFont
from .model import Node

MAX_ITEMS = 20000


@dataclass
class Box:
    width: float
    height: float  # above baseline
    depth: float   # below baseline
    items: list = field(default_factory=list)
    italic: float = 0.0  # italic correction of the last glyph

    def shifted(self, dx: float, dy: float) -> "Box":
        return Box(self.width, self.height, self.depth,
                   [shift_item(it, dx, dy) for it in self.items], self.italic)


def shift_item(item, dx, dy):
    kind = item[0]
    if kind == "glyph":
        _, name, x, y, scale = item
        return ("glyph", name, x + dx, y + dy, scale)
    _, x, y, w, h = item
    return ("rect", x + dx, y + dy, w, h)


class Layouter:
    def __init__(self, font: MathFont, size: float):
        self.font = font
        self.size = size
        self.item_count = 0

    def scale(self, level: int) -> float:
        s = self.size / self.font.upem
        for i in range(1, level + 1):
            pct = (self.font.constant("ScriptPercentScaleDown") if i == 1
                   else self.font.constant("ScriptScriptPercentScaleDown"))
            s *= pct / 100.0
        return s

    def const(self, name: str, level: int) -> float:
        return self.font.constant(name) * self.scale(level)

    def layout(self, node: Node, level: int = 0) -> Box:
        handler = getattr(self, "_layout_" + node.type, None)
        if handler is None:
            raise FormulaError("unknown node type: " + node.type)
        box = handler(node, level)
        self.item_count += len(box.items)
        if self.item_count > MAX_ITEMS:
            raise FormulaError("formula produces too much output")
        return box

    # -- leaf / row -----------------------------------------------------

    def _layout_text(self, node: Node, level: int) -> Box:
        s = self.scale(level)
        x = 0.0
        items = []
        top = 0.0
        bottom = 0.0
        last_italic = 0.0
        for char in node.text:
            glyph = self.font.glyph_for_char(char)
            items.append(("glyph", glyph, x, 0.0, s))
            x0, y0, x1, y1 = self.font.ink_bounds(glyph)
            top = max(top, y1 * s)
            bottom = min(bottom, y0 * s)
            x += self.font.advance(glyph) * s
            last_italic = self.font.italic_correction(glyph) * s
        return Box(x, top, -bottom, items, last_italic)

    def _layout_row(self, node: Node, level: int) -> Box:
        x = 0.0
        items = []
        height = 0.0
        depth = 0.0
        italic = 0.0
        for child in node.children:
            box = self.layout(child, level)
            items.extend(box.shifted(x, 0.0).items)
            height = max(height, box.height)
            depth = max(depth, box.depth)
            x += box.width
            italic = box.italic
        return Box(x, height, depth, items, italic)

    # -- fraction --------------------------------------------------------

    def _layout_frac(self, node: Node, level: int) -> Box:
        num = self.layout(node.children[0], level)
        den = self.layout(node.children[1], level)
        axis = self.const("AxisHeight", level)
        rule = self.const("FractionRuleThickness", level)
        num_shift = self.const("FractionNumeratorShiftUp", level)
        den_shift = self.const("FractionDenominatorShiftDown", level)
        # Keep the required clearance between numerator/denominator and rule.
        num_gap = num_shift - num.depth - (axis + rule / 2)
        min_num_gap = self.const("FractionNumeratorGapMin", level)
        if num_gap < min_num_gap:
            num_shift += min_num_gap - num_gap
        den_gap = (axis - rule / 2) - (den_shift - den.height)
        min_den_gap = self.const("FractionDenominatorGapMin", level)
        if den_gap < min_den_gap:
            den_shift += min_den_gap - den_gap
        width = max(num.width, den.width) + 2 * rule
        items = [("rect", 0.0, axis - rule / 2, width, rule)]
        items.extend(num.shifted((width - num.width) / 2, num_shift).items)
        items.extend(den.shifted((width - den.width) / 2, -den_shift).items)
        return Box(width, num_shift + num.height, den_shift + den.depth, items)

    # -- scripts ---------------------------------------------------------

    def _layout_script(self, node: Node, level: int) -> Box:
        base = self.layout(node.children[0], level)
        sup = self.layout(node.sup, level + 1) if node.sup else None
        sub = self.layout(node.sub, level + 1) if node.sub else None
        # Script boxes are laid out at a scaled-down size; rescale items.
        sup_shift = sub_shift = 0.0
        if sup is not None:
            sup_shift = max(self.const("SuperscriptShiftUp", level),
                            self.const("SuperscriptBottomMin", level) + sup.depth)
        if sub is not None:
            sub_shift = max(self.const("SubscriptShiftDown", level),
                            sub.height - self.const("SubscriptTopMax", level))
        if sup is not None and sub is not None:
            gap = (sup_shift - sup.depth) - (sub.height - sub_shift)
            min_gap = self.const("SubSuperscriptGapMin", level)
            if gap < min_gap:
                extra = (min_gap - gap) / 2
                sup_shift += extra
                sub_shift += extra
        italic = base.italic if sup is not None else 0.0
        x = base.width
        items = list(base.items)
        tail = 0.0
        if sup is not None:
            items.extend(sup.shifted(x + italic, sup_shift).items)
            tail = max(tail, italic + sup.width)
        if sub is not None:
            items.extend(sub.shifted(x, -sub_shift).items)
            tail = max(tail, sub.width)
        tail += self.const("SpaceAfterScript", level)
        height = base.height
        depth = base.depth
        if sup is not None:
            height = max(height, sup_shift + sup.height)
        if sub is not None:
            depth = max(depth, sub_shift + sub.depth)
        return Box(base.width + tail, height, depth, items)

    # -- radical ---------------------------------------------------------

    def _layout_sqrt(self, node: Node, level: int) -> Box:
        rad = self.layout(node.children[0], level)
        s = self.scale(level)
        gap = self.const("RadicalVerticalGap", level)
        rule = self.const("RadicalRuleThickness", level)
        extra = self.const("RadicalExtraAscender", level)
        target = (rad.height + rad.depth + gap + rule) / s
        glyph = self.font.glyph_for_char("\u221a")
        delim = self.font.delimiter(glyph, target)
        sign_w = delim.width * s
        pad = rule  # small kern between the sign and the radicand
        # Bottoms of sign and radicand align; sign rises to cover the rule.
        sign_height = delim.height * s
        sign_depth = max(rad.depth, sign_height - (rad.height + gap + rule))
        items = []
        for part_glyph, y_off in delim.parts:
            items.append(("glyph", part_glyph, 0.0, -sign_depth + y_off * s, s))
        x = sign_w + pad
        items.extend(rad.shifted(x, 0.0).items)
        rule_y = rad.height + gap
        total_w = x + rad.width + pad
        items.append(("rect", sign_w, rule_y, total_w - sign_w, rule))
        height = max(rule_y + rule + extra, -sign_depth + sign_height)
        return Box(total_w, height, sign_depth, items)

    # -- parentheses -----------------------------------------------------

    def _layout_parens(self, node: Node, level: int) -> Box:
        child = self.layout(node.children[0], level)
        s = self.scale(level)
        axis = self.const("AxisHeight", level)
        half = max(child.height - axis, child.depth + axis)
        target = 2 * half / s
        left = self.font.delimiter(self.font.glyph_for_char("("), target)
        right = self.font.delimiter(self.font.glyph_for_char(")"), target)
        items = []
        x = 0.0
        for delim in (left, right):
            h = delim.height * s
            base_y = axis - h / 2  # baseline offset of the delimiter bottom
            for part_glyph, y_off in delim.parts:
                items.append(("glyph", part_glyph, x, base_y + y_off * s, s))
            x += delim.width * s
            if delim is left:
                items.extend(child.shifted(x, 0.0).items)
                x += child.width
        delim_h = max(left.height, right.height) * s
        height = max(child.height, axis + delim_h / 2)
        depth = max(child.depth, delim_h / 2 - axis)
        return Box(x, height, depth, items)


def layout_tree(font: MathFont, node: Node, size: float) -> Box:
    return Layouter(font, size).layout(node)

