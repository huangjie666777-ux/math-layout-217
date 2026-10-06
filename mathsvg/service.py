"""HTTP delivery: FastAPI app exposing the typesetter."""

from __future__ import annotations

import math
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .errors import FormulaError
from .font import MathFont
from .layout import layout_tree
from .model import parse_tree
from .render import render_svg

FONT_PATH = os.environ.get(
    "MATHSVG_FONT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "fonts", "STIXTwoMath-Regular.otf"))

MAX_SIZE = 1000.0

font = MathFont(FONT_PATH)
app = FastAPI(title="mathsvg")


class TypesetRequest(BaseModel):
    formula: dict
    size: float


@app.post("/typeset")
def typeset(req: TypesetRequest):
    if not math.isfinite(req.size) or req.size <= 0 or req.size > MAX_SIZE:
        return JSONResponse(
            status_code=400,
            content={"detail": "size must be a finite number in (0, %g]"
                               % MAX_SIZE})
    try:
        tree = parse_tree(req.formula)
        box = layout_tree(font, tree, req.size)
        svg, width, height, baseline = render_svg(font, box)
    except FormulaError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return {"svg": svg, "width": width, "height": height,
            "baseline": baseline}


@app.get("/health")
def health():
    return {"status": "ok"}

