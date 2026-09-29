"""Shared helpers for page callbacks: chart context, guards and an error boundary."""

import functools
import logging
from contextlib import contextmanager

import dash_mantine_components as dmc
from dash.exceptions import PreventUpdate

from src.expenses.ui.charts import chart_context

logger = logging.getLogger("expenses.dash")


@contextmanager
def render_ctx(theme: str | None, hide: bool | None):
    """Plotly theme/language/hide-amounts for every figure built in the block."""
    with chart_context(theme_base=theme or "dark", hide_amounts=bool(hide), lang="pt"):
        yield


def safe_render(n_outputs: int = 1):
    """Decorator: skip until filters exist; on error log and return an error alert for output 0."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(filters, *args, **kwargs):
            if not filters:
                raise PreventUpdate
            try:
                return func(filters, *args, **kwargs)
            except PreventUpdate:
                raise
            except Exception:
                logger.exception("Falha ao renderizar %s", func.__name__)
                alert = dmc.Alert(
                    "Não foi possível montar esta página. Veja o log do servidor.",
                    color="red",
                    title="Erro",
                )
                from dash import no_update

                return alert if n_outputs == 1 else (alert, *[no_update] * (n_outputs - 1))

        return wrapper

    return decorator
