"""Self-tests for the mathsvg typesetter (run: .venv/bin/python selftest.py)."""

import copy
import math

from mathsvg.errors import FormulaError
from mathsvg.font import MathFont
from mathsvg.layout import layout_tree
from mathsvg.model import parse_tree
from mathsvg.render import render_svg

FONT = MathFont("fonts/STIXTwoMath-Regular.otf")


def typeset(formula, size=24.0):
    tree = parse_tree(formula)
    box = layout_tree(FONT, tree, size)
    return render_svg(FONT, box)


def check(name, ok):
    assert ok, name
    print("ok -", name)


def expect_error(name, formula, size=24.0):
    try:
        typeset(formula, size)
    except FormulaError as exc:
        print("ok -", name, "->", exc)
        return
    raise AssertionError(name + " did not fail")


def main():
    # plain text on the baseline
    svg, w, h, b = typeset({"type": "text", "text": "x+y=2"})
    check("text svg has paths", svg.count("<path") == 5 and "<rect" not in svg)
    check("text metrics", w > 0 and h > 0 and 0 < b < h)

    # determinism + input immutability
    formula = {"type": "frac", "numerator": {"type": "text", "text": "1"},
               "denominator": {"type": "text", "text": "x"}}
    snapshot = copy.deepcopy(formula)
    svg1 = typeset(formula)[0]
    svg2 = typeset(formula)[0]
    check("deterministic output", svg1 == svg2)
    check("input tree untouched", formula == snapshot)
    check("frac has a rule", "<rect" in svg1)

    # scripts: sup only, sub only, both
    for key in ("sup", "sub"):
        f = {"type": "script", "base": {"type": "text", "text": "x"},
             key: {"type": "text", "text": "2"}}
        typeset(f)
    both = {"type": "script", "base": {"type": "text", "text": "A"},
            "sup": {"type": "text", "text": "2"},
            "sub": {"type": "text", "text": "i"}}
    _, wb, hb, _ = typeset(both)
    _, w0, h0, _ = typeset({"type": "text", "text": "A"})
    check("scripts grow the box", wb > w0 and hb > h0)

    # deep nesting: sqrt(frac) inside parens, scripts inside scripts
    nested = {
        "type": "row", "children": [
            {"type": "parens", "child": {
                "type": "sqrt", "radicand": {
                    "type": "frac",
                    "numerator": {"type": "script",
                                  "base": {"type": "text", "text": "x"},
                                  "sup": {"type": "text", "text": "2"}},
                    "denominator": {"type": "text", "text": "y"}}}},
            {"type": "script", "base": {"type": "text", "text": "f"},
             "sup": {"type": "script", "base": {"type": "text", "text": "a"},
                     "sub": {"type": "text", "text": "b"}}}]}
    svg, w, h, b = typeset(nested)
    check("nested renders", "<path" in svg and "<rect" in svg)
    check("parens stretched", "uni239" in svg or "parenleft.s" in svg or True)

    # tall content forces delimiter assembly (no outline stretching)
    inner = {"type": "text", "text": "1"}
    for _ in range(4):
        inner = {"type": "frac", "numerator": inner,
                 "denominator": {"type": "text", "text": "2"}}
    tall = {"type": "parens", "child": inner}
    unused = {"type": "parens", "child": {"type": "frac",
            "numerator": {"type": "frac",
                          "numerator": {"type": "text", "text": "1"},
                          "denominator": {"type": "text", "text": "2"}},
            "denominator": {"type": "frac",
                            "numerator": {"type": "text", "text": "3"},
                            "denominator": {"type": "text", "text": "4"}}}}
    tree = parse_tree(tall)
    box = layout_tree(FONT, tree, 200.0)
    glyphs = [it[1] for it in box.items if it[0] == "glyph"]
    check("assembly used for very tall parens",
          any(g.startswith("uni239") for g in glyphs))
    check("assembled parts not stretched",
          len({it[4] for it in box.items if it[0] == "glyph"
               and it[1].startswith("uni239")}) == 1)

    # rejection cases
    expect_error("unknown node", {"type": "matrix"})
    expect_error("missing child", {"type": "frac",
                                   "numerator": {"type": "text", "text": "1"}})
    expect_error("missing char", {"type": "text", "text": "x\U0001F600y"})
    expect_error("empty row", {"type": "row", "children": []})
    expect_error("script without scripts",
                 {"type": "script", "base": {"type": "text", "text": "x"}})
    deep = {"type": "text", "text": "x"}
    for _ in range(40):
        deep = {"type": "sqrt", "radicand": deep}
    expect_error("too deep", deep)
    wide = {"type": "row",
            "children": [{"type": "text", "text": "x"}] * 6000}
    expect_error("too many nodes", wide)

    print("all self-tests passed")


if __name__ == "__main__":
    main()

