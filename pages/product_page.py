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


FILTER_YEAR_ID = "pa-filter-year"
FILTER_BRANCH_ID = "pa-filter-branch"
FILTER_MANUFACTURER_ID = "pa-filter-manufacturer"
FILTER_CLIENT_ID = "pa-filter-client"
FILTER_CLIENT_CODE_ID = "pa-filter-client-code"

GENERAL_TABLE_ID = "pa-table-global"
GENERAL_CHART_ID = "pa-chart-global"
CLIENT_TABLE_ID = "pa-table-client"
CLIENT_CHART_ID = "pa-chart-client"
CLIENT_VIEW_TOGGLE_ID = "client-view-toggle"
CLIENT_VIEW_COLUMN_ID = "client-view-column"
CLIENT_TABLE_WRAPPER_ID = "client-table-wrapper"
CLIENT_CHART_WRAPPER_ID = "client-chart-wrapper"
CLIENT_NO_DATA_ID = "client-no-data-card"
CLIENT_SELECTED_MANUFACTURER_STORE_ID = "client-selected-manufacturer"
GENERAL_SELECTED_MANUFACTURER_STORE_ID = "global-selected-manufacturer"
CONTENT_GRID_ID = "pa-content-grid"

GENERAL_COLUMN_STYLE = {
    "display": "flex",
    "flexDirection": "column",
    "gap": "12px",
}

_CLIENT_COLUMN_BASE_STYLE = {
    "display": "flex",
    "flexDirection": "column",
    "gap": "12px",
}
CLIENT_VIEW_COLUMN_VISIBLE_STYLE = {**_CLIENT_COLUMN_BASE_STYLE, "display": "flex"}
CLIENT_VIEW_COLUMN_HIDDEN_STYLE = {**_CLIENT_COLUMN_BASE_STYLE, "display": "none"}

GRID_BASE_STYLE = {
    "display": "grid",
    "gridTemplateColumns": "repeat(2, minmax(0, 1fr))",
    "gap": "16px",
    "alignItems": "start",
}
GRID_SINGLE_COLUMN_STYLE = dict(GRID_BASE_STYLE, gridTemplateColumns="minmax(0, 1fr)")


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
                                id=FILTER_YEAR_ID,
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
                                id=FILTER_BRANCH_ID,
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
                                id=FILTER_MANUFACTURER_ID,
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
                                fixed_rows={"headers": True},
                                style_table={
                                    "height": "520px",
                                    "overflowY": "auto",
                                    "overflowX": "hidden",
                                    "border": f"1px solid {IC_GRAY}",
                                    "borderRadius": "10px",
                                },
                                style_header={
                                    "backgroundColor": IC_NAVY,
                                    "color": IC_WHITE,
                                    "fontWeight": "700",
                                    "position": "sticky",
                                    "top": 0,
                                    "zIndex": 2,
                                },
                                style_cell={
                                    "padding": "6px 8px",
                                    "fontFamily": "Arial",
                                    "fontSize": "13px",
                                    "whiteSpace": "nowrap",
                                    "overflow": "hidden",
                                    "textOverflow": "ellipsis",
                                    "minWidth": "120px",
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
                                    fixed_rows={"headers": True},
                                    style_table={
                                        "height": "520px",
                                        "overflowY": "auto",
                                        "overflowX": "hidden",
                                        "border": f"1px solid {IC_GRAY}",
                                        "borderRadius": "10px",
                                    },
                                    style_header={
                                        "backgroundColor": IC_NAVY,
                                        "color": IC_WHITE,
                                        "fontWeight": "700",
                                        "position": "sticky",
                                        "top": 0,
                                        "zIndex": 2,
                                    },
                                    style_cell={
                                        "padding": "6px 8px",
                                        "fontFamily": "Arial",
                                        "fontSize": "13px",
                                        "whiteSpace": "nowrap",
                                        "overflow": "hidden",
                                        "textOverflow": "ellipsis",
                                        "minWidth": "120px",
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
                id=CONTENT_GRID_ID,
                style=GRID_BASE_STYLE,
            ),
            dcc.Store(id=CLIENT_SELECTED_MANUFACTURER_STORE_ID),
            dcc.Store(id=GENERAL_SELECTED_MANUFACTURER_STORE_ID),
        ],
        style={
            "padding": "16px",
            "background": IC_BG,
            "minHeight": "100vh",
        },
    )


# Import callbacks to ensure they are registered when Dash scans the page module.
from . import product_callbacks  # noqa: E402,F401
