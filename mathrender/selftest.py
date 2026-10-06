"""Self-test: layout correctness, validation rejections, determinism."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .font import MathFont
from .layout import Layout
from .nodes import ValidationError, validate_font_size, validate_tree
from .svg import render_svg

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "STIXTwoMath-Regular.otf"
font = MathFont(str(FONT_PATH))
SIZE = 48.0


def render(tree, size=SIZE):
    node = validate_tree(tree, lambda ch: font.glyph_for(ch) is not None)
    box = Layout(font, size).layout(node)
    return render_svg(box, font), box


def expect_error(tree, size=SIZE):
    try:
        if not (isinstance(size, (int, float)) and size > 0):
            validate_font_size(size)
        validate_tree(tree, lambda ch: font.glyph_for(ch) is not None)
    except ValidationError:
        return
    raise AssertionError(f"expected ValidationError for {tree!r}")


def main():
    # text
    (svg, w, h, b), box = render({"type": "text", "value": "xy+1"})
    assert w > 0 and h > 0 and b > 0 and "<path" in svg

    # row aligns on baseline
    (svg, w, h, b), _ = render({"type": "row", "children": [
        {"type": "text", "value": "a"}, {"type": "text", "value": "g"}]})
    assert h > 0 and b > 0

    # fraction
    frac = {"type": "frac", "num": {"type": "text", "value": "1"},
            "den": {"type": "text", "value": "x+2"}}
    (svg, w, h, b), _ = render(frac)
    assert "<rect" in svg and h > SIZE

    # scripts: sup only, sub only, both
    for extra in ({"sup": {"type": "text", "value": "2"}},
                  {"sub": {"type": "text", "value": "i"}},
                  {"sup": {"type": "text", "value": "2"},
                   "sub": {"type": "text", "value": "i"}}):
        node = {"type": "scripts", "base": {"type": "text", "value": "x"}, **extra}
        (svg, w, h, b), _ = render(node)
        assert w > 0

    # sqrt with nested frac; parens around tall content stretch
    nested = {"type": "paren", "child": {"type": "sqrt", "radicand": frac}}
    (svg, w, h, b), _ = render(nested)
    assert h > SIZE * 1.5

    # very tall content triggers assembly (many extender parts)
    tall = frac
    for _ in range(6):
        tall = {"type": "frac", "num": tall, "den": tall}
    (svg, w, h, b), _ = render({"type": "paren", "child": tall})
    assert svg.count("<path") > 10

    # determinism
    s1, _ = render(nested)
    s2, _ = render(nested)
    assert s1 == s2

    # input tree not mutated
    tree = {"type": "frac", "num": {"type": "text", "value": "a"},
            "den": {"type": "text", "value": "b"}}
    snapshot = copy.deepcopy(tree)
    render(tree)
    assert tree == snapshot

    # rejections
    expect_error({"type": "nope"})
    expect_error({"type": "text", "value": ""})
    expect_error({"type": "text", "value": "\u4e2d"})  # CJK not in font
    expect_error({"type": "frac", "num": {"type": "text", "value": "a"}})
    expect_error({"type": "scripts", "base": {"type": "text", "value": "x"}})
    expect_error({"type": "row", "children": []})
    deep = {"type": "text", "value": "x"}
    for _ in range(80):
        deep = {"type": "sqrt", "radicand": deep}
    expect_error(deep)
    for bad in (0, -1, float("inf"), float("nan"), 1e9, "12"):
        try:
            validate_font_size(bad)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"font_size {bad!r} accepted")

    print("selftest OK")


if __name__ == "__main__":
    main()
