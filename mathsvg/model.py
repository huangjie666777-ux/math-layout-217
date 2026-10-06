"""Validation of the incoming JSON formula tree.

Builds an immutable internal node tree; the caller input is never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import FormulaError

MAX_DEPTH = 32
MAX_NODES = 5000
MAX_TEXT_LEN = 1000


@dataclass(frozen=True)
class Node:
    type: str
    text: str = ""
    children: tuple = ()
    # frac: children = (numerator, denominator)
    # script: sup/sub stored below, base in children[0]
    sup: "Node | None" = None
    sub: "Node | None" = None


class _Counter:
    def __init__(self):
        self.count = 0


def parse_tree(raw, counter=None, depth=0) -> Node:
    if counter is None:
        counter = _Counter()
    counter.count += 1
    if counter.count > MAX_NODES:
        raise FormulaError("formula tree has too many nodes")
    if depth > MAX_DEPTH:
        raise FormulaError("formula tree is nested too deeply")
    if not isinstance(raw, dict):
        raise FormulaError("node must be a JSON object")
    ntype = raw.get("type")
    if not isinstance(ntype, str):
        raise FormulaError("node is missing a string \"type\" field")

    if ntype == "text":
        text = raw.get("text")
        if not isinstance(text, str) or not text:
            raise FormulaError("text node requires a non-empty \"text\" string")
        if len(text) > MAX_TEXT_LEN:
            raise FormulaError("text node is too long")
        return Node(type="text", text=text)

    if ntype == "row":
        children = raw.get("children")
        if not isinstance(children, list) or not children:
            raise FormulaError("row node requires a non-empty \"children\" list")
        return Node(type="row", children=tuple(
            parse_tree(c, counter, depth + 1) for c in children))

    if ntype == "frac":
        num = raw.get("numerator")
        den = raw.get("denominator")
        if num is None or den is None:
            raise FormulaError("frac node requires \"numerator\" and \"denominator\"")
        return Node(type="frac", children=(
            parse_tree(num, counter, depth + 1),
            parse_tree(den, counter, depth + 1)))

    if ntype == "script":
        base = raw.get("base")
        if base is None:
            raise FormulaError("script node requires \"base\"")
        sup = raw.get("sup")
        sub = raw.get("sub")
        if sup is None and sub is None:
            raise FormulaError("script node requires \"sup\" and/or \"sub\"")
        return Node(
            type="script",
            children=(parse_tree(base, counter, depth + 1),),
            sup=parse_tree(sup, counter, depth + 1) if sup is not None else None,
            sub=parse_tree(sub, counter, depth + 1) if sub is not None else None)

    if ntype == "sqrt":
        radicand = raw.get("radicand")
        if radicand is None:
            raise FormulaError("sqrt node requires \"radicand\"")
        return Node(type="sqrt", children=(
            parse_tree(radicand, counter, depth + 1),))

    if ntype == "parens":
        child = raw.get("child")
        if child is None:
            raise FormulaError("parens node requires \"child\"")
        return Node(type="parens", children=(
            parse_tree(child, counter, depth + 1),))

    raise FormulaError("unknown node type: %r" % ntype)

