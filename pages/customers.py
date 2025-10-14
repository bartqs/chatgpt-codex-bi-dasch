import dash
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
import plotly.graph_objects as go

from data.app_data import (
    CUSTOMER_COLORWAY,
    CUSTOMER_METRICS,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_RED,
    IC_WHITE,
    MENUO_LABELS_LT,
    _fmt_eur,
    _fmt_pct,
    _fmt_qty,
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
                "Kliento rezultatų dinamika pagal metus",
                style={"fontWeight": 700, "color": IC_NAVY, "marginBottom": "8px"},
            ),
            dcc.Graph(
                id="customer-chart",
                config={"displaylogo": False},
                style={"height": "420px"},
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
                    "overflowX": "auto",
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                },
                style_header={
                    "backgroundColor": IC_NAVY,
                    "color": IC_WHITE,
                    "fontWeight": 700,
                    "textAlign": "center",
                },
                style_cell={
                    "padding": "6px 10px",
                    "fontFamily": "Arial",
                    "fontSize": "13px",
                    "textAlign": "right",
                },
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

    return html.Div(
        [filter_row, status_bar, empty_state, chart_section, table_section],
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
    Input("customer-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(n_clicks):
    return [], [], [], DEFAULT_YEARS, "APYVARTA"


@callback(
    Output("customer-chart", "figure"),
    Output("customer-table", "columns"),
    Output("customer-table", "data"),
    Output("customer-empty", "children"),
    Output("customer-empty", "style"),
    Output("customer-chart-wrapper", "style"),
    Output("customer-table-wrapper", "style"),
    Output("customer-status-text", "children"),
    Input("customer-manager", "value"),
    Input("customer-client", "value"),
    Input("customer-code", "value"),
    Input("customer-years", "value"),
    Input("customer-metric", "value"),
)
def update_customer_view(managers, clients, codes, years, metric):
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

    selected_clients = clients if isinstance(clients, list) else (clients or [])
    if not selected_clients or len(selected_clients) != 1:
        return go.Figure(), [], [], empty_children, empty_style, hidden, hidden, status_text

    filters = {
        "vadybininkas": managers if isinstance(managers, list) else (managers or []),
        "klientas": selected_clients,
        "kliento_kodas": codes if isinstance(codes, list) else (codes or []),
        "metai": years if isinstance(years, list) else (years or []),
    }

    aggregated = compute_customer_monthly_aggregation(filters, metric)
    if aggregated.empty:
        return go.Figure(), [], [], NO_DATA_MESSAGE, empty_style, hidden, hidden, status_text

    metric_col = METRIC_COLUMN_MAP[metric]
    months = sorted(aggregated["Mėnuo"].unique())
    years_sorted = sorted(aggregated["Metai"].unique())
    latest_year = max(years_sorted)

    fig = go.Figure()
    ticks = months
    ticktext = [MENUO_LABELS_LT[m - 1] if 1 <= m <= 12 else str(m) for m in ticks]

    for year in years_sorted:
        df_year = aggregated[aggregated["Metai"] == year]
        color = CUSTOMER_COLORWAY.get(year, IC_GRAY)
        if year == latest_year:
            color = IC_RED
        month_labels = [
            MENUO_LABELS_LT[m - 1] if isinstance(m, (int, float)) and 1 <= int(m) <= 12 else str(m)
            for m in df_year["Mėnuo"]
        ]
        formatted_values = [_format_table_value(metric, v) for v in df_year[metric_col]]
        customdata = list(zip(month_labels, formatted_values))
        fig.add_trace(
            go.Scatter(
                x=df_year["Mėnuo"],
                y=df_year[metric_col],
                mode="lines+markers",
                name=str(year),
                line={"color": color, "width": 3},
                hovertemplate="Mėnuo %{customdata[0]}<br>Metai %{name}<br>Reikšmė %{customdata[1]}<extra></extra>",
                customdata=customdata,
            )
        )

    fig.update_layout(
        margin=dict(l=30, r=20, t=30, b=40),
        plot_bgcolor=IC_WHITE,
        paper_bgcolor=IC_WHITE,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            tickmode="array",
            tickvals=ticks,
            ticktext=ticktext,
            title="Mėnuo",
            gridcolor="#E5E5E5",
        ),
        yaxis=dict(
            title=metric,
            gridcolor="#E5E5E5",
            rangemode="tozero",
        ),
    )

    # Build table
    pivot = aggregated.pivot_table(
        index="Mėnuo",
        columns="Metai",
        values=metric_col,
        aggfunc="sum",
        sort=False,
    )
    pivot = pivot.reindex(months)
    pivot.index = pivot.index.astype(int)

    table_numeric = pivot.copy()
    table_numeric.insert(0, "Mėnuo", table_numeric.index.astype(int).astype(str))

    totals = {}
    for year in years_sorted:
        if metric == "MARŽA %":
            subset = aggregated[aggregated["Metai"] == year]
            turnover = subset["Apyvarta"].sum()
            profit = subset["Pajamos"].sum()
            totals[str(year)] = (profit / turnover * 100.0) if turnover else None
        else:
            totals[str(year)] = aggregated.loc[aggregated["Metai"] == year, metric_col].sum()

    sum_row = {"Mėnuo": "suma"}
    table_numeric = table_numeric.rename(
        columns={year: str(year) for year in table_numeric.columns if isinstance(year, int)}
    )
    for year in years_sorted:
        sum_row[str(year)] = totals[str(year)]
    columns = [{"name": "Mėnuo", "id": "Mėnuo"}] + [
        {"name": str(year), "id": str(year)} for year in years_sorted
    ]

    data_rows = table_numeric.to_dict("records")
    data_rows.append(sum_row)

    data_formatted = []
    for row in data_rows:
        formatted = {}
        for key, value in row.items():
            if key == "Mėnuo" and value != "suma":
                formatted[key] = value
            elif key == "Mėnuo":
                formatted[key] = value
            else:
                formatted[key] = _format_table_value(metric, value)
        data_formatted.append(formatted)

    return fig, columns, data_formatted, empty_children, hidden, chart_style, table_style, status_text


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

    aggregated = compute_customer_monthly_aggregation(filters, metric)
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
    pivot = pivot.sort_index()

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
