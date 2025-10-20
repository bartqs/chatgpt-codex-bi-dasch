"""Callbacks and data loading for the Product Analysis page."""

from __future__ import annotations

import math
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, no_update
from plotly import graph_objects as go
from sqlalchemy import bindparam, text

from data.app_data import (
    IC_GRAY,
    IC_NAVY,
    IC_RED,
    engine,
    get_columns,
    pick_col,
)

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

    stmt = text(
        f"""
        SELECT
            {manufacturer_expr} AS Manufacturer,
            SUM(CAST({turnover_col} AS DECIMAL(18,2))) AS Apyvarta,
            SUM(CAST({revenue_col} AS DECIMAL(18,2))) AS Pajamos,
            SUM(CAST({quantity_col} AS DECIMAL(18,2))) AS Kiekis
        FROM sales
        WHERE CAST({year_col} AS UNSIGNED) = :year
          AND {branch_col} IN :branches
        GROUP BY {manufacturer_expr}
        """
    ).bindparams(bindparam("branches", expanding=True))

    params = {"year": int(year), "branches": list(branches)}

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
        base[["Apyvarta", "Pajamos", "Kiekis"]] = 0.0
        base["Marža %"] = 0.0
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

    where_parts = [f"CAST({year_col} AS UNSIGNED) = :year", f"{branch_col} IN :branches"]
    params: Dict[str, Any] = {"year": int(year), "branches": list(branches)}

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
    ).bindparams(bindparam("branches", expanding=True))

    if normalized_manufacturer:
        stmt = stmt.bindparams(bindparam("manufacturer"))

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        base = pd.DataFrame({"Month": range(1, 13)})
        base[["Apyvarta", "Pajamos", "Kiekis"]] = 0
        base["Marža %"] = 0.0
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
    df[["Apyvarta", "Pajamos", "Kiekis"]] = df[["Apyvarta", "Pajamos", "Kiekis"]].fillna(0.0)

    df["Marža %"] = np.where(
        df["Apyvarta"] != 0,
        (df["Pajamos"] / df["Apyvarta"]) * 100.0,
        0.0,
    )

    _cache_set(_CHART_CACHE, key, df)
    return df


def _build_chart(df: pd.DataFrame, manufacturer: Optional[str], year: Optional[int]) -> go.Figure:
    title = "All manufacturers" if not manufacturer else manufacturer
    subtitle = f"Year {year}" if year else ""

    custom_currency = df["Apyvarta"].apply(_format_currency).to_numpy()
    custom_margin = df["Marža %"].apply(lambda v: f"{v:.2f} %").to_numpy()
    custom_quantity = df["Kiekis"].apply(_format_quantity).to_numpy()

    fig = go.Figure()
    fig.add_bar(
        x=df["Month"],
        y=df["Apyvarta"],
        name="Apyvarta (€)",
        marker_color=IC_NAVY,
        customdata=np.array(custom_currency)[:, None],
        hovertemplate="Mėnuo %{x}<br>Apyvarta: %{customdata[0]}<extra></extra>",
        yaxis="y",
    )
    fig.add_trace(
        go.Scatter(
            x=df["Month"],
            y=df["Marža %"],
            mode="lines+markers",
            name="Marža %",
            line=dict(color=IC_RED, width=2),
            marker=dict(size=6),
            customdata=np.array(custom_margin)[:, None],
            hovertemplate="Mėnuo %{x}<br>Marža: %{customdata[0]}<extra></extra>",
            yaxis="y2",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["Month"],
            y=df["Kiekis"],
            mode="lines+markers",
            name="Kiekis",
            line=dict(color="#2A9D8F", width=2),
            marker=dict(size=6),
            customdata=np.array(custom_quantity)[:, None],
            hovertemplate="Mėnuo %{x}<br>Kiekis: %{customdata[0]}<extra></extra>",
            yaxis="y3",
        )
    )

    fig.update_layout(
        template="plotly_white",
        title=dict(text=f"{title} {subtitle}".strip(), x=0.02, y=0.95),
        margin=dict(t=60, r=80, l=60, b=60),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.15),
        xaxis=dict(
            title="Month Number",
            tickmode="linear",
            dtick=1,
            range=[0.5, 12.5],
            gridcolor=IC_GRAY,
        ),
        yaxis=dict(title="Apyvarta", separatethousands=True),
        yaxis2=dict(
            title="Marža %",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=".1f",
            position=1.0,
        ),
        yaxis3=dict(
            title="Kiekis",
            overlaying="y",
            side="right",
            showgrid=False,
            tickformat=".0f",
            position=1.06,
        ),
        hovermode="x unified",
    )

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
