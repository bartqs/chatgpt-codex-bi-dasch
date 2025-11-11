import dash
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html, ctx
from plotly import graph_objects as go

from data.app_data import (
    COLORWAY_YEARS,
    IC_BLACK,
    IC_GRAY,
    IC_NAVY,
    IC_WHITE,
    MENUO_LABELS_LT,
    MENUO_TVARKA,
    aggregate_by_vendor,
    filter_dataframe,
    get_advisor_categories,
    get_advisor_context,
    get_advisor_data,
    get_advisor_filialai,
    get_advisor_segments,
    get_advisor_sellers,
    get_advisor_years,
    reset_data_caches,
)

dash.register_page(
    __name__,
    path="/sales-advisor",
    name="Pardavėjų patarėjas",
    title="Pardavėjų patarėjas",
)


REFRESH_BUTTON_ID = "adv-refresh-button"


def _maybe_reset_advisor_caches() -> None:
    if ctx.triggered_id == REFRESH_BUTTON_ID:
        reset_data_caches()


def layout():
    """Render the sales advisor page layout (identical to original tab)."""
    FILTER_ITEM = {"flex": "1 1 240px", "minWidth": "240px", "maxWidth": "100%"}
    FILTER_ROW = {
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "10px",
        "alignItems": "stretch",
        "margin": "6px 0 14px 0",
    }
    TABLE_COLS = [{"name": c, "id": c} for c in ["Gamintojas", "Apyvarta", "Pajamos", "Marža %", "Kiekis"]]
    TBL_PROPS = dict(
        style_table={"overflowX": "auto", "border": f"1px solid {IC_GRAY}", "borderRadius": "10px", "maxHeight": "70vh"},
        style_header={"backgroundColor": IC_NAVY, "color": IC_WHITE, "fontWeight": "700"},
        style_cell={"padding": "6px 8px", "fontFamily": "Arial", "fontSize": "13px", "whiteSpace": "nowrap"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
            {"if": {"column_id": ["Apyvarta", "Pajamos", "Marža %", "Kiekis"]}, "textAlign": "right"},
            {"if": {"filter_query": '{Gamintojas} = "Iš viso"'}, "fontWeight": "700"},
        ],
        page_size=20,
        sort_action="none",
    )

    advisor_df, meta = get_advisor_context()
    filialas_options = meta["filialai"]
    year_options = meta["years"]
    segment_options = ["Visi"] + meta["segments"]
    category_options = ["Visos"] + meta["categories"]
    seller_options = meta["sellers"]

    default_year = year_options[-1] if year_options else None

    if default_year is not None:
        start_left_df = advisor_df[advisor_df["Metai"] == default_year]
        if start_left_df.empty and year_options:
            start_left_df = advisor_df[advisor_df["Metai"] == year_options[-1]]
    else:
        start_left_df = advisor_df.copy()

    start_left = aggregate_by_vendor(start_left_df)

    return html.Div(
        [
            html.Div(
                "Pardavėjų patarėjas",
                style={"fontSize": 20, "fontWeight": 800, "color": IC_NAVY, "margin": "12px 0"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Filialas"),
                            dcc.Dropdown(
                                id="adv_f_filialas",
                                options=[{"label": f, "value": f} for f in filialas_options],
                                value=filialas_options,
                                multi=True,
                                clearable=False,
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Label("Metai"),
                            dcc.Dropdown(
                                id="adv_f_metai",
                                options=[{"label": int(y), "value": int(y)} for y in year_options],
                                value=[default_year] if default_year else year_options[-1:],
                                multi=True,
                                clearable=False,
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Label("Mėnesiai"),
                            dcc.Dropdown(
                                id="adv_f_menesiai",
                                options=[{"label": f"M-{m:02d}", "value": f"M-{m:02d}"} for m in range(1, 13)],
                                value=[],
                                multi=True,
                                placeholder="(tušti = visi mėnesiai)",
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Label("Segmentas"),
                            dcc.Dropdown(
                                id="adv_f_segmentas",
                                options=[{"label": s, "value": s} for s in segment_options],
                                value="Visi",
                                clearable=False,
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Label("Kategorija"),
                            dcc.Dropdown(
                                id="adv_f_kategorija",
                                options=[{"label": k, "value": k} for k in category_options],
                                value="Visos",
                                clearable=False,
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Label("Pardavėjas"),
                            dcc.Dropdown(
                                id="adv_f_pardavejas",
                                options=[{"label": s, "value": s} for s in seller_options],
                                value=None,
                                multi=False,
                                placeholder="(nepasirinkus – rodoma tik kairė lentelė)",
                                clearable=True,
                            ),
                        ],
                        style=FILTER_ITEM,
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Atnaujinti duomenis",
                                id=REFRESH_BUTTON_ID,
                                n_clicks=0,
                                style={
                                    "padding": "8px 16px",
                                    "border": f"1px solid {IC_NAVY}",
                                    "background": IC_WHITE,
                                    "color": IC_NAVY,
                                    "borderRadius": "8px",
                                    "fontWeight": 600,
                                },
                            )
                        ],
                        style={
                            "flex": "0 0 auto",
                            "display": "flex",
                            "flexDirection": "column",
                            "justifyContent": "flex-end",
                        },
                    ),
                ],
                style=FILTER_ROW,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Bendri rezultatai (visi pardavėjai)",
                                style={"fontWeight": 700, "color": IC_NAVY, "margin": "0 0 6px 2px"},
                            ),
                            dash_table.DataTable(
                                id="adv_tbl_bendra",
                                columns=TABLE_COLS,
                                data=start_left.to_dict("records"),
                                **TBL_PROPS,
                            ),
                        ],
                        style={"flex": "1 1 50%", "minWidth": "380px"},
                    ),
                    html.Div(
                        [
                            html.Div(
                                id="adv_seller_title",
                                style={"fontWeight": 700, "color": IC_NAVY, "margin": "0 0 6px 2px"},
                            ),
                            dash_table.DataTable(
                                id="adv_tbl_seller",
                                columns=TABLE_COLS,
                                data=[],
                                **TBL_PROPS,
                            ),
                        ],
                        id="adv_seller_card",
                        style={"flex": "1 1 50%", "minWidth": "380px", "display": "none"},
                    ),
                ],
                style={"display": "flex", "flexDirection": "row", "gap": "12px"},
            ),
            html.Div(
                id="div_vendor_chart_section",
                children=[
                    html.Div(
                        [
                            html.Div(
                                "Pardavėjo dinamika",
                                style={"fontWeight": 700, "color": IC_NAVY, "display": "inline-block", "marginRight": "20px"},
                            ),
                            dcc.RadioItems(
                                id="metric_switch_vendor",
                                options=[
                                    {"label": "Apyvarta", "value": "Apyvarta"},
                                    {"label": "Pajamos", "value": "Pajamos"},
                                    {"label": "Marža %", "value": "Marža %"},
                                    {"label": "Kiekis", "value": "Kiekis"},
                                ],
                                value="Apyvarta",
                                inline=True,
                                style={"display": "inline-block"},
                                labelStyle={"marginRight": "15px", "cursor": "pointer"},
                            ),
                        ],
                        style={"margin": "20px 0 10px 0"},
                    ),
                    dcc.Graph(
                        id="fig_vendor_timeseries",
                        config={"displaylogo": False},
                        style={"height": "450px"},
                    ),
                ],
                style={"display": "none", "marginTop": "20px"},
            ),
        ],
        style={"padding": "10px 14px"},
    )


@callback(
    Output("adv_f_filialas", "options"),
    Output("adv_f_filialas", "value"),
    Output("adv_f_metai", "options"),
    Output("adv_f_metai", "value"),
    Output("adv_f_segmentas", "options"),
    Output("adv_f_segmentas", "value"),
    Output("adv_f_kategorija", "options"),
    Output("adv_f_kategorija", "value"),
    Input(REFRESH_BUTTON_ID, "n_clicks"),
    State("adv_f_filialas", "value"),
    State("adv_f_metai", "value"),
    State("adv_f_segmentas", "value"),
    State("adv_f_kategorija", "value"),
    prevent_initial_call=False,
)
def refresh_advisor_filters(
    _refresh_clicks,
    current_filialai,
    current_years,
    current_segment,
    current_category,
):
    _maybe_reset_advisor_caches()

    _, meta = get_advisor_context()

    filialas_opts = meta["filialai"]
    year_opts = meta["years"]
    segment_opts = ["Visi"] + meta["segments"]
    category_opts = ["Visos"] + meta["categories"]

    filialas_option_dicts = [{"label": f, "value": f} for f in filialas_opts]
    year_option_dicts = [{"label": int(y), "value": int(y)} for y in year_opts]
    segment_option_dicts = [{"label": s, "value": s} for s in segment_opts]
    category_option_dicts = [{"label": k, "value": k} for k in category_opts]

    valid_filialas = {opt["value"] for opt in filialas_option_dicts}
    valid_years = {opt["value"] for opt in year_option_dicts}
    valid_segments = {opt["value"] for opt in segment_option_dicts}
    valid_categories = {opt["value"] for opt in category_option_dicts}

    default_year = year_opts[-1] if year_opts else None

    if ctx.triggered_id is None:
        filialas_value = filialas_opts
        metai_value = [default_year] if default_year is not None else []
        segment_value = "Visi"
        category_value = "Visos"
    else:
        filialas_value = [f for f in (current_filialai or []) if f in valid_filialas] or filialas_opts
        metai_candidates = [int(y) for y in (current_years or []) if int(y) in valid_years]
        metai_value = metai_candidates or ([default_year] if default_year is not None else [])
        segment_value = current_segment if current_segment in valid_segments else "Visi"
        category_value = current_category if current_category in valid_categories else "Visos"

    return (
        filialas_option_dicts,
        filialas_value,
        year_option_dicts,
        metai_value,
        segment_option_dicts,
        segment_value,
        category_option_dicts,
        category_value,
    )


@callback(
    Output("adv_f_pardavejas", "options"),
    Output("adv_f_pardavejas", "value"),
    Input("adv_f_filialas", "value"),
    Input("adv_f_metai", "value"),
    Input("adv_f_menesiai", "value"),
    Input("adv_f_segmentas", "value"),
    Input("adv_f_kategorija", "value"),
    Input(REFRESH_BUTTON_ID, "n_clicks"),
    State("adv_f_pardavejas", "value"),
)
def adv_update_seller_options(
    filialai,
    metai,
    menesiai,
    segmentas,
    kategorija,
    _refresh_clicks,
    current_seller,
):
    """Update seller dropdown options based on filters."""
    _maybe_reset_advisor_caches()

    df = get_advisor_data()

    filialai = filialai or []
    metai = [int(y) for y in (metai or [])]
    menesiai = menesiai or []
    segmentas = segmentas or "Visi"
    kategorija = kategorija or "Visos"

    d = filter_dataframe(df, filialai=filialai, years=metai, months=menesiai)

    if segmentas != "Visi":
        d = d[d["Segmentas"] == segmentas]
    if kategorija != "Visos":
        d = d[d["Kategorija"] == kategorija]

    opts = sorted(d["Pardavejas_display"].dropna().unique().tolist())
    option_dicts = [{"label": s, "value": s} for s in opts]

    valid_values = {opt["value"] for opt in option_dicts}
    seller_value = current_seller if current_seller in valid_values else None

    return option_dicts, seller_value


@callback(
    Output("adv_tbl_bendra", "columns"),
    Output("adv_tbl_bendra", "data"),
    Output("adv_tbl_seller", "columns"),
    Output("adv_tbl_seller", "data"),
    Output("adv_seller_card", "style"),
    Output("adv_seller_title", "children"),
    Input("adv_f_filialas", "value"),
    Input("adv_f_metai", "value"),
    Input("adv_f_menesiai", "value"),
    Input("adv_f_segmentas", "value"),
    Input("adv_f_kategorija", "value"),
    Input("adv_f_pardavejas", "value"),
    Input(REFRESH_BUTTON_ID, "n_clicks"),
)
def adv_update_tables(
    filialai,
    metai,
    menesiai,
    segmentas,
    kategorija,
    pardavejas_display,
    _refresh_clicks,
):
    """Update advisor tables based on filters."""
    _maybe_reset_advisor_caches()

    df = get_advisor_data()

    filialai = filialai or []
    metai = [int(y) for y in (metai or [])]
    menesiai = menesiai or []
    segmentas = segmentas or "Visi"
    kategorija = kategorija or "Visos"

    d = filter_dataframe(df, filialai=filialai, years=metai, months=menesiai)

    if segmentas != "Visi":
        d = d[d["Segmentas"] == segmentas]
    if kategorija != "Visos":
        d = d[d["Kategorija"] == kategorija]

    left_df = aggregate_by_vendor(d)
    left_cols = [{"name": c, "id": c} for c in ["Gamintojas", "Apyvarta", "Pajamos", "Marža %", "Kiekis"]]
    left_data = left_df.to_dict("records")

    show_right = {"flex": "1 1 50%", "minWidth": "380px", "display": "none"}
    right_cols = left_cols
    right_data = []
    title = ""

    if pardavejas_display:
        internal = "(ND)" if pardavejas_display == "E-commerce" else pardavejas_display
        sdd = d[d["Pardavejas"].fillna("").str.strip() == internal]
        right_df = aggregate_by_vendor(sdd)
        right_data = right_df.to_dict("records")
        show_right = {"flex": "1 1 50%", "minWidth": "380px", "display": "block"}
        title = f"Pasirinkto pardavėjo rezultatai – {pardavejas_display}"

    return left_cols, left_data, right_cols, right_data, show_right, title


@callback(
    Output("fig_vendor_timeseries", "figure"),
    Output("div_vendor_chart_section", "style"),
    Input("adv_f_filialas", "value"),
    Input("adv_f_metai", "value"),
    Input("adv_f_menesiai", "value"),
    Input("adv_f_segmentas", "value"),
    Input("adv_f_kategorija", "value"),
    Input("adv_f_pardavejas", "value"),
    Input("metric_switch_vendor", "value"),
    Input(REFRESH_BUTTON_ID, "n_clicks"),
)
def update_vendor_timeseries(
    filialai,
    metai,
    menesiai,
    segmentas,
    kategorija,
    pardavejas_display,
    metric,
    _refresh_clicks,
):
    """Create vendor time-series chart showing monthly trends across selected years."""
    try:
        hidden_style = {"display": "none", "marginTop": "20px"}
        visible_style = {"display": "block", "marginTop": "20px"}

        if not pardavejas_display:
            empty_fig = go.Figure()
            return empty_fig, hidden_style

        _maybe_reset_advisor_caches()

        df = get_advisor_data()

        filialai = filialai or []
        metai = [int(y) for y in (metai or [])]
        menesiai = menesiai or []
        segmentas = segmentas or "Visi"
        kategorija = kategorija or "Visos"

        d = filter_dataframe(df, filialai=filialai, years=metai, months=menesiai)

        if segmentas != "Visi":
            d = d[d["Segmentas"] == segmentas]
        if kategorija != "Visos":
            d = d[d["Kategorija"] == kategorija]

        internal = "(ND)" if pardavejas_display == "E-commerce" else pardavejas_display
        vendor_data = d[d["Pardavejas"].fillna("").str.strip() == internal]

        def create_empty_figure(message="No data available"):
            empty_fig = go.Figure()
            empty_fig.update_layout(
                xaxis=dict(
                    tickmode="array",
                    tickvals=MENUO_TVARKA,
                    ticktext=MENUO_LABELS_LT,
                    showgrid=False,
                ),
                yaxis=dict(showgrid=False),
                annotations=[
                    {
                        "text": message,
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "font": {"size": 14, "color": IC_GRAY},
                    }
                ],
                height=450,
                margin=dict(l=70, r=30, t=50, b=50),
                plot_bgcolor=IC_WHITE,
                paper_bgcolor=IC_WHITE,
            )
            return empty_fig

        if vendor_data.empty:
            return create_empty_figure("Nėra duomenų pasirinktam pardavėjui"), visible_style

        vendor_data_copy = vendor_data.copy()
        vendor_data_copy["Menuo"] = vendor_data_copy["Menuo"].astype(str)

        agg = vendor_data_copy.groupby(["Metai", "Menuo"], as_index=False).agg(
            {"Apyvarta": "sum", "Pajamos": "sum", "Kiekis": "sum"}
        )

        agg["Marža %"] = np.where(
            agg["Apyvarta"] != 0,
            (agg["Pajamos"] / agg["Apyvarta"]) * 100.0,
            np.nan,
        )

        years_in_data = sorted(agg["Metai"].unique())

        if not years_in_data:
            return create_empty_figure("Nėra duomenų pasirinktam pardavėjui"), visible_style

        valid_data = agg[metric].notna()
        if not valid_data.any():
            return create_empty_figure(f"Nėra duomenų metrikui: {metric}"), visible_style

        fig = go.Figure()
        has_valid_traces = False

        latest_year = max(int(y) for y in years_in_data)

        for year in years_in_data:
            year_int = int(year)
            year_data = agg[agg["Metai"] == year_int].copy()
            year_data["Menuo"] = year_data["Menuo"].astype(str)

            year_pivot = year_data.set_index("Menuo")[metric].reindex(MENUO_TVARKA)

            if year_pivot.notna().sum() == 0:
                continue

            has_valid_traces = True

            is_latest_year = year_int == latest_year
            color = "#E30613" if is_latest_year else COLORWAY_YEARS.get(year_int, "#7F7F7F")
            line_width = 4 if is_latest_year else 2.5

            hover_texts = []
            data_labels = []

            for idx, month in enumerate(MENUO_TVARKA):
                val = year_pivot.loc[month] if month in year_pivot.index else np.nan
                month_label = MENUO_LABELS_LT[idx]

                if pd.isna(val):
                    hover_texts.append(f"{month_label}: —")
                    data_labels.append("")
                    continue

                if metric == "Marža %":
                    formatted_val = f"{val:.2f} %"
                elif metric in ["Apyvarta", "Pajamos"]:
                    formatted_val = f"{int(round(val)):,}".replace(",", " ") + " €"
                else:
                    formatted_val = f"{int(round(val)):,}".replace(",", " ")

                hover_texts.append(f"{month_label}: {formatted_val}")
                data_labels.append(formatted_val)

            fig.add_trace(
                go.Scatter(
                    x=list(range(12)),
                    y=year_pivot.values,
                    mode="lines+markers+text",
                    name=str(year_int),
                    line=dict(color=color, width=line_width),
                    marker=dict(size=7, color=color),
                    text=data_labels,
                    textposition="top center",
                    textfont=dict(size=11, color=color),
                    hovertext=hover_texts,
                    hovertemplate="%{hovertext}<extra></extra>",
                    connectgaps=False,
                )
            )

        if not has_valid_traces:
            return create_empty_figure(f"Nėra duomenų metrikui: {metric}"), visible_style

        fig.update_xaxes(
            tickmode="array",
            tickvals=list(range(12)),
            ticktext=MENUO_LABELS_LT,
            showgrid=True,
            gridcolor="rgba(200, 200, 200, 0.2)",
        )

        if metric == "Marža %":
            fig.update_yaxes(
                title=dict(text="Marža %", font=dict(size=12, color=IC_NAVY, family="Arial")),
                ticksuffix="%",
                tickformat=".1f",
                showgrid=True,
                gridwidth=1,
                gridcolor="rgba(178, 178, 178, 0.2)",
                showline=True,
                linewidth=2,
                linecolor=IC_GRAY,
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="rgba(0, 47, 108, 0.3)",
                tickfont=dict(size=11, color=IC_BLACK, family="Arial"),
                autorange=True,
                rangemode="normal",
            )
        elif metric in ["Apyvarta", "Pajamos"]:
            fig.update_yaxes(
                title=dict(text=f"{metric} (€)", font=dict(size=12, color=IC_NAVY, family="Arial")),
                tickformat=",",
                separatethousands=True,
                showgrid=True,
                gridwidth=1,
                gridcolor="rgba(178, 178, 178, 0.2)",
                showline=True,
                linewidth=2,
                linecolor=IC_GRAY,
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="rgba(0, 47, 108, 0.3)",
                tickfont=dict(size=11, color=IC_BLACK, family="Arial"),
                autorange=True,
                rangemode="normal",
            )
        else:  # Kiekis
            fig.update_yaxes(
                title=dict(text="Kiekis", font=dict(size=12, color=IC_NAVY, family="Arial")),
                tickformat=",",
                separatethousands=True,
                showgrid=True,
                gridwidth=1,
                gridcolor="rgba(178, 178, 178, 0.2)",
                showline=True,
                linewidth=2,
                linecolor=IC_GRAY,
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="rgba(0, 47, 108, 0.3)",
                tickfont=dict(size=11, color=IC_BLACK, family="Arial"),
                autorange=True,
                rangemode="normal",
            )

        fig.update_layout(
            height=450,
            margin=dict(l=60, r=30, t=50, b=50),
            plot_bgcolor="#FAFBFC",
            paper_bgcolor=IC_WHITE,
            hovermode="x",
            title=dict(
                text=f"<b>{pardavejas_display}</b> – {metric}",
                font=dict(size=14, color=IC_NAVY),
                x=0.02,
                xanchor="left",
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        )

        return fig, visible_style

    except Exception as e:  # pragma: no cover - defensive logging as in original
        print(f"Error in update_vendor_timeseries: {str(e)}")
        import traceback

        traceback.print_exc()

        error_fig = go.Figure()
        error_fig.add_annotation(
            text=f"Klaida: {str(e)[:100]}",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=12, color="#C62828"),
        )
        error_fig.update_layout(height=450, xaxis=dict(visible=False), yaxis=dict(visible=False))
        return error_fig, {"display": "block", "marginTop": "20px"}
