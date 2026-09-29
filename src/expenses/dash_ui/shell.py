"""App shell: header + navigation, sticky filter bar, cross-filter chips (all pt-BR)."""

import dash
import dash_mantine_components as dmc
from dash import dcc, html

from src.expenses.filters import (
    INSTALLMENT_ALL,
    INSTALLMENT_ONLY,
    INSTALLMENT_SINGLE,
    PERIOD_OPTIONS,
    TX_ALL,
    TX_GROSS,
    TX_NET,
    TX_REFUNDS,
)

NAV = [
    ("/", "📊 Visão geral"),
    ("/tendencias", "📈 Tendências"),
    ("/categorias", "🔍 Categorias"),
    ("/relatorios", "📑 Relatórios"),
]
CROSS_FILTER_PATHS = ("/", "/categorias")

_PERIOD_PT = {
    "Last 6 months": "Últimos 6 meses",
    "Last 3 months": "Últimos 3 meses",
    "Last 12 months": "Últimos 12 meses",
    "All History": "Todo o histórico",
    "Custom": "Personalizado",
}
_TX_PT = {
    TX_NET: "Despesas líquidas (compras − estornos)",
    TX_GROSS: "Somente compras (positivas)",
    TX_REFUNDS: "Somente estornos (negativos)",
    TX_ALL: "Todas as transações",
}
_INSTALLMENT_PT = {
    INSTALLMENT_ALL: "Todas",
    INSTALLMENT_SINGLE: "À vista",
    INSTALLMENT_ONLY: "Parceladas",
}
MULTI_FILTERS = {"months": "Faturas", "holders": "Portadores", "cats": "Categorias"}


def _data(mapping: dict) -> list[dict]:
    return [{"value": k, "label": v} for k, v in mapping.items()]


def multi_filter(key: str, label: str) -> dmc.Popover:
    return dmc.Popover(
        width=280,
        position="bottom-start",
        shadow="md",
        withArrow=True,
        children=[
            dmc.PopoverTarget(dmc.Button(label, id=f"{key}-btn", variant="default", size="sm")),
            dmc.PopoverDropdown(
                dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Button(
                                    "Todos", id=f"{key}-all", size="compact-xs", variant="light"
                                ),
                                dmc.Button(
                                    "Nenhum", id=f"{key}-none", size="compact-xs", variant="light"
                                ),
                            ],
                            gap="xs",
                        ),
                        dmc.ScrollArea(
                            dmc.CheckboxGroup(
                                id=f"{key}-value",
                                value=[],
                                children=dmc.Stack(id=f"{key}-opts", gap="xs", children=[]),
                            ),
                            h=260,
                            type="auto",
                        ),
                    ],
                    gap="xs",
                )
            ),
        ],
    )


def more_filters() -> dmc.Popover:
    return dmc.Popover(
        width=320,
        position="bottom-end",
        shadow="md",
        withArrow=True,
        children=[
            dmc.PopoverTarget(
                dmc.Button("⚙️ Mais filtros", id="more-btn", variant="default", size="sm")
            ),
            dmc.PopoverDropdown(
                dmc.Stack(
                    [
                        dmc.Select(
                            id="tx-type",
                            label="Tipo de transação",
                            data=_data(_TX_PT),
                            value=TX_NET,
                            allowDeselect=False,
                        ),
                        dmc.Select(
                            id="installment-type",
                            label="Forma de pagamento",
                            data=_data(_INSTALLMENT_PT),
                            value=INSTALLMENT_ALL,
                            allowDeselect=False,
                        ),
                        dmc.TextInput(
                            id="search-id",
                            label="Buscar estabelecimento",
                            placeholder="Ex.: Mercado…",
                        ),
                    ],
                    gap="sm",
                )
            ),
        ],
    )


def filter_bar() -> dmc.Paper:
    return dmc.Paper(
        dmc.Group(
            [
                dmc.Select(
                    id="period",
                    data=[{"value": p, "label": _PERIOD_PT[p]} for p in PERIOD_OPTIONS],
                    value=PERIOD_OPTIONS[0],
                    allowDeselect=False,
                    size="sm",
                    w=190,
                    leftSection="📅",
                ),
                multi_filter("months", MULTI_FILTERS["months"]),
                multi_filter("holders", MULTI_FILTERS["holders"]),
                multi_filter("cats", MULTI_FILTERS["cats"]),
                more_filters(),
                dmc.Button("🔄 Atualizar", id="refresh", n_clicks=0, size="sm", variant="light"),
                dmc.Text(id="record-count", size="xs", c="dimmed", ml="auto"),
            ],
            gap="sm",
            wrap="wrap",
        ),
        withBorder=True,
        p="xs",
        radius="md",
        className="filter-bar",
    )


def header() -> dmc.AppShellHeader:
    return dmc.AppShellHeader(
        dmc.Group(
            [
                dmc.Group(
                    [
                        dmc.Text("💳", size="xl"),
                        dmc.Text(
                            "Despesas & Inteligência Financeira",
                            fw=700,
                            size="lg",
                            visibleFrom="sm",
                        ),
                    ],
                    gap="xs",
                ),
                dmc.Group(
                    [
                        dmc.NavLink(label=label, href=path, active="exact", w="auto")
                        for path, label in NAV
                    ],
                    gap="xs",
                    className="nav-links",
                ),
                dmc.Group(
                    [
                        dmc.Switch(
                            id="hide-switch",
                            label="🙈 Ocultar valores",
                            checked=False,
                            persistence=True,
                            persistence_type="local",
                            size="sm",
                        ),
                        dmc.ActionIcon("🌗", id="theme-toggle", variant="default", size="lg"),
                    ],
                    gap="md",
                ),
            ],
            justify="space-between",
            h="100%",
            px="md",
            wrap="nowrap",
        ),
    )


def create_layout() -> dmc.MantineProvider:
    return dmc.MantineProvider(
        id="mantine",
        forceColorScheme="dark",
        theme={"primaryColor": "cyan", "defaultRadius": "md"},
        children=[
            dcc.Location(id="url"),
            dcc.Store(id="filters"),
            dcc.Store(id="meta"),
            dcc.Store(id="selection", storage_type="session", data={}),
            dcc.Store(id="theme", storage_type="local", data="dark"),
            dmc.AppShell(
                header={"height": 60},
                padding="md",
                children=[
                    header(),
                    dmc.AppShellMain(
                        dmc.Stack(
                            [
                                html.Div(id="banner"),
                                filter_bar(),
                                html.Div(id="selection-chips"),
                                dash.page_container,
                            ],
                            gap="md",
                        )
                    ),
                ],
            ),
        ],
    )
