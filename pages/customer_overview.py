"""Klientų apžvalgos puslapis.

Šis puslapis rekonstruoja pradinę ataskaitą, kuri buvo prieinama prieš
"Product" puslapio pridėjimą. Jame pateikiama aukšto lygio klientų (segmentų)
apžvalga bei mėnesinė dinamika pasirinktam segmentui.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import dash
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, dash_table, dcc, html
from plotly import graph_objects as go
from plotly.subplots import make_subplots

from data.app_data import (
    FILIALAI_ADV,
    IC_BG,
    IC_GRAY,
    IC_NAVY,
    IC_RED,
    IC_WHITE,
    MENUO_LABELS_LT,
    MENUO_TVARKA,
    df_adv,
)


dash.register_page(
    __name__,
    path="/customers",
    name="Klientų apžvalga",
    title="Klientų apžvalga",
)


def _format_eur(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    return f"{int(round(value)):,} €".replace(",", " ")


def _format_qty(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    return f"{int(round(value)):,}".replace(",", " ")


def _format_pct(value: Optional[float]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    return f"{value:.1f} %"


def _aggregate_summary(year: int, branches: Tuple[str, ...]) -> pd.DataFrame:
    data = df_adv.copy()

    if year:
        data = data[data["Metai"] == year]

    if branches:
        data = data[data["Filialas"].isin(branches)]

    if data.empty:
        return pd.DataFrame(columns=["Segmentas", "Apyvarta", "Pajamos", "Kiekis", "Marža %"])

    grouped = (
        data.groupby("Segmentas", as_index=False)
        .agg({"Apyvarta": "sum", "Pajamos": "sum", "Kiekis": "sum"})
        .sort_values("Apyvarta", ascending=False)
    )

    grouped["Marža %"] = np.where(
        grouped["Apyvarta"] != 0,
        (grouped["Pajamos"] / grouped["Apyvarta"]) * 100.0,
        np.nan,
    )

    total = grouped[["Apyvarta", "Pajamos", "Kiekis"]].sum()
    total_margin = (total["Pajamos"] / total["Apyvarta"] * 100.0) if total["Apyvarta"] else np.nan

    total_row = pd.DataFrame(
        {
            "Segmentas": ["Iš viso"],
            "Apyvarta": [total["Apyvarta"]],
            "Pajamos": [total["Pajamos"]],
            "Kiekis": [total["Kiekis"]],
            "Marža %": [total_margin],
        }
    )

    return pd.concat([grouped, total_row], ignore_index=True)


def _aggregate_monthly(
    year: int,
    branches: Tuple[str, ...],
    segment: str,
) -> pd.DataFrame:
    data = df_adv.copy()

    if year:
        data = data[data["Metai"] == year]

    if branches:
        data = data[data["Filialas"].isin(branches)]

    data = data[data["Segmentas"] == segment]

    if data.empty:
        return pd.DataFrame(columns=["Menuo", "Apyvarta", "Pajamos", "Kiekis", "Marža %"])

    grouped = (
        data.groupby("Menuo", as_index=False)
        .agg({"Apyvarta": "sum", "Pajamos": "sum", "Kiekis": "sum"})
        .set_index("Menuo")
        .reindex(MENUO_TVARKA)
        .dropna(how="all")
        .reset_index()
    )

    grouped["Marža %"] = np.where(
        grouped["Apyvarta"].fillna(0) != 0,
        (grouped["Pajamos"].fillna(0) / grouped["Apyvarta"].fillna(0)) * 100.0,
        np.nan,
    )

    grouped = grouped.dropna(subset=["Apyvarta", "Pajamos", "Kiekis"], how="all")

    return grouped


def layout() -> html.Div:
    default_year = int(df_adv["Metai"].max()) if not df_adv.empty else None
    default_branches = FILIALAI_ADV if FILIALAI_ADV else []

    filter_box_style = {
        "display": "flex",
        "flexWrap": "wrap",
        "gap": "12px",
        "marginBottom": "18px",
    }

    dropdown_style = {"width": "200px"}

    table_columns = [
        {"name": "Segmentas", "id": "Segmentas"},
        {"name": "Apyvarta", "id": "Apyvarta_fmt"},
        {"name": "Pajamos", "id": "Pajamos_fmt"},
        {"name": "Marža %", "id": "Marza_fmt"},
        {"name": "Kiekis", "id": "Kiekis_fmt"},
    ]

    return html.Div(
        [
            html.Div(
                "Klientų apžvalga",
                style={"fontSize": 22, "fontWeight": 800, "color": IC_NAVY, "margin": "12px 0"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Metai"),
                            dcc.Dropdown(
                                id="customer-year",
                                options=[
                                    {"label": int(y), "value": int(y)}
                                    for y in sorted(df_adv["Metai"].dropna().unique())
                                ],
                                value=default_year,
                                clearable=False,
                                style=dropdown_style,
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            html.Label("Filialas"),
                            dcc.Dropdown(
                                id="customer-branches",
                                options=[{"label": b, "value": b} for b in FILIALAI_ADV],
                                value=default_branches,
                                multi=True,
                                clearable=False,
                                style={"minWidth": "220px"},
                            ),
                        ]
                    ),
                ],
                style=filter_box_style,
            ),
            dash_table.DataTable(
                id="customer-table",
                columns=table_columns,
                data=[],
                page_size=15,
                style_table={
                    "overflowX": "auto",
                    "border": f"1px solid {IC_GRAY}",
                    "borderRadius": "10px",
                    "background": IC_WHITE,
                },
                style_header={"backgroundColor": IC_NAVY, "color": IC_WHITE, "fontWeight": "700"},
                style_cell={
                    "padding": "6px 8px",
                    "fontFamily": "Arial",
                    "fontSize": "13px",
                    "whiteSpace": "nowrap",
                },
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "#FAFBFC"},
                    {
                        "if": {"filter_query": '{Segmentas} = "Iš viso"'},
                        "fontWeight": "700",
                    },
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
                sort_action="native",
                row_selectable="single",
            ),
            html.Div(id="customer-empty", style={"marginTop": "20px", "color": IC_GRAY}),
            dcc.Graph(id="customer-chart", style={"marginTop": "20px", "background": IC_WHITE}),
        ],
        style={"background": IC_BG, "padding": "20px"},
    )


def _prepare_table_records(df_summary: pd.DataFrame) -> List[Dict[str, object]]:
    if df_summary.empty:
        return []

    records: List[Dict[str, object]] = []
    for _, row in df_summary.iterrows():
        records.append(
            {
                "Segmentas": row["Segmentas"],
                "Apyvarta_fmt": _format_eur(row["Apyvarta"]),
                "Pajamos_fmt": _format_eur(row["Pajamos"]),
                "Kiekis_fmt": _format_qty(row["Kiekis"]),
                "Marza_fmt": _format_pct(row["Marža %"]),
                "Apyvarta_raw": float(row["Apyvarta"]) if pd.notna(row["Apyvarta"]) else None,
                "Pajamos_raw": float(row["Pajamos"]) if pd.notna(row["Pajamos"]) else None,
                "Kiekis_raw": float(row["Kiekis"]) if pd.notna(row["Kiekis"]) else None,
                "Marza_raw": float(row["Marža %"]) if pd.notna(row["Marža %"]) else None,
            }
        )

    return records


@callback(
    Output("customer-table", "data"),
    Output("customer-table", "selected_rows"),
    Output("customer-empty", "children"),
    Input("customer-year", "value"),
    Input("customer-branches", "value"),
)
def update_customer_table(year: Optional[int], branches: Optional[List[str]]):
    if year is None:
        return [], [], "Metai nepasirinkti."

    branches_tuple: Tuple[str, ...] = tuple(branches) if branches else tuple()
    summary = _aggregate_summary(year, branches_tuple)

    if summary.empty:
        return [], [], "Nėra duomenų su pasirinktais filtrais."

    records = _prepare_table_records(summary)

    return records, ([0] if records else []), ""


@callback(
    Output("customer-chart", "figure"),
    Output("customer-chart", "style"),
    Output("customer-empty", "style"),
    Input("customer-table", "selected_rows"),
    State("customer-table", "data"),
    State("customer-year", "value"),
    State("customer-branches", "value"),
)
def update_customer_chart(
    selected_rows: Optional[List[int]],
    table_data: Optional[List[Dict[str, object]]],
    year: Optional[int],
    branches: Optional[List[str]],
):
    default_empty_style = {"marginTop": "20px", "color": IC_GRAY}

    if not table_data or not selected_rows:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=IC_WHITE,
            plot_bgcolor=IC_WHITE,
            annotations=[
                {
                    "text": "Pasirinkite segmentą lentelėje",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"color": IC_GRAY, "size": 14},
                }
            ],
        )
        return fig, {"display": "none"}, default_empty_style

    row_index = selected_rows[0]
    if row_index >= len(table_data):
        row_index = 0

    segment = table_data[row_index]["Segmentas"]

    if segment == "Iš viso":
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=IC_WHITE,
            plot_bgcolor=IC_WHITE,
            annotations=[
                {
                    "text": "Pasirinkite konkretų segmentą",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"color": IC_GRAY, "size": 14},
                }
            ],
        )
        return fig, {"display": "none"}, default_empty_style

    branches_tuple: Tuple[str, ...] = tuple(branches) if branches else tuple()
    monthly = _aggregate_monthly(year, branches_tuple, segment)

    if monthly.empty:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=IC_WHITE,
            plot_bgcolor=IC_WHITE,
            annotations=[
                {
                    "text": "Pasirinktam segmentui nėra duomenų",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"color": IC_GRAY, "size": 14},
                }
            ],
        )
        return fig, {"display": "none"}, default_empty_style

    months = monthly["Menuo"].tolist()
    month_labels = [MENUO_LABELS_LT[int(m.split("-")[1]) - 1] for m in months]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(
        x=month_labels,
        y=monthly["Apyvarta"].fillna(0),
        name="Apyvarta",
        marker_color=IC_NAVY,
        secondary_y=False,
    )
    fig.add_scatter(
        x=month_labels,
        y=monthly["Marža %"],
        name="Marža %",
        mode="lines+markers",
        marker=dict(color=IC_RED),
        line=dict(color=IC_RED),
        secondary_y=True,
    )
    fig.add_scatter(
        x=month_labels,
        y=monthly["Kiekis"].fillna(0),
        name="Kiekis",
        mode="lines+markers",
        marker=dict(color="#1B998B"),
        line=dict(color="#1B998B"),
        secondary_y=True,
    )

    fig.update_layout(
        paper_bgcolor=IC_WHITE,
        plot_bgcolor=IC_WHITE,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=dict(text=f"{segment} – mėnesinė dinamika", font=dict(color=IC_NAVY, size=16)),
    )
    fig.update_yaxes(title_text="Apyvarta (€)", secondary_y=False)
    fig.update_yaxes(title_text="Marža % / Kiekis", secondary_y=True)

    return fig, {"display": "block"}, {"display": "none"}

