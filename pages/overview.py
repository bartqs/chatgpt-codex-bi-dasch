import dash
from dash import Input, Output, callback, dash_table, dcc, html

from data.app_data import (
    FILIALAS_OPTIONS,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_WHITE,
    MENUO_LABELS_LT,
    MENUO_TVARKA,
    METRICS,
    SEGMENT_OPTIONS,
    SummaryCalculator,
    YEAR_OPTIONS,
    df_sums,
    filter_dataframe,
)

dash.register_page(
    __name__,
    path="/overview",
    name="Suvestinė",
    title="Suvestinė",
)


def layout():
    """Render the overview page layout (identical to original tab)."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(src="/assets/logo.jpg", height="26px", style={"marginRight": "10px"}),
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
                            dcc.Dropdown(METRICS, "APYVARTA", id="metric", clearable=False, style={"minWidth": "150px"}),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Grafiko tipas"),
                            dcc.Dropdown(
                                [
                                    {"label": "Stulpeliai", "value": "bar"},
                                    {"label": "Linijos", "value": "line"},
                                ],
                                "line",
                                id="chart_type",
                                clearable=False,
                                style={"minWidth": "140px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Segmentas"),
                            dcc.Dropdown(
                                [{"label": s, "value": s} for s in SEGMENT_OPTIONS],
                                [],
                                id="segment",
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
                                [{"label": f, "value": f} for f in FILIALAS_OPTIONS],
                                FILIALAS_OPTIONS,
                                id="filialas",
                                multi=True,
                                style={"minWidth": "180px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Metai"),
                            dcc.Dropdown(
                                [{"label": int(y), "value": int(y)} for y in YEAR_OPTIONS],
                                [int(y) for y in YEAR_OPTIONS],
                                id="years",
                                multi=True,
                                style={"minWidth": "180px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                    html.Div(
                        [
                            html.Label("Mėnesiai"),
                            dcc.Dropdown(
                                [{"label": MENUO_LABELS_LT[i], "value": MENUO_TVARKA[i]} for i in range(12)],
                                [],
                                id="months",
                                multi=True,
                                placeholder="(tušti = visi)",
                                style={"minWidth": "220px"},
                            ),
                        ],
                        style={"marginLeft": "12px"},
                    ),
                ],
                style={
                    "display": "flex",
                    "alignItems": "end",
                    "flexWrap": "wrap",
                    "gap": "8px",
                    "padding": "10px 16px",
                    "background": IC_WHITE,
                },
            ),
            html.Div(
                id="kpi_row",
                style={"display": "grid", "gridTemplateColumns": "repeat(3,1fr)", "gap": "12px", "padding": "8px 16px"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("L51", style={"fontWeight": 700, "color": IC_NAVY, "margin": "8px 8px 0"}),
                            dcc.Graph(id="graph_l51", config={"displaylogo": False}, style={"height": "360px"}),
                        ],
                        style={"background": IC_WHITE, "border": f"1px solid {IC_GRAY}", "borderRadius": "10px", "padding": "6px"},
                    ),
                    html.Div(
                        [
                            html.Div("L52", style={"fontWeight": 700, "color": IC_NAVY, "margin": "8px 8px 0"}),
                            dcc.Graph(id="graph_l52", config={"displaylogo": False}, style={"height": "360px"}),
                        ],
                        style={"background": IC_WHITE, "border": f"1px solid {IC_GRAY}", "borderRadius": "10px", "padding": "6px"},
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px", "padding": "16px"},
            ),
            html.Div(
                [
                    html.Div("Mėnesių suvestinė", style={"fontWeight": 700, "color": IC_NAVY, "margin": "0 0 6px 2px"}),
                    dash_table.DataTable(
                        id="tbl_months",
                        columns=[],
                        data=[],
                        style_table={"overflowX": "auto", "border": f"1px solid {IC_GRAY}", "borderRadius": "10px"},
                        style_header={"backgroundColor": IC_NAVY, "color": IC_WHITE, "fontWeight": "700"},
                        style_cell={"padding": "6px 8px", "fontFamily": "Arial", "fontSize": "13px"},
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
                            {"if": {"column_id": MENUO_TVARKA + ["Bendra"]}, "textAlign": "right"},
                        ],
                        export_format="csv",
                    ),
                ],
                style={"padding": "0 16px 16px"},
            ),
        ],
        style={"background": IC_BG},
    )


@callback(
    Output("graph_l51", "figure"),
    Output("graph_l52", "figure"),
    Output("tbl_months", "columns"),
    Output("tbl_months", "data"),
    Output("kpi_row", "children"),
    Input("metric", "value"),
    Input("chart_type", "value"),
    Input("segment", "value"),
    Input("filialas", "value"),
    Input("years", "value"),
    Input("months", "value"),
)
def update_summary(metric, chart_type, segments, filialai, years_sel, months_sel):
    """Replicate the original summary tab callback behavior."""
    years_sel = sorted(set(map(int, years_sel or YEAR_OPTIONS)))

    d = filter_dataframe(df_sums, segments=segments, filialai=filialai, years=years_sel)

    calc = SummaryCalculator(d)

    fig_l51 = calc.create_branch_figure("L51", metric, chart_type, years_sel, months_sel)
    fig_l52 = calc.create_branch_figure("L52", metric, chart_type, years_sel, months_sel)

    columns, data = calc.build_monthly_table(years_sel, months_sel, metric)

    this_year = int(sorted(years_sel)[-1])
    prev_candidates = [y for y in sorted(set(df_sums["Metai"])) if y < this_year]
    prev_year = prev_candidates[-1] if prev_candidates else None

    kpi_row = calc.calculate_kpis(this_year, prev_year, metric, months_sel)

    return fig_l51, fig_l52, columns, data, kpi_row
