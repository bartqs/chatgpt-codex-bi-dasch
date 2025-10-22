"""Product Analysis page layout and registration."""

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

GENERAL_TABLE_ID = "product-table"
GENERAL_CHART_ID = "product-combo-chart"
CLIENT_TABLE_ID = "client-product-table"
CLIENT_CHART_ID = "client-product-combo-chart"
FILTER_CLIENT_ID = "filter-client"
FILTER_CLIENT_CODE_ID = "filter-client-code"
CLIENT_VIEW_TOGGLE_ID = "client-view-toggle"
CLIENT_VIEW_COLUMN_ID = "client-view-column"
CLIENT_TABLE_WRAPPER_ID = "client-table-wrapper"
CLIENT_CHART_WRAPPER_ID = "client-chart-wrapper"
CLIENT_NO_DATA_ID = "client-no-data-card"
CLIENT_SELECTED_MANUFACTURER_STORE_ID = "client-selected-manufacturer"

GENERAL_COLUMN_STYLE = {
    "flex": "1 1 0",
    "minWidth": "360px",
    "display": "flex",
    "flexDirection": "column",
    "gap": "16px",
}

_CLIENT_COLUMN_BASE_STYLE = {
    "flex": "1 1 0",
    "minWidth": "360px",
    "flexDirection": "column",
    "gap": "16px",
}
CLIENT_VIEW_COLUMN_VISIBLE_STYLE = {**_CLIENT_COLUMN_BASE_STYLE, "display": "flex"}
CLIENT_VIEW_COLUMN_HIDDEN_STYLE = {**_CLIENT_COLUMN_BASE_STYLE, "display": "none"}


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
                            html.Label("Klientas"),
                            dcc.Dropdown(
                                id=FILTER_CLIENT_ID,
                                options=[],
                                value=None,
                                clearable=True,
                                placeholder="Pasirinkite klientą",
                                searchable=True,
                            ),
                        ],
                        style={"flex": "1 1 220px", "minWidth": "200px"},
                    ),
                    html.Div(
                        [
                            html.Label("Kliento kodas"),
                            dcc.Dropdown(
                                id=FILTER_CLIENT_CODE_ID,
                                options=[],
                                value=[],
                                multi=True,
                                placeholder="Visi kodai",
                                clearable=True,
                                searchable=True,
                            ),
                        ],
                        style={"flex": "1 1 260px", "minWidth": "220px"},
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
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "gap": "10px",
                    "alignItems": "flex-end",
                    "margin": "6px 0 14px 0",
                },
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dash_table.DataTable(
                                id=GENERAL_TABLE_ID,
                                columns=[
                                    {"name": "Manufacturer", "id": "Manufacturer"},
                                    {"name": "Apyvarta (Turnover €)", "id": "Apyvarta"},
                                    {"name": "Pajamos (Revenue €)", "id": "Pajamos"},
                                    {"name": "Kiekis (Quantity)", "id": "Kiekis"},
                                    {"name": "Marža % (Margin %)", "id": "Marža %"},
                                ],
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
                                        "if": {
                                            "column_id": [
                                                "Apyvarta",
                                                "Pajamos",
                                                "Marža %",
                                                "Kiekis",
                                            ]
                                        },
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
                                    id=GENERAL_CHART_ID,
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
                        style=GENERAL_COLUMN_STYLE,
                    ),
                    html.Div(
                        [
                            html.Div(
                                html.Button(
                                    "Išjungti kliento vaizdą",
                                    id=CLIENT_VIEW_TOGGLE_ID,
                                    n_clicks=0,
                                    style={
                                        "background": IC_NAVY,
                                        "color": IC_WHITE,
                                        "border": "none",
                                        "borderRadius": "8px",
                                        "padding": "8px 16px",
                                        "fontWeight": 600,
                                        "cursor": "pointer",
                                    },
                                ),
                                style={
                                    "display": "flex",
                                    "justifyContent": "flex-end",
                                },
                            ),
                            html.Div(
                                "No data",
                                id=CLIENT_NO_DATA_ID,
                                hidden=True,
                                style={
                                    "background": IC_WHITE,
                                    "border": f"1px solid {IC_GRAY}",
                                    "borderRadius": "10px",
                                    "padding": "28px",
                                    "textAlign": "center",
                                    "fontWeight": 600,
                                    "color": IC_NAVY,
                                },
                            ),
                            html.Div(
                                dash_table.DataTable(
                                    id=CLIENT_TABLE_ID,
                                    columns=[
                                        {"name": "Manufacturer", "id": "Manufacturer"},
                                        {"name": "Apyvarta (Turnover €)", "id": "Apyvarta"},
                                        {"name": "Pajamos (Revenue €)", "id": "Pajamos"},
                                        {"name": "Kiekis (Quantity)", "id": "Kiekis"},
                                        {"name": "Marža % (Margin %)", "id": "Marža %"},
                                    ],
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
                                            "if": {
                                                "column_id": [
                                                    "Apyvarta",
                                                    "Pajamos",
                                                    "Marža %",
                                                    "Kiekis",
                                                ]
                                            },
                                            "textAlign": "right",
                                        },
                                    ],
                                    page_action="none",
                                    sort_action="none",
                                    cell_selectable=False,
                                    row_deletable=False,
                                ),
                                id=CLIENT_TABLE_WRAPPER_ID,
                                hidden=True,
                            ),
                            html.Div(
                                dcc.Graph(
                                    id=CLIENT_CHART_ID,
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
                                id=CLIENT_CHART_WRAPPER_ID,
                                hidden=True,
                            ),
                        ],
                        id=CLIENT_VIEW_COLUMN_ID,
                        style=CLIENT_VIEW_COLUMN_HIDDEN_STYLE,
                    ),
                        ],
                        style={
                            "display": "flex",
                            "flexWrap": "nowrap",
                            "gap": "16px",
                            "alignItems": "stretch",
                        },
            ),
            dcc.Store(id=CLIENT_SELECTED_MANUFACTURER_STORE_ID),
        ],
        style={
            "padding": "16px",
            "background": IC_BG,
            "minHeight": "100vh",
        },
    )


# Import callbacks to ensure they are registered when Dash scans the page module.
from . import product_callbacks  # noqa: E402,F401
