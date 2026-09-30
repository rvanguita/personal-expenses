"""Helpers shared by the Dash test modules."""

import pytest
from dash import dcc


def walk(component):
    """Yields every Dash component under ``component`` (lists and nested children included)."""
    stack = [component]
    while stack:
        node = stack.pop()
        if isinstance(node, list | tuple):
            stack.extend(node)
            continue
        if node is None or isinstance(node, str | int | float):
            continue
        yield node
        children = getattr(node, "children", None)
        if children is not None:
            stack.append(children)


@pytest.fixture
def ids():
    return lambda component: {n.id for n in walk(component) if getattr(n, "id", None)}


@pytest.fixture
def graphs():
    return lambda component: [n.figure for n in walk(component) if isinstance(n, dcc.Graph)]


@pytest.fixture
def texts():
    return lambda component: [
        n.children for n in walk(component) if isinstance(getattr(n, "children", None), str)
    ]
