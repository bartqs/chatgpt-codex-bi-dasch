import dash
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
import plotly.graph_objects as go

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

YOY_COLUMN_IDS = []
if YEAR_OPTIONS:
    sorted_years = sorted(YEAR_OPTIONS)
    base_year = sorted_years[0]
    YOY_COLUMN_IDS = [f"YoY_{int(year)}" for year in sorted_years if int(year) > base_year]

YOY_STYLE_RULES = []
for yoy_id in YOY_COLUMN_IDS:
    YOY_STYLE_RULES.extend(
        [
            {
                "if": {"column_id": yoy_id, "filter_query": f"{{{yoy_id}}} contains '+'"},
                "color": GREEN,
                "fontWeight": "700",
            },
            {
                "if": {"column_id": yoy_id, "filter_query": f"{{{yoy_id}}} contains '-'"},
                "color": RED,
                "fontWeight": "700",
            },
        ]
    )


METRIC_COLUMN_MAP = {
    "APYVARTA": "Apyvarta",
    "PAJAMOS": "Pajamos",
    "KIEKIS": "Kiekis",
    "MARŽA %": "MARŽA %",
}


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
                style={"height": "700px"},
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
                ]
                + YOY_STYLE_RULES,
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


def _calculate_yoy_percent(current, previous):
    if current is None or pd.isna(current):
        return None
    if previous is None or pd.isna(previous) or previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


def _format_yoy(value):
    if value is None or pd.isna(value):
        return ""
    if abs(float(value)) < 1e-9:
        return "0.00 %"
    sign = "+" if value > 0 else ""
    return f"{sign}{float(value):.2f} %"


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
    Output("customer-table", "style_table"),
    Output("customer-table", "style_cell"),
    Output("customer-table", "style_cell_conditional"),
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

    fig = go.Figure()
    for year in years_sorted:
        df_year = aggregated[aggregated["Metai"] == year].sort_values("Mėnuo")
        color = IC_RED if year == latest_year else CUSTOMER_COLORWAY.get(year, IC_GRAY)
        month_numbers = df_year["Mėnuo"].tolist()
        month_labels = [
            MENUO_LABELS_LT[int(m) - 1] if isinstance(m, (int, float)) and 1 <= int(m) <= 12 else str(m)
            for m in month_numbers
        ]
        formatted_values = [_format_table_value(metric, v) for v in df_year[metric_col]]
        customdata = list(zip(month_labels, formatted_values))

        if chart_type == "bar":
            fig.add_trace(
                go.Bar(
                    x=month_numbers,
                    y=df_year[metric_col].tolist(),
                    name=str(year),
                    marker={
                        "color": color,
                        "opacity": 0.9 if year == latest_year else 0.75,
                        "line": {"color": color, "width": 1.2 if year == latest_year else 0.6},
                    },
                    hovertemplate=(
                        "Mėnuo %{customdata[0]}<br>Metai %{name}<br>Reikšmė %{customdata[1]}<extra></extra>"
                    ),
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
                    marker={"size": 8 if year == latest_year else 6},
                    hovertemplate=(
                        "Mėnuo %{customdata[0]}<br>Metai %{name}<br>Reikšmė %{customdata[1]}<extra></extra>"
                    ),
                    customdata=customdata,
                    legendgroup=str(year),
                )
            )

    fig.update_layout(
        height=700,
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

    # Build table with interleaved YoY columns
    columns = [{"name": "Mėnuo", "id": "Mėnuo"}]
    columns_order = ["Mėnuo"]

    month_rows_numeric = []
    for month in month_range:
        row = {"Mėnuo": str(month)}
        for year in years_sorted:
            year_key = str(year)
            raw_value = month_values.get(year, {}).get(month)
            display_value = raw_value
            if display_value is None:
                display_value = 0.0
            row[year_key] = display_value

            prev_year = year - 1
            if year != latest_year and prev_year in years_set:
                yoy_id = f"YoY_{year}"
                months_curr = months_by_year.get(year, set())
                months_prev = months_by_year.get(prev_year, set())
                yoy_value = None
                if month in months_curr and month in months_prev:
                    current_val = month_values.get(year, {}).get(month)
                    prev_val = month_values.get(prev_year, {}).get(month)
                    if metric != "MARŽA %":
                        current_val = current_val if current_val is not None else 0.0
                        prev_val = prev_val if prev_val is not None else 0.0
                    yoy_value = _calculate_yoy_percent(current_val, prev_val)
                row[yoy_id] = yoy_value

        month_rows_numeric.append(row)

    sum_row = {"Mėnuo": "suma"}
    for year in years_sorted:
        year_key = str(year)
        months_curr = months_by_year.get(year, set())
        if metric == "MARŽA %":
            turnover_total = sum(turnover_map.get(year, {}).get(m, 0.0) for m in months_curr)
            profit_total = sum(profit_map.get(year, {}).get(m, 0.0) for m in months_curr)
            total_value = (profit_total / turnover_total * 100.0) if turnover_total else 0.0
        else:
            total_value = sum(
                (month_values.get(year, {}).get(m) if month_values.get(year, {}).get(m) is not None else 0.0)
                for m in months_curr
            )
        sum_row[year_key] = total_value

        prev_year = year - 1
        if year != latest_year and prev_year in years_set:
            yoy_id = f"YoY_{year}"
            comparable_months = months_by_year.get(year, set()) & months_by_year.get(prev_year, set())
            if comparable_months:
                if metric == "MARŽA %":
                    curr_turnover = sum(turnover_map.get(year, {}).get(m, 0.0) for m in comparable_months)
                    curr_profit = sum(profit_map.get(year, {}).get(m, 0.0) for m in comparable_months)
                    prev_turnover = sum(turnover_map.get(prev_year, {}).get(m, 0.0) for m in comparable_months)
                    prev_profit = sum(profit_map.get(prev_year, {}).get(m, 0.0) for m in comparable_months)
                    curr_metric = (curr_profit / curr_turnover * 100.0) if curr_turnover else None
                    prev_metric = (prev_profit / prev_turnover * 100.0) if prev_turnover else None
                    yoy_total = _calculate_yoy_percent(curr_metric, prev_metric)
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
            else:
                yoy_total = None
            sum_row[yoy_id] = yoy_total

    numeric_rows = month_rows_numeric + [sum_row]

    for year in years_sorted:
        year_key = str(year)
        prev_year = year - 1
        if year != latest_year and prev_year in years_set:
            yoy_id = f"YoY_{year}"
            if yoy_id not in sum_row:
                sum_row[yoy_id] = None
            columns.append({"name": f"YoY ({year} vs {prev_year})", "id": yoy_id})
            columns_order.append(yoy_id)
        columns.append({"name": str(year), "id": year_key})
        columns_order.append(year_key)

    data_formatted = []
    for row in numeric_rows:
        formatted = {}
        for key in columns_order:
            if key == "Mėnuo":
                formatted[key] = row.get(key, "")
            elif key.startswith("YoY_"):
                formatted[key] = _format_yoy(row.get(key))
            else:
                formatted[key] = _format_table_value(metric, row.get(key))
        data_formatted.append(formatted)

    years_count = len(years_sorted)
    table_style_props["overflowX"] = "auto" if years_count > 4 else "hidden"
    cell_style["padding"] = "6px 8px" if years_count <= 4 else "4px 6px"

    numeric_columns = [cid for cid in columns_order if cid not in ("Mėnuo",) and not cid.startswith("YoY_")]
    yoy_columns = [cid for cid in columns_order if cid.startswith("YoY_")]

    if years_count >= 5:
        numeric_width = "80px"
        yoy_width = "85px"
    elif years_count == 4:
        numeric_width = "90px"
        yoy_width = "95px"
    elif years_count == 3:
        numeric_width = "100px"
        yoy_width = "100px"
    else:
        numeric_width = "110px"
        yoy_width = "105px"

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
    for col_id in yoy_columns:
        cell_conditional.append(
            {
                "if": {"column_id": col_id},
                "minWidth": yoy_width,
                "width": yoy_width,
                "maxWidth": yoy_width,
            }
        )

    month_width = 110
    numeric_px = int(numeric_width.replace("px", "")) if numeric_width.endswith("px") else 100
    yoy_px = int(yoy_width.replace("px", "")) if yoy_width.endswith("px") else 90
    total_px = month_width + numeric_px * len(numeric_columns) + yoy_px * len(yoy_columns)
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
