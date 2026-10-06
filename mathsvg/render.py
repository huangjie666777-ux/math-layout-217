"""SVG rendering: emits glyph outlines as paths plus rule rectangles.

The output is self-contained (no fonts, links, scripts or foreignObject).
The viewBox is the union of the layout box and the actual ink bounds, so
nothing is ever clipped. All lengths share one unit (the request size).
"""

from __future__ import annotations

from .font import MathFont
from .layout import Box


def _fmt(value: float) -> str:
    text = "%.3f" % value
    text = text.rstrip("0").rstrip(".")
    return text if text else "0"


def render_svg(font: MathFont, box: Box):
    """Return (svg, width, height, baseline_from_top)."""
    # Union of layout metrics and real ink bounds, in baseline coords (y up).
    min_x = min(0.0, box.width)
    max_x = max(0.0, box.width)
    min_y = min(0.0, -box.depth)
    max_y = max(0.0, box.height)
    for item in box.items:
        if item[0] == "glyph":
            _, name, x, y, s = item
            gx0, gy0, gx1, gy1 = font.ink_bounds(name)
            min_x = min(min_x, x + gx0 * s)
            max_x = max(max_x, x + gx1 * s)
            min_y = min(min_y, y + gy0 * s)
            max_y = max(max_y, y + gy1 * s)
        else:
            _, x, y, w, h = item
            min_x = min(min_x, x)
            max_x = max(max_x, x + w)
            min_y = min(min_y, y)
            max_y = max(max_y, y + h)
    width = max_x - min_x
    height = max_y - min_y
    baseline = max_y  # distance from the top of the viewBox to the baseline

    parts = []
    for item in box.items:
        if item[0] == "glyph":
            _, name, x, y, s = item
            tx = x - min_x
            ty = baseline - y
            d = font.path_data(name)
            if not d:
                continue
            parts.append(
                '<path d="%s" transform="translate(%s %s) scale(%s %s)"/>'
                % (d, _fmt(tx), _fmt(ty), _fmt(s), _fmt(-s)))
        else:
            _, x, y, w, h = item
            parts.append('<rect x="%s" y="%s" width="%s" height="%s"/>'
                         % (_fmt(x - min_x), _fmt(baseline - y - h),
                            _fmt(w), _fmt(h)))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
           'viewBox="0 0 %s %s">%s</svg>'
           % (_fmt(width), _fmt(height), _fmt(width), _fmt(height),
              "".join(parts)))
    return svg, width, height, baseline

