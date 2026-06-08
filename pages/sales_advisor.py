import dash
import numpy as np
import pandas as pd
from dash import Input, Output, callback, dash_table, dcc, html
from plotly import graph_objects as go

from data.app_data import (
    COLORWAY_YEARS,
    IC_BLACK,
    FILIALAI_ADV,
    IC_GRAY,
    IC_NAVY,
    IC_WHITE,
    KATEGORIJOS,
    MENUO_LABELS_LT,
    MENUO_TVARKA,
    SEGMENTAI_ADV,
    ADVISOR_TABLE_COLS,
    PARDAVEJAI_ADV,
    format_vendor_aggregate,
    perf_timer,
    query_advisor_seller_options,
    query_advisor_vendor_aggregate,
    query_advisor_vendor_timeseries,
    YEARS_ADV,
)

dash.register_page(
    __name__,
    path="/sales-advisor",
    name="Pardavėjų patarėjas",
    title="Pardavėjų patarėjas",
)


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
    TABLE_COLS = [{"name": c, "id": c} for c in ADVISOR_TABLE_COLS]
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

    default_year = 2025 if 2025 in YEARS_ADV else (YEARS_ADV[-1] if YEARS_ADV else None)

    if default_year is not None:
        start_left_df = query_advisor_vendor_aggregate(FILIALAI_ADV, [default_year], [], "Visi", "Visos")
    else:
        start_left_df = query_advisor_vendor_aggregate(FILIALAI_ADV, YEARS_ADV[-1:], [], "Visi", "Visos")

    start_left = format_vendor_aggregate(start_left_df)

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
                                options=[{"label": f, "value": f} for f in FILIALAI_ADV],
                                value=FILIALAI_ADV,
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
                                options=[{"label": int(y), "value": int(y)} for y in YEARS_ADV],
                                value=[default_year] if default_year else YEARS_ADV[-1:],
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
                                options=[{"label": s, "value": s} for s in ["Visi"] + SEGMENTAI_ADV],
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
                                options=[{"label": k, "value": k} for k in ["Visos"] + KATEGORIJOS],
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
                                options=[{"label": s, "value": s} for s in PARDAVEJAI_ADV],
                                value=None,
                                multi=False,
                                placeholder="(nepasirinkus – rodoma tik kairė lentelė)",
                                clearable=True,
                            ),
                        ],
                        style=FILTER_ITEM,
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
    Output("adv_f_pardavejas", "options"),
    Input("adv_f_filialas", "value"),
    Input("adv_f_metai", "value"),
    Input("adv_f_menesiai", "value"),
    Input("adv_f_segmentas", "value"),
    Input("adv_f_kategorija", "value"),
)
def adv_update_seller_options(filialai, metai, menesiai, segmentas, kategorija):
    """Update seller dropdown options based on filters."""
    with perf_timer("callback.adv_update_seller_options", report="Pardavėjų patarėjas"):
        filialai = filialai or []
        metai = [int(y) for y in (metai or [])]
        menesiai = menesiai or []
        segmentas = segmentas or "Visi"
        kategorija = kategorija or "Visos"

        with perf_timer("callback.adv_update_seller_options.sql", report="seller_options"):
            opts = query_advisor_seller_options(filialai, metai, menesiai, segmentas, kategorija)

        return [{"label": s, "value": s} for s in opts]


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
)
def adv_update_tables(filialai, metai, menesiai, segmentas, kategorija, pardavejas_display):
    """Update advisor tables based on filters."""
    with perf_timer("callback.adv_update_tables", report="Pardavėjų patarėjas", seller=pardavejas_display):
        filialai = filialai or []
        metai = [int(y) for y in (metai or [])]
        menesiai = menesiai or []
        segmentas = segmentas or "Visi"
        kategorija = kategorija or "Visos"

        with perf_timer("callback.adv_update_tables.sql", report="all_sellers"):
            left_raw = query_advisor_vendor_aggregate(filialai, metai, menesiai, segmentas, kategorija)
        with perf_timer("callback.adv_update_tables.transform", report="all_sellers", rows=len(left_raw)):
            left_df = format_vendor_aggregate(left_raw)
            left_cols = [{"name": c, "id": c} for c in ADVISOR_TABLE_COLS]
            left_data = left_df.to_dict("records")

        show_right = {"flex": "1 1 50%", "minWidth": "380px", "display": "none"}
        right_cols = left_cols
        right_data = []
        title = ""

        if pardavejas_display:
            with perf_timer("callback.adv_update_tables.sql", report="selected_seller", seller=pardavejas_display):
                right_raw = query_advisor_vendor_aggregate(
                    filialai, metai, menesiai, segmentas, kategorija, pardavejas_display
                )
            with perf_timer("callback.adv_update_tables.transform", report="selected_seller", rows=len(right_raw)):
                right_df = format_vendor_aggregate(right_raw)
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
)
def update_vendor_timeseries(filialai, metai, menesiai, segmentas, kategorija, pardavejas_display, metric):
    """Create vendor time-series chart showing monthly trends across selected years."""
    try:
        hidden_style = {"display": "none", "marginTop": "20px"}
        visible_style = {"display": "block", "marginTop": "20px"}

        if not pardavejas_display:
            empty_fig = go.Figure()
            return empty_fig, hidden_style

        with perf_timer("callback.update_vendor_timeseries", report="Pardavėjų patarėjas", seller=pardavejas_display, metric=metric):
            filialai = filialai or []
            metai = [int(y) for y in (metai or [])]
            menesiai = menesiai or []
            segmentas = segmentas or "Visi"
            kategorija = kategorija or "Visos"

            with perf_timer("callback.update_vendor_timeseries.sql", seller=pardavejas_display):
                vendor_data = query_advisor_vendor_timeseries(
                    filialai, metai, menesiai, segmentas, kategorija, pardavejas_display
                )

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

        with perf_timer("callback.update_vendor_timeseries.transform", rows=len(vendor_data)):
            agg = vendor_data.copy()
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
