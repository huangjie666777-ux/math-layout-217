"""HTTP delivery: FastAPI app exposing POST /render."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .font import MathFont, FontError
from .layout import Layout
from .nodes import ValidationError, validate_font_size, validate_tree
from .svg import render_svg

FONT_PATH = Path(__file__).resolve().parent.parent / "fonts" / "STIXTwoMath-Regular.otf"

app = FastAPI(title="Math Formula Typesetter")
_font = MathFont(str(FONT_PATH))


class RenderRequest(BaseModel):
    formula: Any
    font_size: Any


@app.exception_handler(ValidationError)
async def validation_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(FontError)
async def font_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.post("/render")
async def render(req: RenderRequest):
    size = validate_font_size(req.font_size)
    tree = validate_tree(req.formula, lambda ch: _font.glyph_for(ch) is not None)
    box = Layout(_font, size).layout(tree)
    svg, width, height, baseline = render_svg(box, _font)
    return {"svg": svg, "width": width, "height": height, "baseline": baseline}
