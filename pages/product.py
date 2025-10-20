import dash
import numpy as np
import pandas as pd
from dash import Input, Output, callback, dash_table, dcc, html
from plotly import graph_objects as go

from data.app_data import (
    FILIALAI_ADV,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_RED,
    IC_WHITE,
    MENUO_LABELS_LT,
    YEAR_OPTIONS,
    load_product_manufacturer_monthly,
    load_product_manufacturer_summary,
)


dash.register_page(
    __name__,
    path="/product",
    name="Product",
    title="Produktų analizė",
)


_MONTH_LABEL_MAP = {f"M-{i:02d}": MENUO_LABELS_LT[i - 1] for i in range(1, 13)}
_CHART_HEIGHT = 520


def _format_currency(value: float) -> str:
    if value is None or pd.isna(value):
        return "–"
    return f"{int(round(float(value))):,}".replace(",", " ") + " €"


def _format_quantity(value: float) -> str:
    if value is None or pd.isna(value):
        return "–"
    return f"{int(round(float(value))):,}".replace(",", " ")


def _format_margin(value: float) -> str:
    if value is None or pd.isna(value):
        return "–"
    return f"{float(value):.1f} %"


def _table_display(df: pd.DataFrame) -> list[dict[str, str]]:
    if df.empty:
        return []

    records = []
    for row in df.to_dict("records"):
        records.append(
            {
                "Gamintojas": row["Gamintojas"],
                "Apyvarta": _format_currency(row["Apyvarta"]),
                "Pajamos": _format_currency(row["Pajamos"]),
                "Kiekis": _format_quantity(row["Kiekis"]),
                "Marza_pct": _format_margin(row["Marza_pct"]),
            }
        )

    return records


def _empty_chart() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=_CHART_HEIGHT,
        paper_bgcolor=IC_WHITE,
        plot_bgcolor=IC_WHITE,
        margin=dict(l=60, r=60, t=40, b=60),
        showlegend=True,
    )
    return fig


def _build_combo_figure(df: pd.DataFrame, manufacturer: str) -> go.Figure:
    df = df.copy()
    df["Menuo_str"] = df["Menuo"].astype(str)
    df["MonthLabel"] = df["Menuo_str"].map(_MONTH_LABEL_MAP).fillna(df["Menuo_str"])
    x_vals = df["MonthLabel"].tolist()

    bar_text = [_format_currency(v) for v in df["Apyvarta"]]
    bar_hover = [f"{label}: {text}" for label, text in zip(x_vals, bar_text)]

    margin_text = ["—" if pd.isna(v) else f"{v:.1f} %" for v in df["Marza_pct"]]
    margin_hover = [f"{label}: {text}" for label, text in zip(x_vals, margin_text)]

    qty_text = ["—" if pd.isna(v) else _format_quantity(v) for v in df["Kiekis"]]
    qty_hover = [f"{label}: {text}" for label, text in zip(x_vals, qty_text)]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=x_vals,
            y=df["Apyvarta"],
            name="Apyvarta",
            marker_color=IC_RED,
            text=bar_text,
            textposition="outside",
            hovertext=bar_hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=df["Marza_pct"],
            name="Marža %",
            mode="lines+markers+text",
            text=margin_text,
            textposition="top center",
            marker=dict(color=IC_NAVY, size=8),
            line=dict(color=IC_NAVY, width=2),
            yaxis="y2",
            hovertext=margin_hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=df["Kiekis"],
            name="Kiekis",
            mode="lines+markers+text",
            text=qty_text,
            textposition="bottom center",
            marker=dict(color=IC_GRAY, size=8),
            line=dict(color=IC_GRAY, width=2, dash="dot"),
            yaxis="y3",
            hovertext=qty_hover,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )

    margin_series = df["Marza_pct"].dropna()
    if margin_series.empty:
        margin_range = [0, 100]
    else:
        margin_min = float(np.floor(margin_series.min() / 5.0) * 5)
        margin_max = float(np.ceil(margin_series.max() / 5.0) * 5)
        if margin_min == margin_max:
            margin_max = margin_min + 10
        margin_range = [margin_min, margin_max]

    qty_series = df["Kiekis"].dropna()
    if qty_series.empty:
        qty_range_max = 1.0
    else:
        qty_range_max = float(np.ceil(qty_series.max() / 10.0) * 10)
        if qty_range_max == 0:
            qty_range_max = 1.0

    fig.update_layout(
        height=_CHART_HEIGHT,
        title=f"{manufacturer} – mėnesio dinamika",
        margin=dict(l=70, r=80, t=60, b=80),
        bargap=0.25,
        plot_bgcolor=IC_WHITE,
        paper_bgcolor=IC_WHITE,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )

    fig.update_xaxes(title="Mėnuo", tickmode="array", tickvals=x_vals, ticktext=x_vals)
    fig.update_yaxes(
        title="Apyvarta (€)",
        tickprefix="€",
        tickformat=",.0f",
        showgrid=True,
        gridcolor="#E4E6EB",
        zeroline=False,
    )
    fig.update_layout(
        yaxis2=dict(
            title="Marža %",
            overlaying="y",
            side="right",
            titlefont=dict(color=IC_NAVY),
            tickfont=dict(color=IC_NAVY),
            range=margin_range,
            showgrid=False,
            zeroline=False,
        ),
        yaxis3=dict(
            title="Kiekis",
            overlaying="y",
            side="right",
            position=1.08,
            titlefont=dict(color=IC_GRAY),
            tickfont=dict(color=IC_GRAY),
            tickformat=",.0f",
            showgrid=False,
            zeroline=False,
            range=[0, qty_range_max],
        ),
    )

    return fig


def layout():
    default_year = YEAR_OPTIONS[-1] if YEAR_OPTIONS else None
    default_branches = [b for b in FILIALAI_ADV if b in ("L51", "L52")]
    if not default_branches:
        default_branches = FILIALAI_ADV[:2] if len(FILIALAI_ADV) >= 2 else FILIALAI_ADV

    base_df = (
        load_product_manufacturer_summary(default_year, tuple(default_branches))
        if default_year and default_branches
        else pd.DataFrame(columns=["Gamintojas", "Apyvarta", "Pajamos", "Kiekis", "Marza_pct"])
    )

    table_data = _table_display(base_df)

    columns = [
        {"name": "Gamintojas", "id": "Gamintojas"},
        {"name": "Apyvarta (€)", "id": "Apyvarta"},
        {"name": "Pajamos (€)", "id": "Pajamos"},
        {"name": "Kiekis", "id": "Kiekis"},
        {"name": "Marža %", "id": "Marza_pct"},
    ]

    table_style = dict(
        style_table={"overflowX": "auto", "border": f"1px solid {IC_GRAY}", "borderRadius": "10px"},
        style_cell={
            "padding": "8px 10px",
            "fontSize": "13px",
            "fontFamily": "Arial",
            "whiteSpace": "nowrap",
        },
        style_header={"backgroundColor": IC_NAVY, "color": IC_WHITE, "fontWeight": 700},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
            {"if": {"column_id": ["Apyvarta", "Pajamos", "Kiekis", "Marza_pct"]}, "textAlign": "right"},
            {
                "if": {"state": "selected"},
                "backgroundColor": "rgba(227, 6, 19, 0.14)",
                "borderLeft": "3px solid rgba(227, 6, 19, 0.35)",
            },
            {
                "if": {"state": "active"},
                "backgroundColor": "rgba(227, 6, 19, 0.14)",
                "borderLeft": "3px solid rgba(227, 6, 19, 0.35)",
            },
        ],
        page_size=20,
    )

    filter_style = {
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "12px",
        "margin": "12px 0 20px 0",
    }

    filter_item = {"flex": "1 1 220px", "minWidth": "220px"}

    return html.Div(
        [
            html.Div(
                "Produktų analizė",
                style={"fontSize": 22, "fontWeight": 800, "color": IC_NAVY, "margin": "10px 0"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Metai"),
                            dcc.Dropdown(
                                id="product-filter-year",
                                options=[{"label": int(y), "value": int(y)} for y in YEAR_OPTIONS],
                                value=int(default_year) if default_year else None,
                                clearable=False,
                            ),
                        ],
                        style=filter_item,
                    ),
                    html.Div(
                        [
                            html.Label("Filialas"),
                            dcc.Dropdown(
                                id="product-filter-branches",
                                options=[{"label": f, "value": f} for f in FILIALAI_ADV],
                                value=default_branches,
                                multi=True,
                                clearable=False,
                            ),
                        ],
                        style=filter_item,
                    ),
                ],
                style=filter_style,
            ),
            html.Div(
                [
                    html.Div(
                        "Gamintojai",
                        style={"fontWeight": 700, "color": IC_NAVY, "marginBottom": "8px"},
                    ),
                    dash_table.DataTable(
                        id="product-table",
                        columns=columns,
                        data=table_data,
                        row_selectable="single",
                        cell_selectable=False,
                        **table_style,
                    ),
                    html.Div(
                        id="product-table-empty",
                        style={"marginTop": "10px", "color": "#6c757d", "fontStyle": "italic"},
                    ),
                ],
                style={
                    "background": IC_WHITE,
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "padding": "16px",
                    "marginBottom": "24px",
                },
            ),
            html.Div(
                [
                    html.Div(
                        "Mėnesio dinamika",
                        style={"fontWeight": 700, "color": IC_NAVY, "marginBottom": "8px"},
                    ),
                    html.Div(
                        "Pasirinkite gamintoją, kad matytumėte mėnesio dinamiką.",
                        id="product-chart-empty",
                        style={
                            "padding": "20px",
                            "background": IC_WHITE,
                            "border": f"1px dashed {IC_GRAY}",
                            "borderRadius": "8px",
                            "color": "#6c757d",
                        },
                    ),
                    dcc.Graph(
                        id="product-combo-chart",
                        figure=_empty_chart(),
                        style={"display": "none"},
                        config={"displayModeBar": False},
                    ),
                ],
                style={
                    "background": IC_WHITE,
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "padding": "16px",
                    "marginBottom": "24px",
                },
            ),
        ],
        style={
            "background": IC_BG,
            "minHeight": "100vh",
            "padding": "20px 32px",
        },
    )


@callback(
    Output("product-table", "data"),
    Output("product-table", "selected_rows"),
    Output("product-table-empty", "children"),
    Input("product-filter-year", "value"),
    Input("product-filter-branches", "value"),
)
def update_product_table(year, branches):
    branches = branches or []
    df = load_product_manufacturer_summary(year, tuple(branches))
    data = _table_display(df)

    message = ""
    if not data:
        message = "Nėra duomenų su pasirinktais filtrais."

    return data, [], message


@callback(
    Output("product-combo-chart", "figure"),
    Output("product-chart-empty", "children"),
    Output("product-chart-empty", "style"),
    Output("product-combo-chart", "style"),
    Input("product-filter-year", "value"),
    Input("product-filter-branches", "value"),
    Input("product-table", "selected_rows"),
    Input("product-table", "data"),
)
def update_product_chart(year, branches, selected_rows, table_data):
    empty_style = {
        "padding": "20px",
        "background": IC_WHITE,
        "border": f"1px dashed {IC_GRAY}",
        "borderRadius": "8px",
        "color": "#6c757d",
    }

    if not year or not branches:
        return _empty_chart(), "Pasirinkite filtrus, kad matytumėte duomenis.", empty_style, {"display": "none"}

    if not table_data:
        return _empty_chart(), "Nėra duomenų su pasirinktais filtrais.", empty_style, {"display": "none"}

    if not selected_rows:
        return _empty_chart(), "Pasirinkite gamintoją, kad matytumėte mėnesio dinamiką.", empty_style, {"display": "none"}

    idx = selected_rows[0]
    if idx is None or idx >= len(table_data):
        return _empty_chart(), "Pasirinkite gamintoją, kad matytumėte mėnesio dinamiką.", empty_style, {"display": "none"}

    manufacturer = table_data[idx]["Gamintojas"]
    df = load_product_manufacturer_monthly(year, tuple(branches), manufacturer)

    if df.empty:
        return _empty_chart(), "Šiam gamintojui nėra duomenų su pasirinktais filtrais.", empty_style, {"display": "none"}

    figure = _build_combo_figure(df, manufacturer)
    return figure, "", {"display": "none"}, {"display": "block"}
