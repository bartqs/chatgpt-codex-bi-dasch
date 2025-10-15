from html import escape

import dash
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
import plotly.graph_objects as go
from typing import Any, Dict, Iterable, List, Optional, Tuple

from data.app_data import (
    CUSTOMER_COLORWAY,
    CUSTOMER_METRICS,
    GREEN,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_RED,
    IC_WHITE,
    MENUO_LABELS_LT,
    RED,
    _fmt_eur,
    _fmt_pct,
    _fmt_qty,
    compute_customer_category_detail_summary,
    compute_customer_category_group_summary,
    compute_customer_category_vendor_summary,
    compute_customer_monthly_aggregation,
    get_customer_filter_frame,
    get_customer_year_options,
    get_latest_customer_year,
)


dash.register_page(
    __name__,
    path="/customers",
    name="Klientų apžvalga",
    title="IC – Klientų apžvalga",
)


FILTER_FRAME = get_customer_filter_frame()
MANAGER_OPTIONS = sorted(FILTER_FRAME["Vadybininkas"].dropna().unique().tolist())
CLIENT_OPTIONS = sorted(FILTER_FRAME["Klientas"].dropna().unique().tolist())
CODE_OPTIONS = sorted(FILTER_FRAME["Kliento kodas"].dropna().unique().tolist())
YEAR_OPTIONS = get_customer_year_options()
LATEST_YEAR = get_latest_customer_year()
DEFAULT_YEARS = []
if LATEST_YEAR:
    DEFAULT_YEARS = [y for y in YEAR_OPTIONS if LATEST_YEAR - 3 <= y <= LATEST_YEAR]
    DEFAULT_YEARS = sorted(DEFAULT_YEARS) or [LATEST_YEAR]

METRIC_COLUMN_MAP = {
    "APYVARTA": "Apyvarta",
    "PAJAMOS": "Pajamos",
    "KIEKIS": "Kiekis",
    "MARŽA %": "MARŽA %",
}

YOY_POS_BG = "rgba(46, 125, 50, 0.2)"
YOY_NEG_BG = "rgba(227, 6, 19, 0.2)"
YOY_NEUTRAL_BG = "rgba(120, 120, 120, 0.16)"

BADGE_POS_BG = "rgba(46, 125, 50, 0.18)"
BADGE_NEG_BG = "rgba(227, 6, 19, 0.18)"
BADGE_NEUTRAL_BG = "rgba(120, 120, 120, 0.18)"
BADGE_TEXT_NEUTRAL = "#6c757d"


CHART_HEIGHT = 450


BASE_TABLE_STYLE = {
    "overflowX": "hidden",
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "minWidth": "100%",
}

BASE_CELL_STYLE = {
    "padding": "6px 10px",
    "fontFamily": "Arial",
    "fontSize": "13px",
    "textAlign": "right",
    "whiteSpace": "nowrap",
}

BASE_CELL_CONDITIONAL = [
    {
        "if": {"column_id": "Mėnuo"},
        "textAlign": "left",
        "minWidth": "90px",
        "width": "90px",
        "maxWidth": "110px",
    }
]


CATEGORY_TABLE_STYLE = {
    "overflowX": "auto",
    "overflowY": "auto",
    "maxHeight": "420px",
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "minWidth": "100%",
}

CATEGORY_CELL_STYLE = {
    "padding": "6px 10px",
    "fontFamily": "Arial",
    "fontSize": "13px",
    "textAlign": "right",
    "whiteSpace": "nowrap",
}

CATEGORY_CELL_CONDITIONAL = [
    {
        "if": {"column_id": "Kategorijos grupe"},
        "textAlign": "left",
        "minWidth": "200px",
        "width": "200px",
        "maxWidth": "260px",
    }
]


CATEGORY_DETAIL_TABLE_STYLE = {
    "overflowX": "auto",
    "overflowY": "auto",
    "maxHeight": "380px",
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "minWidth": "100%",
}

CATEGORY_DETAIL_CELL_STYLE = {
    "padding": "6px 10px",
    "fontFamily": "Arial",
    "fontSize": "13px",
    "textAlign": "right",
    "whiteSpace": "nowrap",
}

CATEGORY_DETAIL_CELL_CONDITIONAL = [
    {
        "if": {"column_id": "Kategorija"},
        "textAlign": "left",
        "minWidth": "220px",
        "width": "240px",
        "maxWidth": "320px",
    }
]


CATEGORY_DETAIL_WRAPPER_STYLE = {
    "background": IC_WHITE,
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "padding": "16px",
    "margin": "0 16px 32px",
}


CATEGORY_VENDOR_TABLE_STYLE = {
    "overflowX": "auto",
    "overflowY": "auto",
    "maxHeight": "360px",
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "minWidth": "100%",
}

CATEGORY_VENDOR_CELL_STYLE = {
    "padding": "6px 10px",
    "fontFamily": "Arial",
    "fontSize": "13px",
    "textAlign": "right",
    "whiteSpace": "nowrap",
}

CATEGORY_VENDOR_CELL_CONDITIONAL = [
    {
        "if": {"column_id": "Gamintojas (pavad)"},
        "textAlign": "left",
        "minWidth": "220px",
        "width": "240px",
        "maxWidth": "320px",
    }
]


CATEGORY_VENDOR_WRAPPER_STYLE = {
    "background": IC_WHITE,
    "border": f"1px solid {IC_GRAY}",
    "borderRadius": "10px",
    "padding": "16px",
    "margin": "0 16px 32px",
}


EMPTY_MESSAGE = html.Div(
    [
        html.Div("🧩", style={"fontSize": "36px", "marginBottom": "12px"}),
        html.Div("Pasirinkite klientą, kad matytumėte duomenis.", style={"color": "#6c757d"}),
    ],
    style={"textAlign": "center"},
)

NO_DATA_MESSAGE = html.Div(
    [
        html.Div("ℹ️", style={"fontSize": "32px", "marginBottom": "12px"}),
        html.Div("Duomenų nerasta pasirinktiems filtrams.", style={"color": "#6c757d"}),
    ],
    style={"textAlign": "center"},
)


def layout():
    """Render the customer overview page."""

    filter_row = html.Div(
        [
            html.Div(
                [
                    html.Label("Pardavimų vadybininkas"),
                    dcc.Dropdown(
                        options=[{"label": m, "value": m} for m in MANAGER_OPTIONS],
                        value=[],
                        multi=True,
                        placeholder="Visi",
                        id="customer-manager",
                        style={"minWidth": "200px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Klientas"),
                    dcc.Dropdown(
                        options=[{"label": c, "value": c} for c in CLIENT_OPTIONS],
                        value=[],
                        multi=True,
                        placeholder="Pasirinkite klientą",
                        id="customer-client",
                        style={"minWidth": "220px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Kliento kodas"),
                    dcc.Dropdown(
                        options=[{"label": c, "value": c} for c in CODE_OPTIONS],
                        value=[],
                        multi=True,
                        placeholder="Visi kodai",
                        id="customer-code",
                        style={"minWidth": "180px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Metai"),
                    dcc.Dropdown(
                        options=[{"label": int(y), "value": int(y)} for y in YEAR_OPTIONS],
                        value=DEFAULT_YEARS,
                        multi=True,
                        placeholder="Metai",
                        id="customer-years",
                        style={"minWidth": "160px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Label("Matas"),
                    dcc.Dropdown(
                        options=[{"label": m, "value": m} for m in CUSTOMER_METRICS],
                        value="APYVARTA",
                        clearable=False,
                        id="customer-metric",
                        style={"minWidth": "160px"},
                    ),
                ]
            ),
            html.Div(
                [
                    html.Button(
                        "Atstatyti filtrus",
                        id="customer-reset",
                        n_clicks=0,
                        style={
                            "border": f"1px solid {IC_RED}",
                            "background": "transparent",
                            "color": IC_RED,
                            "padding": "8px 16px",
                            "borderRadius": "8px",
                            "fontWeight": 600,
                        },
                    )
                ],
                style={"marginLeft": "auto"},
            ),
        ],
        style={
            "display": "flex",
            "gap": "12px",
            "flexWrap": "wrap",
            "alignItems": "end",
            "padding": "16px",
            "background": IC_WHITE,
            "borderBottom": f"1px solid {IC_GRAY}",
        },
    )

    status_bar = html.Div(
        id="customer-status-text",
        style={
            "padding": "8px 16px",
            "color": IC_NAVY,
            "fontSize": "13px",
            "background": IC_WHITE,
            "borderBottom": f"1px solid {IC_GRAY}",
        },
    )

    chart_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "Kliento rezultatų dinamika pagal metus",
                        style={"fontWeight": 700, "color": IC_NAVY},
                    ),
                    dcc.RadioItems(
                        id="customer-chart-type",
                        options=[
                            {"label": "Linijinis", "value": "line"},
                            {"label": "Stulpelinis", "value": "bar"},
                        ],
                        value="line",
                        inline=True,
                        labelStyle={
                            "marginRight": "12px",
                            "fontWeight": 600,
                            "color": IC_NAVY,
                        },
                        inputStyle={"marginRight": "6px"},
                        style={"marginLeft": "auto"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "marginBottom": "12px",
                },
            ),
            dcc.Graph(
                id="customer-chart",
                config={"displaylogo": False},
                style={"height": f"{CHART_HEIGHT}px"},
            ),
        ],
        id="customer-chart-wrapper",
        style={
            "background": IC_WHITE,
            "border": f"1px solid {IC_GRAY}",
            "borderRadius": "10px",
            "padding": "16px",
            "margin": "16px",
        },
    )

    table_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "Mėnesinė suvestinė",
                        style={"fontWeight": 700, "color": IC_NAVY},
                    ),
                    html.Button(
                        "Eksportuoti į Excel",
                        id="customer-export",
                        n_clicks=0,
                        title="Eksportuoti į Excel",
                        style={
                            "marginLeft": "auto",
                            "background": IC_NAVY,
                            "color": IC_WHITE,
                            "border": "none",
                            "padding": "6px 14px",
                            "borderRadius": "6px",
                            "fontWeight": 600,
                            "cursor": "pointer",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "8px"},
            ),
            dash_table.DataTable(
                id="customer-table",
                columns=[],
                data=[],
                style_table={
                    "overflowX": "hidden",
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "minWidth": "100%",
                },
                markdown_options={"html": True},
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": 700,
                    "textAlign": "center",
                    "padding": "6px 8px",
                },
                style_cell={
                    "padding": "6px 10px",
                    "fontFamily": "Arial",
                    "fontSize": "13px",
                    "textAlign": "right",
                    "whiteSpace": "nowrap",
                },
                style_cell_conditional=[],
                fixed_columns={"headers": True, "data": 1},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
                    {
                        "if": {"filter_query": '{Mėnuo} = "suma"'},
                        "backgroundColor": "#FFF3CD",
                        "fontWeight": "700",
                    },
                    {"if": {"column_id": "Mėnuo"}, "textAlign": "left"},
                ],
            ),
            dcc.Download(id="customer-export-download"),
        ],
        id="customer-table-wrapper",
        style={
            "background": IC_WHITE,
            "border": f"1px solid {IC_GRAY}",
            "borderRadius": "10px",
            "padding": "16px",
            "margin": "0 16px 24px",
        },
    )

    empty_state = html.Div(
        id="customer-empty",
        children=EMPTY_MESSAGE,
        style={
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "height": "320px",
            "background": IC_WHITE,
            "margin": "16px",
            "border": f"1px dashed {IC_GRAY}",
            "borderRadius": "10px",
        },
    )

    category_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "Pardavimai pagal Kategorijos grupę",
                        style={"fontWeight": 700, "color": IC_NAVY},
                    ),
                    html.Div(
                        [
                            html.Label("Matas", style={"fontSize": "13px", "marginRight": "6px"}),
                            dcc.Dropdown(
                                options=[{"label": m, "value": m} for m in CUSTOMER_METRICS],
                                value="APYVARTA",
                                clearable=False,
                                id="customer-category-metric",
                                style={"minWidth": "150px"},
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Rodyti pokyčius",
                                        htmlFor="customer-category-show-changes",
                                        style={
                                            "fontSize": "12px",
                                            "marginRight": "6px",
                                            "color": IC_NAVY,
                                        },
                                    ),
                                    dcc.Checklist(
                                        options=[{"label": "", "value": "show"}],
                                        value=["show"],
                                        id="customer-category-show-changes",
                                        inputStyle={"marginRight": "0px"},
                                        style={"display": "flex", "alignItems": "center"},
                                        labelStyle={"display": "inline-flex"},
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                    "gap": "4px",
                                },
                            ),
                            html.Button(
                                "Eksportuoti į Excel",
                                id="customer-category-export",
                                n_clicks=0,
                                title="Eksportuoti į Excel",
                                style={
                                    "marginLeft": "12px",
                                    "background": IC_NAVY,
                                    "color": IC_WHITE,
                                    "border": "none",
                                    "padding": "6px 14px",
                                    "borderRadius": "6px",
                                    "fontWeight": 600,
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                        style={
                            "marginLeft": "auto",
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "6px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "marginBottom": "8px",
                },
            ),
            dash_table.DataTable(
                id="customer-category-table",
                columns=[],
                data=[],
                tooltip_data=[],
                tooltip_delay=0,
                tooltip_duration=None,
                style_table=dict(CATEGORY_TABLE_STYLE),
                style_cell=dict(CATEGORY_CELL_STYLE),
                style_cell_conditional=[dict(item) for item in CATEGORY_CELL_CONDITIONAL],
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": 700,
                    "textAlign": "center",
                    "padding": "6px 8px",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
                    {
                        "if": {"column_id": "Kategorijos grupe"},
                        "textAlign": "left",
                    },
                ],
                fixed_columns={"headers": True, "data": 1},
                markdown_options={"html": True},
            ),
            dcc.Download(id="customer-category-export-download"),
        ],
        id="customer-category-wrapper",
        style={
            "background": IC_WHITE,
            "border": f"1px solid {IC_GRAY}",
            "borderRadius": "10px",
            "padding": "16px",
            "margin": "0 16px 32px",
        },
    )

    category_detail_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        id="customer-category-detail-title",
                        style={"fontWeight": 700, "color": IC_NAVY},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Uždaryti",
                                id="customer-category-detail-close",
                                n_clicks=0,
                                style={
                                    "background": "transparent",
                                    "border": "none",
                                    "color": IC_RED,
                                    "cursor": "pointer",
                                    "fontWeight": 600,
                                },
                            ),
                            html.Button(
                                "Eksportuoti į Excel",
                                id="customer-category-detail-export",
                                n_clicks=0,
                                title="Eksportuoti į Excel",
                                style={
                                    "marginLeft": "12px",
                                    "background": IC_NAVY,
                                    "color": IC_WHITE,
                                    "border": "none",
                                    "padding": "6px 14px",
                                    "borderRadius": "6px",
                                    "fontWeight": 600,
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                        style={
                            "marginLeft": "auto",
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "6px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "marginBottom": "8px",
                },
            ),
            dash_table.DataTable(
                id="customer-category-detail-table",
                columns=[],
                data=[],
                tooltip_data=[],
                tooltip_delay=0,
                tooltip_duration=None,
                style_table=dict(CATEGORY_DETAIL_TABLE_STYLE),
                style_cell=dict(CATEGORY_DETAIL_CELL_STYLE),
                style_cell_conditional=[
                    dict(item) for item in CATEGORY_DETAIL_CELL_CONDITIONAL
                ],
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": 700,
                    "textAlign": "center",
                    "padding": "6px 8px",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
                    {"if": {"column_id": "Kategorija"}, "textAlign": "left"},
                ],
                fixed_columns={"headers": True, "data": 1},
                markdown_options={"html": True},
            ),
            dcc.Download(id="customer-category-detail-export-download"),
        ],
        id="customer-category-detail-wrapper",
        style={**CATEGORY_DETAIL_WRAPPER_STYLE, "display": "none"},
    )

    category_vendor_section = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        id="customer-category-vendor-title",
                        style={"fontWeight": 700, "color": IC_NAVY},
                    ),
                    html.Div(
                        html.Button(
                            "Uždaryti",
                            id="customer-category-vendor-close",
                            n_clicks=0,
                            style={
                                "background": "transparent",
                                "border": "none",
                                "color": IC_RED,
                                "cursor": "pointer",
                                "fontWeight": 600,
                            },
                        ),
                        style={
                            "marginLeft": "auto",
                            "display": "flex",
                            "alignItems": "center",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "marginBottom": "8px",
                },
            ),
            dash_table.DataTable(
                id="customer-category-vendor-table",
                columns=[],
                data=[],
                tooltip_data=[],
                tooltip_delay=0,
                tooltip_duration=None,
                style_table=dict(CATEGORY_VENDOR_TABLE_STYLE),
                style_cell=dict(CATEGORY_VENDOR_CELL_STYLE),
                style_cell_conditional=[
                    dict(item) for item in CATEGORY_VENDOR_CELL_CONDITIONAL
                ],
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": 700,
                    "textAlign": "center",
                    "padding": "6px 8px",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
                    {
                        "if": {"column_id": "Gamintojas (pavad)"},
                        "textAlign": "left",
                    },
                ],
                fixed_columns={"headers": True, "data": 1},
                markdown_options={"html": True},
            ),
        ],
        id="customer-category-vendor-wrapper",
        style={**CATEGORY_VENDOR_WRAPPER_STYLE, "display": "none"},
    )

    return html.Div(
        [
            filter_row,
            status_bar,
            empty_state,
            chart_section,
            table_section,
            category_section,
            category_detail_section,
            category_vendor_section,
            dcc.Store(id="customer-category-selected-group"),
            dcc.Store(id="customer-category-selected-category"),
        ],
        style={"background": IC_BG, "minHeight": "100vh"},
    )


def _format_table_value(metric: str, value):
    if value is None or pd.isna(value):
        return ""
    if metric in ("APYVARTA", "PAJAMOS"):
        return _fmt_eur(value)
    if metric == "KIEKIS":
        return _fmt_qty(value)
    return _fmt_pct(value)


def _calculate_yoy_percent(current, previous):
    if current is None or pd.isna(current):
        return None
    if previous is None or pd.isna(previous) or previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


def _format_yoy_percent(metric: str, value):
    if value is None or pd.isna(value):
        return "–"
    if metric == "MARŽA %":
        sign = "+" if value > 0 else ""
        return f"{sign}{float(value):.2f} p.p."
    sign = "+" if value > 0 else ""
    return f"{sign}{float(value):.2f} %"


def _format_yoy_diff(metric: str, value):
    if value is None or pd.isna(value):
        return "–"
    if metric in ("APYVARTA", "PAJAMOS"):
        return _fmt_eur(value)
    if metric == "KIEKIS":
        return _fmt_qty(value)
    if metric == "MARŽA %":
        return "–"
    sign = "+" if value > 0 else ""
    return f"{sign}{float(value):.2f} p.p."


def _get_yoy_color(yoy_value):
    if yoy_value is None or pd.isna(yoy_value):
        return IC_GRAY
    if yoy_value > 0:
        return GREEN
    if yoy_value < 0:
        return RED
    return IC_GRAY


def _yoy_background(yoy_value):
    if yoy_value is None or pd.isna(yoy_value):
        return YOY_NEUTRAL_BG, 0
    color = YOY_POS_BG if yoy_value > 0 else YOY_NEG_BG if yoy_value < 0 else YOY_NEUTRAL_BG
    width = min(abs(float(yoy_value)), 100.0)
    return color, width


def _build_cell_html(metric, value, yoy_pct, yoy_diff, has_baseline, is_latest):
    value_text = _format_table_value(metric, value)
    if not has_baseline or yoy_pct is None or pd.isna(yoy_pct):
        emphasize = "font-weight:700;" if is_latest else ""
        return (
            f"<div style='position:relative;padding:6px;display:flex;flex-direction:column;"
            f"align-items:flex-end;{emphasize}'>"
            f"<span>{value_text or '–'}</span>"
            "</div>"
        )

    pct_text = _format_yoy_percent(metric, yoy_pct)
    diff_text = _format_yoy_diff(metric, yoy_diff)
    yoy_color = _get_yoy_color(yoy_pct)
    bar_color, width = _yoy_background(yoy_pct)
    emphasize = "font-weight:700;" if is_latest else ""
    hover_title = (
        f"YoY: {pct_text} | Δ {diff_text}"
    )
    if diff_text == "–":
        hover_title = f"YoY: {pct_text}"

    bar_style = (
        "position:absolute;inset:4px;border-radius:8px;"
        f"background:linear-gradient(90deg,{bar_color} {width}%, rgba(0,0,0,0) {width}%);"
        + ("opacity:1;" if is_latest else "opacity:0.75;")
    )
    if yoy_pct < 0:
        bar_style = (
            "position:absolute;inset:4px;border-radius:8px;"
            f"background:linear-gradient(270deg,{bar_color} {width}%, rgba(0,0,0,0) {width}%);"
            + ("opacity:1;" if is_latest else "opacity:0.75;")
        )

    return (
        "<div style='position:relative;padding:4px 6px;border-radius:8px;"
        "overflow:hidden;min-height:48px;' title='"
        + hover_title
        + "'>"
        + f"<div style='{bar_style}'></div>"
        + "<div style='position:relative;display:flex;flex-direction:column;align-items:flex-end;"
        f"gap:2px;color:{IC_NAVY};{emphasize}'>"
        + f"<span>{value_text or '–'}</span>"
        + f"<span style='font-size:11px;color:{yoy_color};font-weight:600;'>"
        + f"{pct_text}"
        + (" | " + diff_text if diff_text != "–" else "")
        + "</span></div></div>"
    )


def _format_hover_yoy(metric, yoy_pct, yoy_diff):
    if yoy_pct is None or pd.isna(yoy_pct):
        return "–", IC_GRAY
    pct_text = _format_yoy_percent(metric, yoy_pct)
    diff_text = _format_yoy_diff(metric, yoy_diff)
    text = pct_text
    if diff_text != "–":
        text = f"{pct_text} | {diff_text}"
    return text, _get_yoy_color(yoy_pct)


def _format_period_label(period: Optional[Tuple[int, int]]) -> Optional[str]:
    if not period:
        return None
    year, month = period
    if year is None or month is None:
        return None
    try:
        month = int(month)
    except (TypeError, ValueError):
        return str(period)
    if 1 <= month <= 12:
        return f"{int(year)}-{month:02d}"
    return f"{int(year)}-{month}"


def _format_category_value(metric: str, value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    if metric in ("APYVARTA", "PAJAMOS"):
        text = _fmt_eur(value)
        return text if text != "-" else "—"
    if metric == "KIEKIS":
        text = _fmt_qty(value)
        return text if text != "-" else "—"
    if metric == "MARŽA %":
        return f"{float(value):.2f} %"
    return "—"


def _format_delta_percent(metric: str, value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    numeric = float(value)
    if metric == "MARŽA %":
        if abs(numeric) < 1e-9:
            return "0.00 p.p."
        sign = "+" if numeric > 0 else ""
        return f"{sign}{numeric:.2f} p.p."
    capped = max(min(numeric, 999.0), -999.0)
    if abs(capped) < 1e-9:
        return "0.00 %"
    sign = "+" if capped > 0 else ""
    return f"{sign}{capped:.2f} %"


def _format_delta_value(metric: str, value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    numeric = float(value)
    if metric in ("APYVARTA", "PAJAMOS"):
        formatted = _fmt_eur(numeric)
        if numeric > 0:
            return "+" + formatted
        return formatted
    if metric == "KIEKIS":
        formatted = _fmt_qty(numeric)
        if numeric > 0:
            return "+" + formatted
        return formatted
    if metric == "MARŽA %":
        if abs(numeric) < 1e-9:
            return "0.00 p.p."
        sign = "+" if numeric > 0 else ""
        return f"{sign}{numeric:.2f} p.p."
    return "—"


def _delta_arrow(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    if abs(float(value)) < 1e-9:
        return "—"
    return "↑" if float(value) > 0 else "↓"


def _delta_color(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return BADGE_TEXT_NEUTRAL
    if float(value) > 0:
        return GREEN
    if float(value) < 0:
        return RED
    return BADGE_TEXT_NEUTRAL


def _delta_background(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return BADGE_NEUTRAL_BG
    numeric = float(value)
    if numeric > 0:
        return BADGE_POS_BG
    if numeric < 0:
        return BADGE_NEG_BG
    return BADGE_NEUTRAL_BG


def _format_window_range(periods: Optional[Iterable[Tuple[int, int]]]) -> Optional[str]:
    if not periods:
        return None
    ordered = sorted({(int(y), int(m)) for y, m in periods})
    if not ordered:
        return None
    start_year, start_month = ordered[0]
    end_year, end_month = ordered[-1]
    if len(ordered) == 1:
        return f"{start_year}-{start_month:02d}"
    return f"{start_year}-{start_month:02d}..{end_year}-{end_month:02d}"


def _compute_delta(metric: str, current: Optional[float], baseline: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if current is None or pd.isna(current):
        return None, None
    if baseline is None or pd.isna(baseline):
        return None, None
    if metric == "MARŽA %":
        diff = float(current) - float(baseline)
        return diff, diff
    if abs(float(baseline)) < 1e-9:
        return None, None
    diff = float(current) - float(baseline)
    pct = (diff / float(baseline)) * 100.0
    return pct, diff


def _build_change_badge(
    metric: str,
    pct_value: Optional[float],
    diff_value: Optional[float],
    label: str,
    tooltip: Optional[str],
) -> str:
    safe_label = escape(label)
    tooltip_attr = f" title='{escape(tooltip)}'" if tooltip else ""

    reference_value = diff_value if diff_value is not None and not pd.isna(diff_value) else pct_value
    if reference_value is None or pd.isna(reference_value):
        return (
            "<span style='display:inline-flex;align-items:center;padding:2px 6px;border-radius:8px;"
            f"background:{BADGE_NEUTRAL_BG};color:{BADGE_TEXT_NEUTRAL};font-size:11px;font-weight:500;' {tooltip_attr}>"
            f"Δ {safe_label}: —"
            "</span>"
        )

    color = _delta_color(reference_value)
    background = _delta_background(reference_value)
    arrow = _delta_arrow(reference_value)

    if metric == "MARŽA %":
        pct_text = _format_delta_percent(metric, diff_value)
        diff_part = ""
    else:
        pct_text = _format_delta_percent(metric, pct_value)
        diff_text = _format_delta_value(metric, diff_value)
        diff_part = f" | {escape(diff_text)}" if diff_text != "—" else ""

    if pct_text == "—" and not diff_part:
        return (
            "<span style='display:inline-flex;align-items:center;padding:2px 6px;border-radius:8px;"
            f"background:{BADGE_NEUTRAL_BG};color:{BADGE_TEXT_NEUTRAL};font-size:11px;font-weight:500;' {tooltip_attr}>"
            f"Δ {safe_label}: —"
            "</span>"
        )

    badge_text = f"Δ {safe_label}: {arrow} {escape(pct_text)}{diff_part}"
    return (
        "<span style='display:inline-flex;align-items:center;padding:2px 6px;border-radius:8px;gap:4px;"
        f"background:{background};color:{color};font-size:11px;font-weight:600;' {tooltip_attr}>"
        + badge_text
        + "</span>"
    )


def _build_category_last_cell(
    metric: str,
    last_value: Optional[float],
    previous_value: Optional[float],
    show_changes: bool,
    tooltip_prev: Optional[str],
) -> str:
    base_text = _format_category_value(metric, last_value)
    if not show_changes:
        return (
            "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:4px;'>"
            f"<span style='font-weight:700;color:{IC_NAVY};'>{base_text}</span>"
            "</div>"
        )

    pct_prev, diff_prev = _compute_delta(metric, last_value, previous_value)
    badge_html = _build_change_badge(metric, pct_prev, diff_prev, "M/M-1", tooltip_prev)
    return (
        "<div style='position:relative;padding:4px 0 2px;display:flex;flex-direction:column;"
        "align-items:flex-end;gap:6px;'>"
        f"<span style='font-weight:700;color:{IC_NAVY};'>{base_text}</span>"
        "<div style='display:flex;flex-wrap:wrap;gap:4px;justify-content:flex-end;'>"
        + badge_html
        + "</div></div>"
    )


def _build_category_avg3_cell(
    metric: str,
    avg3_value: Optional[float],
    avg6_value: Optional[float],
    show_changes: bool,
    tooltip_avg: Optional[str],
) -> str:
    base_text = _format_category_value(metric, avg3_value)
    if not show_changes:
        return (
            "<div style='display:flex;flex-direction:column;align-items:flex-end;gap:4px;'>"
            f"<span style='font-weight:700;color:{IC_NAVY};'>{base_text}</span>"
            "</div>"
        )

    pct_vs6, diff_vs6 = _compute_delta(metric, avg3_value, avg6_value)
    badge_html = _build_change_badge(metric, pct_vs6, diff_vs6, "vs 6m", tooltip_avg)
    return (
        "<div style='position:relative;padding:4px 0 2px;display:flex;flex-direction:column;"
        "align-items:flex-end;gap:6px;'>"
        f"<span style='font-weight:700;color:{IC_NAVY};'>{base_text}</span>"
        "<div style='display:flex;flex-wrap:wrap;gap:4px;justify-content:flex-end;'>"
        + badge_html
        + "</div></div>"
    )

def _build_status_text(managers, clients, codes, years, metric):
    def join_values(values):
        if not values:
            return "Visi"
        if isinstance(values, str):
            return values
        if len(values) > 3:
            return ", ".join(list(values)[:2]) + " …"
        return ", ".join(values)

    return (
        f"Vadybininkas: {join_values(managers)} | "
        f"Klientas: {join_values(clients)} | "
        f"Kodas: {join_values(codes)} | "
        f"Metai: {join_values([str(y) for y in years] if years else [])} | "
        f"Matas: {metric}"
    )


@callback(
    Output("customer-client", "options"),
    Input("customer-manager", "value"),
)
def update_clients(managers):
    df = FILTER_FRAME
    if managers:
        df = df[df["Vadybininkas"].isin(managers)]
    options = sorted(df["Klientas"].dropna().unique().tolist())
    return [{"label": c, "value": c} for c in options]


@callback(
    Output("customer-code", "options"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
)
def update_codes(managers, clients):
    df = FILTER_FRAME
    if managers:
        df = df[df["Vadybininkas"].isin(managers)]
    if clients:
        selected = clients if isinstance(clients, list) else [clients]
        df = df[df["Klientas"].isin(selected)]
    options = sorted(df["Kliento kodas"].dropna().unique().tolist())
    return [{"label": c, "value": c} for c in options]


@callback(
    Output("customer-manager", "value"),
    Output("customer-client", "value"),
    Output("customer-code", "value"),
    Output("customer-years", "value"),
    Output("customer-metric", "value"),
    Output("customer-category-metric", "value"),
    Input("customer-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(n_clicks):
    return [], [], [], DEFAULT_YEARS, "APYVARTA", "APYVARTA"


@callback(
    Output("customer-chart", "figure"),
    Output("customer-table", "columns"),
    Output("customer-table", "data"),
    Output("customer-table", "style_table"),
    Output("customer-table", "style_cell"),
    Output("customer-table", "style_cell_conditional"),
    Output("customer-empty", "children"),
    Output("customer-empty", "style"),
    Output("customer-chart-wrapper", "style"),
    Output("customer-table-wrapper", "style"),
    Output("customer-category-wrapper", "style"),
    Output("customer-status-text", "children"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-years", "value"),
    Input("customer-metric", "value"),
    Input("customer-chart-type", "value"),
)
def update_customer_view(managers, clients, codes, years, metric, chart_type):
    status_text = _build_status_text(managers, clients, codes, years, metric)
    empty_children = EMPTY_MESSAGE
    empty_style = {
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "height": "320px",
        "background": IC_WHITE,
        "margin": "16px",
        "border": f"1px dashed {IC_GRAY}",
        "borderRadius": "10px",
    }
    hidden = {"display": "none"}
    chart_style = {
        "background": IC_WHITE,
        "border": f"1px solid {IC_GRAY}",
        "borderRadius": "10px",
        "padding": "16px",
        "margin": "16px",
    }
    table_style = {
        "background": IC_WHITE,
        "border": f"1px solid {IC_GRAY}",
        "borderRadius": "10px",
        "padding": "16px",
        "margin": "0 16px 24px",
    }
    category_style = {
        "background": IC_WHITE,
        "border": f"1px solid {IC_GRAY}",
        "borderRadius": "10px",
        "padding": "16px",
        "margin": "0 16px 32px",
    }

    table_style_props = dict(BASE_TABLE_STYLE)
    cell_style = dict(BASE_CELL_STYLE)
    cell_conditional = [dict(item) for item in BASE_CELL_CONDITIONAL]

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return (
            go.Figure(),
            [],
            [],
            table_style_props,
            cell_style,
            cell_conditional,
            empty_children,
            empty_style,
            hidden,
            hidden,
            hidden,
            status_text,
        )

    chart_type = chart_type or "line"

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    aggregated, _ = compute_customer_monthly_aggregation(filters, metric)
    if aggregated.empty:
        return (
            go.Figure(),
            [],
            [],
            table_style_props,
            cell_style,
            cell_conditional,
            NO_DATA_MESSAGE,
            empty_style,
            hidden,
            hidden,
            hidden,
            status_text,
        )

    metric_col = METRIC_COLUMN_MAP[metric]
    aggregated = aggregated.sort_values(["Mėnuo", "Metai"], kind="mergesort")
    years_sorted = sorted(aggregated["Metai"].unique())
    latest_year = max(years_sorted)
    years_set = set(years_sorted)

    months_by_year = {year: set() for year in years_sorted}
    month_values = {year: {} for year in years_sorted}
    turnover_map = {year: {} for year in years_sorted}
    profit_map = {year: {} for year in years_sorted}

    for _, row in aggregated.iterrows():
        year = int(row["Metai"])
        month = int(row["Mėnuo"])
        months_by_year.setdefault(year, set()).add(month)

        raw_value = row[metric_col]
        if pd.isna(raw_value):
            raw_value = None
        else:
            raw_value = float(raw_value)
        month_values.setdefault(year, {})[month] = raw_value

        turnover_map.setdefault(year, {})[month] = float(row["Apyvarta"]) if not pd.isna(row["Apyvarta"]) else 0.0
        profit_map.setdefault(year, {})[month] = float(row["Pajamos"]) if not pd.isna(row["Pajamos"]) else 0.0

    month_range = list(range(1, 13))
    tickvals = month_range
    ticktext = [MENUO_LABELS_LT[i - 1] if 1 <= i <= 12 else str(i) for i in month_range]

    yoy_percent_map = {year: {} for year in years_sorted}
    yoy_diff_map = {year: {} for year in years_sorted}
    for year in years_sorted:
        prev_year = year - 1
        if prev_year not in years_set:
            continue
        comparable_months = months_by_year.get(year, set()) & months_by_year.get(prev_year, set())
        for month in comparable_months:
            current_val = month_values.get(year, {}).get(month)
            prev_val = month_values.get(prev_year, {}).get(month)
            if metric == "MARŽA %":
                if current_val is None or prev_val is None:
                    continue
                diff_val = current_val - prev_val
                yoy_percent_map[year][month] = diff_val
                yoy_diff_map[year][month] = diff_val
            else:
                if current_val is None or prev_val is None:
                    continue
                yoy_pct = _calculate_yoy_percent(current_val, prev_val)
                if yoy_pct is None:
                    continue
                yoy_percent_map[year][month] = yoy_pct
                yoy_diff_map[year][month] = current_val - prev_val

    fig = go.Figure()
    for year in years_sorted:
        df_year = aggregated[aggregated["Metai"] == year].sort_values("Mėnuo")
        color = IC_RED if year == latest_year else CUSTOMER_COLORWAY.get(year, IC_GRAY)
        month_numbers = df_year["Mėnuo"].astype(int).tolist()
        month_labels = [
            MENUO_LABELS_LT[int(m) - 1] if isinstance(m, (int, float)) and 1 <= int(m) <= 12 else str(m)
            for m in month_numbers
        ]
        formatted_values = [_format_table_value(metric, v) for v in df_year[metric_col]]

        if year == latest_year:
            customdata = []
            for m, label, fval in zip(month_numbers, month_labels, formatted_values):
                yoy_pct = yoy_percent_map.get(year, {}).get(int(m))
                yoy_diff = yoy_diff_map.get(year, {}).get(int(m))
                yoy_text, yoy_color = _format_hover_yoy(metric, yoy_pct, yoy_diff)
                customdata.append((label, fval, yoy_text, yoy_color))
            hovertemplate = (
                "Mėnuo %{customdata[0]}<br>Metai %{name}<br>Reikšmė %{customdata[1]}"
                "<br><span style='color:%{customdata[3]};'>YoY %{customdata[2]}</span><extra></extra>"
            )
        else:
            customdata = list(zip(month_labels, formatted_values))
            hovertemplate = (
                "Mėnuo %{customdata[0]}<br>Metai %{name}<br>Reikšmė %{customdata[1]}<extra></extra>"
            )

        if chart_type == "bar":
            fig.add_trace(
                go.Bar(
                    x=month_numbers,
                    y=df_year[metric_col].tolist(),
                    name=str(year),
                    marker={
                        "color": color,
                        "opacity": 0.92 if year == latest_year else 0.75,
                        "line": {"color": color, "width": 1.4 if year == latest_year else 0.6},
                    },
                    hovertemplate=hovertemplate,
                    customdata=customdata,
                    offsetgroup=str(year),
                    legendgroup=str(year),
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=month_numbers,
                    y=df_year[metric_col].tolist(),
                    mode="lines+markers",
                    name=str(year),
                    line={"color": color, "width": 4 if year == latest_year else 2},
                    marker={"size": 9 if year == latest_year else 6},
                    hovertemplate=hovertemplate,
                    customdata=customdata,
                    legendgroup=str(year),
                )
            )

    fig.update_layout(
        height=CHART_HEIGHT,
        margin=dict(l=30, r=20, t=30, b=40),
        plot_bgcolor=IC_WHITE,
        paper_bgcolor=IC_WHITE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            title="Mėnuo",
            gridcolor="#E5E5E5",
        ),
        yaxis=dict(
            title=metric,
            gridcolor="#E5E5E5",
            rangemode="tozero",
        ),
        hovermode="x unified" if chart_type == "line" else "x",
        transition_duration=300,
    )
    if chart_type == "bar":
        fig.update_layout(barmode="group", bargap=0.2)

    columns = [{"name": "Mėnuo", "id": "Mėnuo"}]
    columns_order = ["Mėnuo"]

    month_rows_numeric = []
    for month in month_range:
        row = {"Mėnuo": str(month)}
        for year in years_sorted:
            year_key = str(year)
            raw_value = month_values.get(year, {}).get(month)
            if raw_value is None:
                row[year_key] = 0.0 if metric != "MARŽA %" else 0.0
            else:
                row[year_key] = raw_value
        month_rows_numeric.append(row)

    sum_row = {"Mėnuo": "suma"}
    yoy_total_percent = {}
    yoy_total_diff = {}
    for year in years_sorted:
        year_key = str(year)
        months_curr = months_by_year.get(year, set())
        if metric == "MARŽA %":
            turnover_total = sum(turnover_map.get(year, {}).get(m, 0.0) for m in months_curr)
            profit_total = sum(profit_map.get(year, {}).get(m, 0.0) for m in months_curr)
            total_value = (profit_total / turnover_total * 100.0) if turnover_total else None
        else:
            total_value = sum(
                (month_values.get(year, {}).get(m) if month_values.get(year, {}).get(m) is not None else 0.0)
                for m in months_curr
            )
        sum_row[year_key] = total_value if total_value is not None else 0.0

        prev_year = year - 1
        has_baseline = prev_year in years_set
        yoy_total = None
        yoy_diff_total = None
        if has_baseline:
            comparable_months = months_by_year.get(year, set()) & months_by_year.get(prev_year, set())
            if comparable_months:
                if metric == "MARŽA %":
                    curr_turnover = sum(turnover_map.get(year, {}).get(m, 0.0) for m in comparable_months)
                    curr_profit = sum(profit_map.get(year, {}).get(m, 0.0) for m in comparable_months)
                    prev_turnover = sum(turnover_map.get(prev_year, {}).get(m, 0.0) for m in comparable_months)
                    prev_profit = sum(profit_map.get(prev_year, {}).get(m, 0.0) for m in comparable_months)
                    curr_metric = (curr_profit / curr_turnover * 100.0) if curr_turnover else None
                    prev_metric = (prev_profit / prev_turnover * 100.0) if prev_turnover else None
                    if curr_metric is not None and prev_metric is not None:
                        yoy_total = curr_metric - prev_metric
                        yoy_diff_total = curr_metric - prev_metric
                else:
                    curr_metric = sum(
                        (month_values.get(year, {}).get(m) if month_values.get(year, {}).get(m) is not None else 0.0)
                        for m in comparable_months
                    )
                    prev_metric = sum(
                        (month_values.get(prev_year, {}).get(m) if month_values.get(prev_year, {}).get(m) is not None else 0.0)
                        for m in comparable_months
                    )
                    yoy_total = _calculate_yoy_percent(curr_metric, prev_metric)
                    if yoy_total is not None:
                        yoy_diff_total = curr_metric - prev_metric
        yoy_total_percent[year] = yoy_total
        yoy_total_diff[year] = yoy_diff_total

    numeric_rows = month_rows_numeric + [sum_row]

    for year in years_sorted:
        year_key = str(year)
        columns.append({"name": str(year), "id": year_key, "presentation": "markdown"})
        columns_order.append(year_key)

    data_formatted = []
    for row in numeric_rows:
        formatted = {}
        is_total = row["Mėnuo"] == "suma"
        formatted["Mėnuo"] = row["Mėnuo"]
        for year in years_sorted:
            year_key = str(year)
            has_baseline = (year - 1) in years_set
            is_latest = year == latest_year
            if is_total:
                yoy_pct = yoy_total_percent.get(year)
                yoy_diff = yoy_total_diff.get(year)
            else:
                month_idx = int(row["Mėnuo"])
                yoy_pct = yoy_percent_map.get(year, {}).get(month_idx)
                yoy_diff = yoy_diff_map.get(year, {}).get(month_idx)
            value = row.get(year_key)
            formatted[year_key] = _build_cell_html(metric, value, yoy_pct, yoy_diff, has_baseline, is_latest)
        data_formatted.append(formatted)

    years_count = len(years_sorted)
    table_style_props["overflowX"] = "auto" if years_count > 4 else "hidden"
    cell_style["padding"] = "6px 10px" if years_count <= 4 else "4px 6px"

    numeric_columns = [cid for cid in columns_order if cid != "Mėnuo"]
    if years_count >= 5:
        numeric_width = "140px"
    elif years_count == 4:
        numeric_width = "130px"
    elif years_count == 3:
        numeric_width = "120px"
    else:
        numeric_width = "110px"

    cell_conditional = [dict(item) for item in BASE_CELL_CONDITIONAL]
    for col_id in numeric_columns:
        cell_conditional.append(
            {
                "if": {"column_id": col_id},
                "minWidth": numeric_width,
                "width": numeric_width,
                "maxWidth": numeric_width,
            }
        )
    cell_conditional.append(
        {
            "if": {"column_id": str(latest_year)},
            "fontWeight": "700",
        }
    )

    month_width = 110
    numeric_px = int(numeric_width.replace("px", "")) if numeric_width.endswith("px") else 120
    total_px = month_width + numeric_px * len(numeric_columns)
    table_style_props["minWidth"] = f"{total_px + 40}px" if years_count > 4 else "100%"

    return (
        fig,
        columns,
        data_formatted,
        table_style_props,
        cell_style,
        cell_conditional,
        empty_children,
        hidden,
        chart_style,
        table_style,
        category_style,
        status_text,
    )


@callback(
    Output("customer-export-download", "data"),
    Input("customer-export", "n_clicks"),
    State("customer-manager", "value"),
    State("customer-client", "value"),
    State("customer-code", "value"),
    State("customer-years", "value"),
    State("customer-metric", "value"),
    prevent_initial_call=True,
)
def export_customer_data(n_clicks, managers, clients, codes, years, metric):
    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return dash.no_update

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    aggregated, _ = compute_customer_monthly_aggregation(filters, metric)
    if aggregated.empty:
        return dash.no_update

    metric_col = METRIC_COLUMN_MAP[metric]
    pivot = aggregated.pivot_table(
        index="Mėnuo",
        columns="Metai",
        values=metric_col,
        aggfunc="sum",
        sort=False,
    )
    pivot.index = pivot.index.astype(int)
    pivot = pivot.reindex(range(1, 13)).fillna(0.0)

    totals = {}
    years_sorted = sorted(pivot.columns.tolist())
    for year in years_sorted:
        if metric == "MARŽA %":
            subset = aggregated[aggregated["Metai"] == year]
            turnover = subset["Apyvarta"].sum()
            profit = subset["Pajamos"].sum()
            totals[year] = (profit / turnover * 100.0) if turnover else None
        else:
            totals[year] = aggregated.loc[aggregated["Metai"] == year, metric_col].sum()

    export_df = pivot.copy()
    export_df.insert(0, "Mėnuo", export_df.index.astype(int))
    export_df = export_df.rename(columns={year: str(year) for year in years_sorted})
    sum_row = {"Mėnuo": "suma"}
    for year in years_sorted:
        sum_row[str(year)] = totals[year]
    export_df = pd.concat([export_df, pd.DataFrame([sum_row])], ignore_index=True)

    client_name = selected_clients[0].replace(" ", "_")
    filename = f"kliento_apzvalga_{client_name}_{metric}.xlsx"
    return dcc.send_data_frame(export_df.to_excel, filename, index=False)


@callback(
    Output("customer-category-table", "columns"),
    Output("customer-category-table", "data"),
    Output("customer-category-table", "tooltip_data"),
    Output("customer-category-table", "style_table"),
    Output("customer-category-table", "style_cell"),
    Output("customer-category-table", "style_cell_conditional"),
    Output("customer-category-table", "style_data_conditional"),
    Input("customer-category-metric", "value"),
    Input("customer-category-show-changes", "value"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-years", "value"),
    State("customer-category-selected-group", "data"),
)
def update_category_table(
    metric, show_changes_value, managers, clients, codes, years, selected_group
):
    metric = metric or "APYVARTA"
    show_changes = bool(show_changes_value and "show" in show_changes_value)
    table_style = dict(CATEGORY_TABLE_STYLE)
    cell_style = dict(CATEGORY_CELL_STYLE)
    cell_conditional = [dict(item) for item in CATEGORY_CELL_CONDITIONAL]
    data_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
        {"if": {"column_id": "Kategorijos grupe"}, "textAlign": "left"},
    ]

    for col_id in ["previous_value", "avg_3m", "avg_6m"]:
        width_conf = {
            "if": {"column_id": col_id},
            "minWidth": "140px",
            "width": "140px",
            "maxWidth": "160px",
        }
        if col_id == "avg_3m" and show_changes:
            width_conf.update({"minWidth": "200px", "width": "220px", "maxWidth": "260px"})
        cell_conditional.append(width_conf)
        data_conditional.append(
            {
                "if": {"filter_query": f'{{{col_id}}} = "—"', "column_id": col_id},
                "color": "#6c757d",
            }
        )

    last_column_style = {
        "if": {"column_id": "last_value"},
        "minWidth": "220px",
        "width": "240px",
        "maxWidth": "320px",
        "whiteSpace": "normal",
    }
    if not show_changes:
        last_column_style.update(
            {
                "minWidth": "160px",
                "width": "180px",
                "maxWidth": "220px",
                "whiteSpace": "nowrap",
            }
        )
    cell_conditional.append(last_column_style)

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return [], [], [], table_style, cell_style, cell_conditional, data_conditional

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    frame, metadata = compute_customer_category_group_summary(filters, metric)
    if frame.empty:
        return [], [], [], table_style, cell_style, cell_conditional, data_conditional

    last_label = _format_period_label(metadata.get("last_period"))
    prev_label = _format_period_label(metadata.get("previous_period"))
    window3_label = _format_window_range(metadata.get("window3_periods"))
    window6_label = _format_window_range(metadata.get("window6_periods"))

    tooltip_prev = None
    if last_label and prev_label:
        tooltip_prev = f"{last_label} vs {prev_label} (MoM)"
    tooltip_avg = None
    if window3_label and window6_label:
        tooltip_avg = f"Avg3 ({window3_label}) vs Avg6 ({window6_label})"

    columns = [
        {"name": "Kategorijos grupe", "id": "Kategorijos grupe"},
        {
            "name": "Paskutinis mėnuo" + (f" ({last_label})" if last_label else ""),
            "id": "last_value",
            "presentation": "markdown",
        },
        {
            "name": "Ankstesnis mėnuo" + (f" ({prev_label})" if prev_label else ""),
            "id": "previous_value",
        },
        {
            "name": "Vidurkis 3 mėn.",
            "id": "avg_3m",
            "presentation": "markdown",
        },
        {"name": "Vidurkis 6 mėn.", "id": "avg_6m"},
    ]

    formatted: List[Dict[str, Any]] = []
    tooltip_rows: List[Dict[str, Any]] = []
    highlighted_index: Optional[int] = None
    for idx, row in enumerate(frame.to_dict("records")):
        last_value = row.get("last_value")
        prev_value = row.get("previous_value")
        avg3_value = row.get("avg_3m")
        avg6_value = row.get("avg_6m")
        group_name = row.get("Kategorijos grupe")
        if selected_group and group_name == selected_group and highlighted_index is None:
            highlighted_index = idx
        formatted.append(
            {
                "Kategorijos grupe": group_name,
                "last_value": _build_category_last_cell(
                    metric,
                    last_value,
                    prev_value,
                    show_changes,
                    tooltip_prev,
                ),
                "previous_value": _format_category_value(metric, prev_value),
                "avg_3m": _build_category_avg3_cell(
                    metric,
                    avg3_value,
                    avg6_value,
                    show_changes,
                    tooltip_avg,
                ),
                "avg_6m": _format_category_value(metric, row.get("avg_6m")),
            }
        )
        tooltip_rows.append(
            {
                "last_value": (tooltip_prev or "") if show_changes else "",
                "avg_3m": (tooltip_avg or "") if show_changes else "",
            }
        )

    if highlighted_index is not None:
        data_conditional.append(
            {
                "if": {"row_index": highlighted_index},
                "backgroundColor": "rgba(227, 6, 19, 0.08)",
            }
        )
        data_conditional.append(
            {
                "if": {"row_index": highlighted_index},
                "borderLeft": f"4px solid {IC_RED}",
            }
        )

    return (
        columns,
        formatted,
        tooltip_rows,
        table_style,
        cell_style,
        cell_conditional,
        data_conditional,
    )


@callback(
    Output("customer-category-selected-group", "data"),
    Output("customer-category-detail-wrapper", "style"),
    Output("customer-category-detail-title", "children"),
    Output("customer-category-detail-table", "columns"),
    Output("customer-category-detail-table", "data"),
    Output("customer-category-detail-table", "tooltip_data"),
    Output("customer-category-detail-table", "style_table"),
    Output("customer-category-detail-table", "style_cell"),
    Output("customer-category-detail-table", "style_cell_conditional"),
    Output("customer-category-detail-table", "style_data_conditional"),
    Input("customer-category-table", "active_cell"),
    Input("customer-category-detail-close", "n_clicks"),
    Input("customer-category-metric", "value"),
    Input("customer-category-show-changes", "value"),
    Input("customer-category-selected-category", "data"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-years", "value"),
    State("customer-category-table", "data"),
    State("customer-category-selected-group", "data"),
)
def update_category_detail(
    active_cell,
    close_clicks,
    metric,
    show_changes_value,
    selected_category,
    managers,
    clients,
    codes,
    years,
    table_data,
    stored_selection,
):
    metric = metric or "APYVARTA"
    show_changes = bool(show_changes_value and "show" in show_changes_value)

    table_style = dict(CATEGORY_DETAIL_TABLE_STYLE)
    cell_style = dict(CATEGORY_DETAIL_CELL_STYLE)
    cell_conditional = [dict(item) for item in CATEGORY_DETAIL_CELL_CONDITIONAL]
    data_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
        {"if": {"column_id": "Kategorija"}, "textAlign": "left"},
    ]

    for col_id in ["previous_value", "avg_3m", "avg_6m"]:
        width_conf = {
            "if": {"column_id": col_id},
            "minWidth": "140px",
            "width": "140px",
            "maxWidth": "160px",
        }
        if col_id == "avg_3m" and show_changes:
            width_conf.update({"minWidth": "200px", "width": "220px", "maxWidth": "260px"})
        cell_conditional.append(width_conf)
        data_conditional.append(
            {
                "if": {"filter_query": f'{{{col_id}}} = "—"', "column_id": col_id},
                "color": "#6c757d",
            }
        )

    last_column_style = {
        "if": {"column_id": "last_value"},
        "minWidth": "220px",
        "width": "240px",
        "maxWidth": "320px",
        "whiteSpace": "normal",
    }
    if not show_changes:
        last_column_style.update(
            {
                "minWidth": "160px",
                "width": "180px",
                "maxWidth": "220px",
                "whiteSpace": "nowrap",
            }
        )
    cell_conditional.append(last_column_style)

    wrapper_style = dict(CATEGORY_DETAIL_WRAPPER_STYLE)
    wrapper_style["display"] = "none"
    title = ""
    columns: List[Dict[str, Any]] = []
    data_rows: List[Dict[str, Any]] = []
    tooltip_rows: List[Dict[str, Any]] = []

    table_rows = table_data or []
    available_groups = {
        row.get("Kategorijos grupe")
        for row in table_rows
        if isinstance(row, dict) and row.get("Kategorijos grupe")
    }

    ctx = dash.callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    selection = stored_selection or None
    if triggered == "customer-category-detail-close.n_clicks":
        selection = None
    elif triggered == "customer-category-table.active_cell":
        selection = None
        if active_cell and isinstance(active_cell, dict):
            row_idx = active_cell.get("row")
            if isinstance(row_idx, int) and 0 <= row_idx < len(table_rows):
                candidate = table_rows[row_idx].get("Kategorijos grupe")
                if candidate:
                    selection = candidate

    if selection and selection not in available_groups:
        selection = None

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1 or not selection:
        return (
            selection,
            wrapper_style,
            title,
            columns,
            data_rows,
            tooltip_rows,
            table_style,
            cell_style,
            cell_conditional,
            data_conditional,
        )

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    frame, metadata = compute_customer_category_detail_summary(filters, metric, selection)
    if frame.empty:
        return (
            None,
            wrapper_style,
            title,
            columns,
            data_rows,
            tooltip_rows,
            table_style,
            cell_style,
            cell_conditional,
            data_conditional,
        )

    last_label = _format_period_label(metadata.get("last_period"))
    prev_label = _format_period_label(metadata.get("previous_period"))
    window3_label = _format_window_range(metadata.get("window3_periods"))
    window6_label = _format_window_range(metadata.get("window6_periods"))

    tooltip_prev = None
    if last_label and prev_label:
        tooltip_prev = f"{last_label} vs {prev_label} (MoM)"
    tooltip_avg = None
    if window3_label and window6_label:
        tooltip_avg = f"Avg3 ({window3_label}) vs Avg6 ({window6_label})"

    columns = [
        {"name": "Kategorija", "id": "Kategorija"},
        {
            "name": "Paskutinis mėnuo" + (f" ({last_label})" if last_label else ""),
            "id": "last_value",
            "presentation": "markdown",
        },
        {
            "name": "Ankstesnis mėnuo" + (f" ({prev_label})" if prev_label else ""),
            "id": "previous_value",
        },
        {
            "name": "Vidurkis 3 mėn.",
            "id": "avg_3m",
            "presentation": "markdown",
        },
        {"name": "Vidurkis 6 mėn.", "id": "avg_6m"},
    ]

    highlight_index: Optional[int] = None
    records = frame.to_dict("records")
    for idx, row in enumerate(records):
        last_value = row.get("last_value")
        prev_value = row.get("previous_value")
        avg3_value = row.get("avg_3m")
        avg6_value = row.get("avg_6m")
        category_name = row.get("Kategorija")
        if (
            selected_category
            and isinstance(selected_category, str)
            and category_name == selected_category
            and highlight_index is None
        ):
            highlight_index = idx
        data_rows.append(
            {
                "Kategorija": category_name,
                "last_value": _build_category_last_cell(
                    metric,
                    last_value,
                    prev_value,
                    show_changes,
                    tooltip_prev,
                ),
                "previous_value": _format_category_value(metric, prev_value),
                "avg_3m": _build_category_avg3_cell(
                    metric,
                    avg3_value,
                    avg6_value,
                    show_changes,
                    tooltip_avg,
                ),
                "avg_6m": _format_category_value(metric, avg6_value),
            }
        )
        tooltip_rows.append(
            {
                "last_value": (tooltip_prev or "") if show_changes else "",
                "avg_3m": (tooltip_avg or "") if show_changes else "",
            }
        )

    if highlight_index is not None:
        data_conditional.append(
            {
                "if": {"row_index": highlight_index},
                "backgroundColor": "rgba(227, 6, 19, 0.08)",
            }
        )
        data_conditional.append(
            {
                "if": {"row_index": highlight_index},
                "borderLeft": f"4px solid {IC_RED}",
            }
        )

    wrapper_style["display"] = "block"
    title = f"Kategorijos (grupė: {selection})"

    return (
        selection,
        wrapper_style,
        title,
        columns,
        data_rows,
        tooltip_rows,
        table_style,
        cell_style,
        cell_conditional,
        data_conditional,
    )


@callback(
    Output("customer-category-selected-category", "data"),
    Output("customer-category-vendor-wrapper", "style"),
    Output("customer-category-vendor-title", "children"),
    Output("customer-category-vendor-table", "columns"),
    Output("customer-category-vendor-table", "data"),
    Output("customer-category-vendor-table", "tooltip_data"),
    Output("customer-category-vendor-table", "style_table"),
    Output("customer-category-vendor-table", "style_cell"),
    Output("customer-category-vendor-table", "style_cell_conditional"),
    Output("customer-category-vendor-table", "style_data_conditional"),
    Input("customer-category-detail-table", "active_cell"),
    Input("customer-category-vendor-close", "n_clicks"),
    Input("customer-category-detail-close", "n_clicks"),
    Input("customer-category-metric", "value"),
    Input("customer-category-show-changes", "value"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-years", "value"),
    Input("customer-category-selected-group", "data"),
    State("customer-category-detail-table", "data"),
    State("customer-category-selected-category", "data"),
)
def update_category_vendor(
    active_cell,
    close_clicks,
    detail_close_clicks,
    metric,
    show_changes_value,
    managers,
    clients,
    codes,
    years,
    selected_group,
    table_data,
    stored_category,
):
    metric = metric or "APYVARTA"
    show_changes = bool(show_changes_value and "show" in show_changes_value)

    table_style = dict(CATEGORY_VENDOR_TABLE_STYLE)
    cell_style = dict(CATEGORY_VENDOR_CELL_STYLE)
    cell_conditional = [dict(item) for item in CATEGORY_VENDOR_CELL_CONDITIONAL]
    data_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#F7F9FC"},
        {"if": {"column_id": "Gamintojas (pavad)"}, "textAlign": "left"},
    ]

    for col_id in ["previous_value", "avg_3m", "avg_6m"]:
        width_conf = {
            "if": {"column_id": col_id},
            "minWidth": "140px",
            "width": "140px",
            "maxWidth": "160px",
        }
        if col_id == "avg_3m" and show_changes:
            width_conf.update({"minWidth": "200px", "width": "220px", "maxWidth": "260px"})
        cell_conditional.append(width_conf)
        data_conditional.append(
            {
                "if": {"filter_query": f'{{{col_id}}} = "—"', "column_id": col_id},
                "color": "#6c757d",
            }
        )

    last_column_style = {
        "if": {"column_id": "last_value"},
        "minWidth": "220px",
        "width": "240px",
        "maxWidth": "320px",
        "whiteSpace": "normal",
    }
    if not show_changes:
        last_column_style.update(
            {
                "minWidth": "160px",
                "width": "180px",
                "maxWidth": "220px",
                "whiteSpace": "nowrap",
            }
        )
    cell_conditional.append(last_column_style)

    wrapper_style = dict(CATEGORY_VENDOR_WRAPPER_STYLE)
    wrapper_style["display"] = "none"
    title = ""
    columns: List[Dict[str, Any]] = []
    data_rows: List[Dict[str, Any]] = []
    tooltip_rows: List[Dict[str, Any]] = []

    table_rows = table_data or []
    available_categories = {
        row.get("Kategorija")
        for row in table_rows
        if isinstance(row, dict) and row.get("Kategorija")
    }

    ctx = dash.callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    selection = stored_category or None
    if triggered in {
        "customer-category-vendor-close.n_clicks",
        "customer-category-detail-close.n_clicks",
    }:
        selection = None
    elif triggered == "customer-category-detail-table.active_cell":
        selection = None
        if active_cell and isinstance(active_cell, dict):
            row_idx = active_cell.get("row")
            if isinstance(row_idx, int) and 0 <= row_idx < len(table_rows):
                candidate = table_rows[row_idx].get("Kategorija")
                if candidate:
                    selection = candidate

    if not selected_group:
        selection = None

    if selection and selection not in available_categories:
        selection = None

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if (
        not selected_clients
        or len(selected_clients) != 1
        or not selection
        or not selected_group
    ):
        return (
            selection,
            wrapper_style,
            title,
            columns,
            data_rows,
            tooltip_rows,
            table_style,
            cell_style,
            cell_conditional,
            data_conditional,
        )

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    frame, metadata = compute_customer_category_vendor_summary(
        filters, metric, selected_group, selection
    )
    if frame.empty:
        return (
            None,
            wrapper_style,
            title,
            columns,
            data_rows,
            tooltip_rows,
            table_style,
            cell_style,
            cell_conditional,
            data_conditional,
        )

    last_label = _format_period_label(metadata.get("last_period"))
    prev_label = _format_period_label(metadata.get("previous_period"))
    window3_label = _format_window_range(metadata.get("window3_periods"))
    window6_label = _format_window_range(metadata.get("window6_periods"))

    tooltip_prev = None
    if last_label and prev_label:
        tooltip_prev = f"{last_label} vs {prev_label} (MoM)"
    tooltip_avg = None
    if window3_label and window6_label:
        tooltip_avg = f"Avg3 ({window3_label}) vs Avg6 ({window6_label})"

    columns = [
        {"name": "Gamintojas (pavad)", "id": "Gamintojas (pavad)"},
        {
            "name": "Paskutinis mėnuo" + (f" ({last_label})" if last_label else ""),
            "id": "last_value",
            "presentation": "markdown",
        },
        {
            "name": "Ankstesnis mėnuo" + (f" ({prev_label})" if prev_label else ""),
            "id": "previous_value",
        },
        {
            "name": "Vidurkis 3 mėn.",
            "id": "avg_3m",
            "presentation": "markdown",
        },
        {"name": "Vidurkis 6 mėn.", "id": "avg_6m"},
    ]

    for row in frame.to_dict("records"):
        last_value = row.get("last_value")
        prev_value = row.get("previous_value")
        avg3_value = row.get("avg_3m")
        avg6_value = row.get("avg_6m")
        vendor_name = row.get("Gamintojas (pavad)")
        data_rows.append(
            {
                "Gamintojas (pavad)": vendor_name,
                "last_value": _build_category_last_cell(
                    metric,
                    last_value,
                    prev_value,
                    show_changes,
                    tooltip_prev,
                ),
                "previous_value": _format_category_value(metric, prev_value),
                "avg_3m": _build_category_avg3_cell(
                    metric,
                    avg3_value,
                    avg6_value,
                    show_changes,
                    tooltip_avg,
                ),
                "avg_6m": _format_category_value(metric, avg6_value),
            }
        )
        tooltip_rows.append(
            {
                "last_value": (tooltip_prev or "") if show_changes else "",
                "avg_3m": (tooltip_avg or "") if show_changes else "",
            }
        )

    wrapper_style["display"] = "block"
    title = f"Gamintojai (grupė: {selected_group}, kategorija: {selection})"

    return (
        selection,
        wrapper_style,
        title,
        columns,
        data_rows,
        tooltip_rows,
        table_style,
        cell_style,
        cell_conditional,
        data_conditional,
    )


@callback(
    Output("customer-category-export-download", "data"),
    Input("customer-category-export", "n_clicks"),
    State("customer-category-metric", "value"),
    State("customer-manager", "value"),
    State("customer-client", "value"),
    State("customer-code", "value"),
    State("customer-years", "value"),
    prevent_initial_call=True,
)
def export_category_table(n_clicks, metric, managers, clients, codes, years):
    metric = metric or "APYVARTA"
    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return dash.no_update

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    frame, metadata = compute_customer_category_group_summary(filters, metric)
    if frame.empty:
        return dash.no_update

    last_label = _format_period_label(metadata.get("last_period"))
    prev_label = _format_period_label(metadata.get("previous_period"))

    export_df = frame.copy()
    export_df = export_df.rename(
        columns={
            "Kategorijos grupe": "Kategorijos grupe",
            "last_value": "Paskutinis mėnuo" + (f" ({last_label})" if last_label else ""),
            "previous_value": "Ankstesnis mėnuo" + (f" ({prev_label})" if prev_label else ""),
            "avg_3m": "Vidurkis 3 mėn.",
            "avg_6m": "Vidurkis 6 mėn.",
        }
    )

    client_name = selected_clients[0].replace(" ", "_")
    filename = f"kategorijos_grupe_{client_name}_{metric}.xlsx"
    return dcc.send_data_frame(export_df.to_excel, filename, index=False)


@callback(
    Output("customer-category-detail-export-download", "data"),
    Input("customer-category-detail-export", "n_clicks"),
    State("customer-category-selected-group", "data"),
    State("customer-category-metric", "value"),
    State("customer-manager", "value"),
    State("customer-client", "value"),
    State("customer-code", "value"),
    State("customer-years", "value"),
    prevent_initial_call=True,
)
def export_category_detail_table(
    n_clicks, selection, metric, managers, clients, codes, years
):
    metric = metric or "APYVARTA"
    if not selection:
        return dash.no_update

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return dash.no_update

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    frame, metadata = compute_customer_category_detail_summary(filters, metric, selection)
    if frame.empty:
        return dash.no_update

    last_label = _format_period_label(metadata.get("last_period"))
    prev_label = _format_period_label(metadata.get("previous_period"))

    export_df = frame.copy()
    export_df = export_df.rename(
        columns={
            "Kategorija": "Kategorija",
            "last_value": "Paskutinis mėnuo" + (f" ({last_label})" if last_label else ""),
            "previous_value": "Ankstesnis mėnuo" + (f" ({prev_label})" if prev_label else ""),
            "avg_3m": "Vidurkis 3 mėn.",
            "avg_6m": "Vidurkis 6 mėn.",
        }
    )

    client_name = selected_clients[0].replace(" ", "_")
    group_name = str(selection).replace(" ", "_")
    filename = f"kategorijos_{group_name}_{client_name}_{metric}.xlsx"
    return dcc.send_data_frame(export_df.to_excel, filename, index=False)
