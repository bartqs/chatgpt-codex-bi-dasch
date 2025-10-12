import math
from typing import List

import dash
from dash import Input, Output, callback, dash_table, dcc, html

from data.app_data import (
    CUSTOMER_CODES,
    CUSTOMER_DEFAULT_YEAR,
    CUSTOMER_FILIALAI,
    CUSTOMER_KATEGORIJOS,
    CUSTOMER_LIST,
    CUSTOMER_METRIC_OPTIONS,
    CUSTOMER_SEGMENTAI,
    CUSTOMER_YEAR_OPTIONS,
    GREEN,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_WHITE,
    MENUO_LABELS_LT,
    MENUO_TVARKA,
    RED,
    build_client_matrix,
    build_general_table,
    compute_kpis,
    load_customer_overview_df,
    load_customer_segment_df,
    load_customer_client_keys,
    load_customer_history_df,
)


dash.register_page(
    __name__,
    path="/customers",
    name="Klientų apžvalga",
    title="Klientų apžvalga",
)


def _default_year() -> int:
    if CUSTOMER_YEAR_OPTIONS:
        if CUSTOMER_DEFAULT_YEAR in CUSTOMER_YEAR_OPTIONS:
            return CUSTOMER_DEFAULT_YEAR
        return CUSTOMER_YEAR_OPTIONS[-1]
    return CUSTOMER_DEFAULT_YEAR


DEFAULT_YEAR = _default_year()


def _is_nan(value) -> bool:
    try:
        return value is None or (isinstance(value, float) and math.isnan(value))
    except TypeError:
        return False


def _render_kpi_cards(kpis: List[dict], active_metric: str) -> List[html.Div]:
    cards: List[html.Div] = []
    for item in kpis:
        metric = item["metric"]
        value_text = item["formatted"]
        yoy_value = item["yoy"]
        yoy_unit = item["yoy_unit"]

        if _is_nan(yoy_value):
            trend_text = "– vs LY"
            trend_color = IC_GRAY
        else:
            arrow = "▲" if yoy_value >= 0 else "▼"
            sign = "+" if yoy_value >= 0 else ""
            if yoy_unit == "pp":
                trend_text = f"{arrow} {sign}{yoy_value:.1f} pp vs LY"
            else:
                trend_text = f"{arrow} {sign}{yoy_value:.1f}% vs LY"
            trend_color = GREEN if yoy_value >= 0 else RED

        card_style = {
            "background": IC_WHITE,
            "borderRadius": "10px",
            "padding": "16px",
            "boxShadow": "0 2px 6px rgba(0,0,0,0.08)",
            "border": f"2px solid {IC_NAVY}" if metric == active_metric else f"1px solid {IC_GRAY}",
            "display": "flex",
            "flexDirection": "column",
            "gap": "6px",
        }

        cards.append(
            html.Div(
                [
                    html.Div(
                        metric,
                        style={"fontSize": "15px", "fontWeight": 600, "color": IC_NAVY},
                    ),
                    html.Div(
                        value_text,
                        style={"fontSize": "24px", "fontWeight": 700, "color": "#1B1C1D"},
                    ),
                    html.Div(
                        trend_text,
                        style={"fontSize": "13px", "fontWeight": 500, "color": trend_color},
                    ),
                ],
                style=card_style,
            )
        )

    return cards


def layout():
    metric_options = [{"label": label, "value": label} for label in CUSTOMER_METRIC_OPTIONS]
    segment_options = [{"label": s, "value": s} for s in CUSTOMER_SEGMENTAI]
    filial_options = [{"label": f, "value": f} for f in CUSTOMER_FILIALAI]
    category_options = [{"label": c, "value": c} for c in CUSTOMER_KATEGORIJOS]
    customer_options = [{"label": c, "value": c} for c in CUSTOMER_LIST]
    customer_code_options = [{"label": c, "value": c} for c in CUSTOMER_CODES]
    year_options = [{"label": int(y), "value": int(y)} for y in CUSTOMER_YEAR_OPTIONS]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(
                                src="/assets/logo.jpg",
                                height="26px",
                                style={"marginRight": "10px"},
                            ),
                            html.Div(
                                "Inter Cars – BI",
                                style={"fontSize": "18px", "fontWeight": 800, "color": IC_NAVY},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    )
                ],
                style={
                    "padding": "10px 14px",
                    "borderBottom": f"2px solid {IC_NAVY}",
                    "background": IC_WHITE,
                },
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Matas"),
                            dcc.Dropdown(
                                metric_options,
                                CUSTOMER_METRIC_OPTIONS[0],
                                id="customer-metric",
                                clearable=False,
                                style={"minWidth": "180px"},
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Segmentas"),
                            dcc.Dropdown(
                                segment_options,
                                [],
                                id="customer-segment",
                                multi=True,
                                placeholder="Visi",
                                style={"minWidth": "200px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Filialas"),
                            dcc.Dropdown(
                                filial_options,
                                [],
                                id="customer-branch",
                                multi=True,
                                placeholder="Visi",
                                style={"minWidth": "180px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Metai"),
                            dcc.Dropdown(
                                year_options,
                                DEFAULT_YEAR,
                                id="customer-year",
                                clearable=False,
                                style={"minWidth": "140px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Mėnuo"),
                            dcc.Dropdown(
                                [
                                    {"label": MENUO_LABELS_LT[idx], "value": MENUO_TVARKA[idx]}
                                    for idx in range(len(MENUO_TVARKA))
                                ],
                                [],
                                id="customer-month",
                                multi=True,
                                placeholder="Visi (YTD)",
                                style={"minWidth": "200px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Klientas"),
                            dcc.Dropdown(
                                customer_options,
                                None,
                                id="customer-client",
                                clearable=True,
                                placeholder="Pasirinkite klientą",
                                style={"minWidth": "220px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Kliento kodas"),
                            dcc.Dropdown(
                                customer_code_options,
                                None,
                                id="customer-code",
                                clearable=True,
                                placeholder="Pasirinkite kodą",
                                style={"minWidth": "180px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Kategorija"),
                            dcc.Dropdown(
                                category_options,
                                [],
                                id="customer-category",
                                multi=True,
                                placeholder="Visos",
                                style={"minWidth": "200px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "alignItems": "end",
                    "gap": "10px",
                    "padding": "12px 16px",
                    "background": IC_WHITE,
                },
            ),
            html.Div(
                id="customer-kpi-cards",
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                    "gap": "12px",
                    "padding": "16px",
                },
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Bendroji suvestinė",
                                style={"fontWeight": 700, "color": IC_NAVY, "marginBottom": "8px"},
                            ),
                            dash_table.DataTable(
                                id="customer-summary-table",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto", "border": f"1px solid {IC_GRAY}", "borderRadius": "10px"},
                                style_header={
                                    "backgroundColor": IC_NAVY,
                                    "color": IC_WHITE,
                                    "fontWeight": "700",
                                },
                                style_cell={
                                    "padding": "6px 8px",
                                    "fontFamily": "Arial",
                                    "fontSize": "13px",
                                },
                                style_data_conditional=[
                                    {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
                                    {"if": {"column_id": ["Apyvarta", "Pajamos", "Kiekis", "Marža %"]}, "textAlign": "right"},
                                ],
                            ),
                        ],
                        style={
                            "background": IC_WHITE,
                            "border": f"1px solid {IC_GRAY}",
                            "borderRadius": "10px",
                            "padding": "16px",
                        },
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="customer-matrix-title",
                                style={"fontWeight": 700, "color": IC_NAVY, "marginBottom": "8px"},
                            ),
                            html.Div(
                                id="customer-matrix-message",
                                style={"fontSize": "14px", "color": IC_GRAY, "marginBottom": "10px"},
                            ),
                            dash_table.DataTable(
                                id="customer-matrix-table",
                                columns=[],
                                data=[],
                                style_table={"overflowX": "auto", "border": f"1px solid {IC_GRAY}", "borderRadius": "10px"},
                                style_header={
                                    "backgroundColor": IC_NAVY,
                                    "color": IC_WHITE,
                                    "fontWeight": "700",
                                },
                                style_cell={
                                    "padding": "6px 8px",
                                    "fontFamily": "Arial",
                                    "fontSize": "13px",
                                    "textAlign": "right",
                                },
                                style_cell_conditional=[
                                    {"if": {"column_id": "Metai"}, "textAlign": "left"}
                                ],
                            ),
                        ],
                        style={
                            "background": IC_WHITE,
                            "border": f"1px solid {IC_GRAY}",
                            "borderRadius": "10px",
                            "padding": "16px",
                            "minHeight": "320px",
                        },
                    ),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "gap": "16px",
                    "padding": "0 16px 16px",
                },
            ),
        ],
        style={"background": IC_BG, "minHeight": "100vh"},
    )


@callback(
    Output("customer-kpi-cards", "children"),
    Output("customer-summary-table", "columns"),
    Output("customer-summary-table", "data"),
    Output("customer-matrix-title", "children"),
    Output("customer-matrix-table", "columns"),
    Output("customer-matrix-table", "data"),
    Output("customer-matrix-message", "children"),
    Input("customer-metric", "value"),
    Input("customer-segment", "value"),
    Input("customer-branch", "value"),
    Input("customer-year", "value"),
    Input("customer-month", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-category", "value"),
)
def update_customer_overview(metric, segments, branches, year, months, client, code, categories):
    year = int(year or DEFAULT_YEAR)
    months_filter = months or None

    filters = {
        "metai": year,
        "segmentas": segments or None,
        "filialas": branches or None,
        "menuo": months_filter,
        "klientas": client,
        "kliento_kodas": code,
        "kategorija": categories or None,
    }

    summary_df = load_customer_overview_df(filters)
    segment_df = load_customer_segment_df(filters)
    client_keys_df = load_customer_client_keys(filters)

    kpis = compute_kpis(summary_df, year, months_filter, client_keys_df)
    kpi_cards = _render_kpi_cards(kpis, metric)

    summary_columns, summary_data = build_general_table(segment_df)

    matrix_title = "Kliento mėnesinė dinamika"
    history_df = load_customer_history_df(filters)
    matrix_columns, matrix_data = build_client_matrix(history_df.iloc[0:0], [], metric)
    matrix_message = "Pasirinkite klientą…"

    if (client or code) and not history_df.empty:
        available_years = sorted(
            {int(y) for y in history_df["Metai"].unique() if year - 3 <= int(y) <= year}
        )
        ordered_years = [y for y in [year, year - 1, year - 2, year - 3] if y in available_years]
        matrix_columns, matrix_data = build_client_matrix(history_df, ordered_years, metric)
        if client:
            matrix_title = f"Kliento mėnesinė dinamika – {client}"
        elif code:
            matrix_title = f"Kliento mėnesinė dinamika – {code}"

        matrix_message = "" if matrix_data else "Pasirinktai kombinacijai nėra duomenų."

    return (
        kpi_cards,
        summary_columns,
        summary_data,
        matrix_title,
        matrix_columns,
        matrix_data,
        matrix_message,
    )
