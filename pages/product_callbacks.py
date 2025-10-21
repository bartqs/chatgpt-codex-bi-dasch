"""Callbacks and data loading for the Product Analysis page."""

from __future__ import annotations

import math
import time
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, no_update
from plotly import graph_objects as go
from sqlalchemy import text

from data.app_data import IC_GRAY, engine, get_columns, pick_col

from .product_page import PAGE_ID_PREFIX


_CACHE_TTL_SECONDS = 120
_TABLE_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}
_CHART_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}


def _cache_get(cache: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]], key: Tuple[Any, ...]) -> Optional[pd.DataFrame]:
    entry = cache.get(key)
    if not entry:
        return None

    timestamp, value = entry
    if time.time() - timestamp > _CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None

    return value.copy(deep=False)


def _cache_set(cache: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]], key: Tuple[Any, ...], value: pd.DataFrame) -> None:
    cache[key] = (time.time(), value.copy(deep=False))


def _build_in_clause(column: str, values: Iterable[Any], param_prefix: str) -> Tuple[str, Dict[str, Any]]:
    """Build a parameterized IN clause compatible with MySQL without expanding params."""

    placeholders: List[str] = []
    params: Dict[str, Any] = {}
    for idx, value in enumerate(values):
        param_name = f"{param_prefix}_{idx}"
        placeholders.append(f":{param_name}")
        params[param_name] = value

    if not placeholders:
        # No values -> return an always-false clause to avoid SQL syntax errors.
        return "1 = 0", {}

    clause = f"{column} IN ({', '.join(placeholders)})"
    return clause, params


@lru_cache(maxsize=1)
def _product_columns() -> Dict[str, str]:
    """Resolve database column names used by the product page queries."""

    cols = get_columns()
    return {
        "year": pick_col(cols, ["Year", "Year [Name] PE-Y01", "Metai"]),
        "month": pick_col(cols, ["Month", "Month [Short name] PE-M02", "Menuo", "Mėnuo"]),
        "branch": pick_col(cols, ["Filialas", "Branch", "Filialas [Name]"]),
        "manufacturer": pick_col(
            cols,
            ["Gamintojas (pavad)", "Gamintojas", "Gamintojas [Name]", "Manufacturer"],
        ),
        "turnover": pick_col(cols, ["APYVARTA", "Apyvarta", "Turnover", "Turnover €"]),
        "revenue": pick_col(cols, ["PAJAMOS", "Pajamos", "Revenue", "Pelnas"]),
        "quantity": pick_col(cols, ["KIEKIS", "Kiekis", "Quantity"]),
    }


def _require_column(name: str) -> str:
    column = _product_columns().get(name)
    if not column:
        raise RuntimeError(f"Missing required column mapping for '{name}'")
    return column


@lru_cache(maxsize=1)
def _manufacturer_expr() -> str:
    column = _require_column("manufacturer")
    return f"COALESCE({column}, 'Nežinomas gamintojas')"


@lru_cache(maxsize=1)
def _all_manufacturers() -> Tuple[str, ...]:
    stmt = text(
        f"""
        SELECT DISTINCT {_manufacturer_expr()} AS Gamintojas
        FROM sales
        ORDER BY Gamintojas
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)

    return tuple(df["Gamintojas"].dropna().astype(str))


def _format_currency(value: float) -> str:
    if pd.isna(value):
        return "0 €"
    formatted = f"{value:,.0f}".replace(",", " ")
    return f"{formatted} €"


def _format_quantity(value: float) -> str:
    if pd.isna(value):
        return "0"
    return f"{int(round(value)):,}".replace(",", " ")


def _format_margin(value: float) -> str:
    if pd.isna(value):
        return "0.00 %"
    return f"{value:.2f} %"


def _month_to_number(value: Any) -> Optional[int]:
    if pd.isna(value):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)) and not math.isnan(value):
        return int(value)
    s = str(value)
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        return int(digits)
    return None


def _normalized_branches(branches: Optional[Sequence[str]]) -> List[str]:
    if not branches:
        return []
    if isinstance(branches, str):
        return [branches]
    return [str(b) for b in branches if b]


def _fetch_table_data(year: Optional[int], branches: Sequence[str]) -> pd.DataFrame:
    if not year or not branches:
        return pd.DataFrame(
            columns=["Manufacturer", "Apyvarta", "Pajamos", "Kiekis", "Marža %"]
        )

    key = ("table", int(year), tuple(sorted(branches)))
    cached = _cache_get(_TABLE_CACHE, key)
    if cached is not None:
        return cached

    year_col = _require_column("year")
    branch_col = _require_column("branch")
    turnover_col = _require_column("turnover")
    revenue_col = _require_column("revenue")
    quantity_col = _require_column("quantity")
    manufacturer_expr = _manufacturer_expr()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "branch")

    stmt = text(
        f"""
        SELECT
            {manufacturer_expr} AS Manufacturer,
            SUM(CAST({turnover_col} AS DECIMAL(18,2))) AS Apyvarta,
            SUM(CAST({revenue_col} AS DECIMAL(18,2))) AS Pajamos,
            SUM(CAST({quantity_col} AS DECIMAL(18,2))) AS Kiekis
        FROM sales
        WHERE CAST({year_col} AS UNSIGNED) = :year
          AND {branch_clause}
        GROUP BY {manufacturer_expr}
        """
    )

    params: Dict[str, Any] = {"year": int(year), **branch_params}

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        df["Marža %"] = pd.Series(dtype="float64")
    else:
        df["Marža %"] = np.where(
            df["Apyvarta"] != 0,
            (df["Pajamos"] / df["Apyvarta"]) * 100.0,
            np.nan,
        )

    df = df.sort_values("Apyvarta", ascending=False).reset_index(drop=True)
    _cache_set(_TABLE_CACHE, key, df)
    return df


def _fetch_monthly_data(
    year: Optional[int], branches: Sequence[str], manufacturer: Optional[str]
) -> pd.DataFrame:
    if not year or not branches:
        base = pd.DataFrame({"Month": range(1, 13)})
        base[["Apyvarta", "Pajamos", "Kiekis", "Marža %"]] = np.nan
        return base

    normalized_manufacturer = str(manufacturer) if manufacturer else None
    key = (
        "monthly",
        int(year),
        tuple(sorted(branches)),
        normalized_manufacturer if normalized_manufacturer else "__all__",
    )
    cached = _cache_get(_CHART_CACHE, key)
    if cached is not None:
        return cached

    year_col = _require_column("year")
    branch_col = _require_column("branch")
    month_col = _require_column("month")
    turnover_col = _require_column("turnover")
    revenue_col = _require_column("revenue")
    quantity_col = _require_column("quantity")
    manufacturer_expr = _manufacturer_expr()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "branch")
    where_parts = [f"CAST({year_col} AS UNSIGNED) = :year", branch_clause]
    params: Dict[str, Any] = {"year": int(year), **branch_params}

    if normalized_manufacturer:
        where_parts.append(f"{manufacturer_expr} = :manufacturer")
        params["manufacturer"] = normalized_manufacturer

    stmt = text(
        f"""
        SELECT
            {month_col} AS MonthRaw,
            SUM(CAST({turnover_col} AS DECIMAL(18,2))) AS Apyvarta,
            SUM(CAST({revenue_col} AS DECIMAL(18,2))) AS Pajamos,
            SUM(CAST({quantity_col} AS DECIMAL(18,2))) AS Kiekis
        FROM sales
        WHERE {' AND '.join(where_parts)}
        GROUP BY {month_col}
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        base = pd.DataFrame({"Month": range(1, 13)})
        base[["Apyvarta", "Pajamos", "Kiekis", "Marža %"]] = np.nan
        _cache_set(_CHART_CACHE, key, base)
        return base

    df["Month"] = df["MonthRaw"].apply(_month_to_number)
    df = df.dropna(subset=["Month"])

    df = (
        df.groupby("Month", as_index=False)[["Apyvarta", "Pajamos", "Kiekis"]]
        .sum()
        .sort_values("Month")
    )

    full_months = pd.DataFrame({"Month": list(range(1, 13))})
    df = full_months.merge(df, on="Month", how="left")

    df["Apyvarta"] = pd.to_numeric(df["Apyvarta"], errors="coerce")
    df["Pajamos"] = pd.to_numeric(df["Pajamos"], errors="coerce")
    df["Kiekis"] = pd.to_numeric(df["Kiekis"], errors="coerce")

    with np.errstate(divide="ignore", invalid="ignore"):
        margin = (df["Pajamos"] / df["Apyvarta"]) * 100.0
    df["Marža %"] = np.where(
        (df["Apyvarta"].notna()) & (df["Apyvarta"] != 0),
        margin,
        np.where(df["Apyvarta"] == 0, 0.0, np.nan),
    )

    df["Month"] = df["Month"].astype(int)

    _cache_set(_CHART_CACHE, key, df)
    return df


def _build_chart(df: pd.DataFrame, manufacturer: Optional[str], year: Optional[int]) -> go.Figure:
    title = "All manufacturers" if not manufacturer else manufacturer
    subtitle = f"Year {year}" if year else ""

    df_plot = df.copy()
    value_columns = [col for col in ["Apyvarta", "Pajamos", "Kiekis", "Marža %"] if col in df_plot]
    if value_columns:
        df_plot = df_plot.loc[~df_plot[value_columns].isna().all(axis=1)]
    df_plot = df_plot.sort_values("Month").reset_index(drop=True)

    months = df_plot["Month"].tolist() if not df_plot.empty else []

    turnover_series = (
        pd.to_numeric(df_plot.get("Apyvarta"), errors="coerce")
        if not df_plot.empty
        else pd.Series(dtype="float64")
    )
    margin_series = (
        pd.to_numeric(df_plot.get("Marža %"), errors="coerce")
        if not df_plot.empty
        else pd.Series(dtype="float64")
    )
    quantity_series = (
        pd.to_numeric(df_plot.get("Kiekis"), errors="coerce")
        if not df_plot.empty
        else pd.Series(dtype="float64")
    )

    def _format_currency_compact(value: float) -> str:
        if pd.isna(value):
            return "—"
        abs_value = abs(value)
        suffix = ""
        scaled = float(value)
        for threshold, suffix_candidate in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
            if abs_value >= threshold:
                scaled = value / threshold
                suffix = suffix_candidate
                break

        if suffix:
            formatted = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"€{formatted}{suffix}"

        formatted = f"{int(round(value)):,}".replace(",", " ")
        return f"€{formatted}"

    def _format_margin_hover(value: float) -> str:
        if pd.isna(value):
            return "—"
        return f"{value:.1f}%"

    def _format_quantity_hover(value: float) -> str:
        if pd.isna(value):
            return "—"
        return f"{int(round(value)):,}".replace(",", " ")

    bar_customdata: List[List[str]] = []
    margin_customdata: List[List[str]] = []
    quantity_customdata: List[List[str]] = []
    margin_label_points: List[Tuple[int, float, str, str]] = []
    quantity_label_points: List[Tuple[int, float, str, str]] = []

    for idx in range(len(df_plot)):
        month = months[idx]
        turnover_val = turnover_series.iloc[idx]
        margin_val = margin_series.iloc[idx]
        quantity_val = quantity_series.iloc[idx]

        formatted_turnover = _format_currency_compact(turnover_val)
        formatted_margin = _format_margin_hover(margin_val)
        formatted_quantity = _format_quantity_hover(quantity_val)

        shared_customdata = [formatted_turnover, formatted_margin, formatted_quantity]
        bar_customdata.append(shared_customdata.copy())
        margin_customdata.append(shared_customdata.copy())
        quantity_customdata.append(shared_customdata.copy())

        if not pd.isna(margin_val):
            margin_label_points.append(
                (month, float(margin_val), formatted_margin, "bottom center")
            )

        if not pd.isna(quantity_val):
            quantity_label_points.append(
                (
                    month,
                    float(quantity_val),
                    _format_quantity_hover(quantity_val),
                    "top center",
                )
            )

    def _axis_range(values: pd.Series) -> Optional[List[float]]:
        if values is None or values.empty:
            return None
        clean = pd.to_numeric(values, errors="coerce").dropna()
        if clean.empty:
            return None
        min_val = clean.min()
        max_val = clean.max()
        if math.isclose(min_val, max_val):
            padding = abs(min_val) * 0.1 if min_val != 0 else 1.0
            return [min_val - padding, max_val + padding]
        lower = min_val * (0.9 if min_val >= 0 else 1.1)
        upper = max_val * (1.1 if max_val >= 0 else 0.9)
        if math.isclose(lower, upper):
            padding = abs(lower) * 0.1 if lower != 0 else 1.0
            lower -= padding
            upper += padding
        return [lower, upper]

    marza_range = _axis_range(margin_series)
    kiekis_range = _axis_range(quantity_series)

    fig = go.Figure()
    fig.add_bar(
        x=months,
        y=turnover_series.tolist(),
        name="Apyvarta (€)",
        marker=dict(color="#000000", opacity=0.9, line=dict(width=0)),
        customdata=bar_customdata,
        hovertemplate=(
            "Mėnuo: %{x}<br>"
            "Apyvarta: %{customdata[0]}<br>"
            "Marža: %{customdata[1]}<br>"
            "Kiekis: %{customdata[2]}<extra></extra>"
        ),
        yaxis="y",
    )

    fig.add_trace(
        go.Scatter(
            x=months,
            y=margin_series.tolist(),
            mode="lines+markers",
            name="Marža %",
            line=dict(color="#D62828", width=3),
            marker=dict(size=8, color="#D62828", symbol="circle"),
            customdata=margin_customdata,
            hovertemplate=(
                "Mėnuo: %{x}<br>"
                "Apyvarta: %{customdata[0]}<br>"
                "Marža: %{customdata[1]}<br>"
                "Kiekis: %{customdata[2]}<extra></extra>"
            ),
            yaxis="y2",
            connectgaps=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=months,
            y=quantity_series.tolist(),
            mode="lines+markers",
            name="Kiekis",
            line=dict(color="#FCA311", width=3),
            marker=dict(size=8, color="#FCA311", symbol="circle"),
            customdata=quantity_customdata,
            hovertemplate=(
                "Mėnuo: %{x}<br>"
                "Apyvarta: %{customdata[0]}<br>"
                "Marža: %{customdata[1]}<br>"
                "Kiekis: %{customdata[2]}<extra></extra>"
            ),
            yaxis="y3",
            connectgaps=False,
        )
    )

    if margin_label_points:
        margin_label_points[-1] = (
            margin_label_points[-1][0],
            margin_label_points[-1][1],
            margin_label_points[-1][2],
            "bottom right",
        )
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in margin_label_points],
                y=[point[1] for point in margin_label_points],
                mode="text",
                text=[point[2] for point in margin_label_points],
                textposition=[point[3] for point in margin_label_points],
                textfont=dict(
                    color="#D62828",
                    size=11,
                    family="Inter SemiBold, Arial, sans-serif",
                ),
                showlegend=False,
                hoverinfo="skip",
                yaxis="y2",
                cliponaxis=False,
            )
        )

    if quantity_label_points:
        quantity_label_points[-1] = (
            quantity_label_points[-1][0],
            quantity_label_points[-1][1],
            quantity_label_points[-1][2],
            "top right",
        )
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in quantity_label_points],
                y=[point[1] for point in quantity_label_points],
                mode="text",
                text=[point[2] for point in quantity_label_points],
                textposition=[point[3] for point in quantity_label_points],
                textfont=dict(
                    color="#FCA311",
                    size=11,
                    family="Inter SemiBold, Arial, sans-serif",
                ),
                showlegend=False,
                hoverinfo="skip",
                yaxis="y3",
                cliponaxis=False,
            )
        )

    if months:
        x_range = [months[0] - 0.5, months[-1] + 0.5]
    else:
        x_range = [0.5, 12.5]

    layout_kwargs = dict(
        template="plotly_white",
        title=dict(text=f"{title} {subtitle}".strip(), x=0.02, y=0.95),
        margin=dict(t=60, r=70, l=60, b=60),
        legend=dict(orientation="h", x=1, xanchor="right", y=1, yanchor="top"),
        xaxis=dict(
            title="Month Number",
            tickmode="array",
            tickvals=months,
            ticktext=[str(month) for month in months],
            range=x_range,
            gridcolor=IC_GRAY,
        ),
        yaxis=dict(title="Apyvarta (€)", separatethousands=True),
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            showticklabels=False,
            ticks="",
            showline=False,
            zeroline=False,
            title_text="",
        ),
        yaxis3=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            showticklabels=False,
            ticks="",
            showline=False,
            zeroline=False,
            title_text="",
        ),
        hovermode="x unified",
        hoverlabel=dict(namelength=-1),
    )

    if marza_range:
        layout_kwargs["yaxis2"]["range"] = marza_range
    if kiekis_range:
        layout_kwargs["yaxis3"]["range"] = kiekis_range

    fig.update_layout(**layout_kwargs)

    return fig


@callback(
    Output(f"{PAGE_ID_PREFIX}_manufacturer", "options"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
)
def populate_manufacturers(_: Any) -> List[Dict[str, str]]:
    return [{"label": name, "value": name} for name in _all_manufacturers()]


@callback(
    Output(f"{PAGE_ID_PREFIX}_table", "data"),
    Output(f"{PAGE_ID_PREFIX}_chart", "figure"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
    Input(f"{PAGE_ID_PREFIX}_branch", "value"),
    Input(f"{PAGE_ID_PREFIX}_manufacturer", "value"),
)
def update_product_view(
    year: Optional[int],
    branches: Optional[Sequence[str]],
    manufacturer: Optional[str],
):
    normalized_branches = _normalized_branches(branches)

    table_df = _fetch_table_data(year, normalized_branches)
    table_records = [
        {
            "Manufacturer": row["Manufacturer"],
            "Apyvarta": _format_currency(row["Apyvarta"]),
            "Pajamos": _format_currency(row["Pajamos"]),
            "Kiekis": _format_quantity(row["Kiekis"]),
            "Marža %": _format_margin(row["Marža %"]),
        }
        for _, row in table_df.iterrows()
    ]

    chart_df = _fetch_monthly_data(year, normalized_branches, manufacturer)
    figure = _build_chart(chart_df, manufacturer, year)

    return table_records, figure


@callback(
    Output(f"{PAGE_ID_PREFIX}_manufacturer", "value"),
    Input(f"{PAGE_ID_PREFIX}_table", "active_cell"),
    State(f"{PAGE_ID_PREFIX}_table", "data"),
    prevent_initial_call=True,
)
def sync_manufacturer_from_table(active_cell: Optional[Dict[str, Any]], rows: Optional[List[Dict[str, Any]]]):
    if not active_cell or rows is None:
        return no_update

    row_index = active_cell.get("row")
    if row_index is None:
        return no_update

    try:
        record = rows[row_index]
    except (IndexError, TypeError):
        return no_update

    manufacturer = record.get("Manufacturer")
    if not manufacturer:
        return no_update

    return manufacturer
