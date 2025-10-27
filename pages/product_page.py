"""Product Analysis page layout and registration.

This module only defines the static layout for the page. The Dash callbacks
that provide interactivity live in :mod:`pages.product_callbacks` so they can
focus solely on data access and plotting logic. Keeping the definitions split
between the layout and the callback logic prevents accidental circular imports
and makes it clearer where to look when adjusting the UI versus the data flow.
"""

from __future__ import annotations

import dash
from dash import dcc, html, dash_table

from data.app_data import (
    FILIALAS_OPTIONS,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_WHITE,
    YEAR_OPTIONS,
)


PAGE_ID_PREFIX = "product_analysis"

# Reusable layout fragments -------------------------------------------------

TABLE_COLUMNS = [
    {"name": "Manufacturer", "id": "Manufacturer"},
    {"name": "Apyvarta (Turnover €)", "id": "Apyvarta"},
    {"name": "Pajamos (Revenue €)", "id": "Pajamos"},
    {"name": "Kiekis (Quantity)", "id": "Kiekis"},
    {"name": "Marža % (Margin %)", "id": "Marža %"},
]

FILTER_CONTAINER_STYLE = {
    "display": "flex",
    "flexWrap": "wrap",
    "gap": "10px",
    "alignItems": "flex-end",
    "margin": "6px 0 14px 0",
}

PAGE_STYLE = {
    "padding": "16px",
    "background": IC_BG,
    "minHeight": "100vh",
}


dash.register_page(
    __name__,
    path="/product-analysis",
    name="Product Analysis",
    title="Product Analysis",
)


def _default_year() -> int | None:
    """Return the latest available year from preloaded summary data."""

    if not YEAR_OPTIONS:
        return None
    return int(sorted(YEAR_OPTIONS)[-1])


DEFAULT_BRANCHES = ["L51", "L52"]


def layout():
    """Render the product analysis page layout."""

    year_options = [
        {"label": str(int(year)), "value": int(year)}
        for year in sorted(YEAR_OPTIONS)
    ]

    branch_options = [
        {"label": branch, "value": branch}
        for branch in FILIALAS_OPTIONS
    ]

    return html.Div(
        [
            html.Div(
                "Product Analysis",
                style={
                    "fontSize": "20px",
                    "fontWeight": 800,
                    "color": IC_NAVY,
                    "margin": "12px 0",
                },
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Year"),
                            dcc.Dropdown(
                                id=f"{PAGE_ID_PREFIX}_year",
                                options=year_options,
                                value=_default_year(),
                                clearable=False,
                            ),
                        ],
                        style={"flex": "1 1 160px", "minWidth": "160px"},
                    ),
                    html.Div(
                        [
                            html.Label("Branch"),
                            dcc.Dropdown(
                                id=f"{PAGE_ID_PREFIX}_branch",
                                options=branch_options,
                                value=[b for b in DEFAULT_BRANCHES if b in FILIALAS_OPTIONS]
                                or FILIALAS_OPTIONS[:2],
                                multi=True,
                                clearable=False,
                                placeholder="All branches",
                            ),
                        ],
                        style={"flex": "1 1 220px", "minWidth": "200px"},
                    ),
                    html.Div(
                        [
                            html.Label("Manufacturer"),
                            dcc.Dropdown(
                                id=f"{PAGE_ID_PREFIX}_manufacturer",
                                options=[],
                                value=None,
                                multi=False,
                                placeholder="All manufacturers",
                                clearable=True,
                                searchable=True,
                            ),
                        ],
                        style={"flex": "2 1 300px", "minWidth": "260px"},
                    ),
                ],
                style=FILTER_CONTAINER_STYLE,
            ),
            dash_table.DataTable(
                id=f"{PAGE_ID_PREFIX}_table",
                columns=TABLE_COLUMNS,
                data=[],
                style_table={
                    "overflowX": "auto",
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "maxHeight": "60vh",
                },
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": "700",
                },
                style_cell={
                    "padding": "6px 8px",
                    "fontFamily": "Arial",
                    "fontSize": "13px",
                    "whiteSpace": "nowrap",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
                    {
                        "if": {"column_id": ["Apyvarta", "Pajamos", "Marža %", "Kiekis"]},
                        "textAlign": "right",
                    },
                ],
                page_action="none",
                sort_action="none",
                cell_selectable=False,
                row_deletable=False,
            ),
            html.Div(
                dcc.Graph(
                    id=f"{PAGE_ID_PREFIX}_chart",
                    config={"responsive": True, "displayModeBar": False},
                    style={"height": "540px", "width": "100%"},
                ),
                style={
                    "marginTop": "18px",
                    "background": IC_WHITE,
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "padding": "10px",
                },
            ),
        ],
        style=PAGE_STYLE,
    )


# Import callbacks to ensure they are registered when Dash scans the page module.
from . import product_callbacks  # noqa: E402,F401
