"""Callbacks and data loading for the Product Analysis page."""

from __future__ import annotations

import math
import time
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, ctx, no_update
from dash.exceptions import PreventUpdate
from plotly import graph_objects as go
from sqlalchemy import text

from data.app_data import IC_GRAY, engine, get_columns, pick_col

from .product_page import (
    CLIENT_CHART_ID,
    CLIENT_CHART_WRAPPER_ID,
    CLIENT_NO_DATA_ID,
    CLIENT_TABLE_ID,
    CLIENT_TABLE_WRAPPER_ID,
    CLIENT_VIEW_COLUMN_HIDDEN_STYLE,
    CLIENT_VIEW_COLUMN_ID,
    CLIENT_VIEW_COLUMN_VISIBLE_STYLE,
    CLIENT_VIEW_TOGGLE_ID,
    CLIENT_SELECTED_MANUFACTURER_STORE_ID,
    FILTER_CLIENT_CODE_ID,
    FILTER_CLIENT_ID,
    GENERAL_CHART_ID,
    GENERAL_TABLE_ID,
    PAGE_ID_PREFIX,
)


_CACHE_TTL_SECONDS = 120
_TABLE_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}
_CHART_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}
_CLIENT_OPTIONS_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}
_CLIENT_CODES_CACHE: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}


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
        "client": pick_col(cols, ["Klientas", "Client", "Pirkėjas", "Customer"]),
        "client_code": pick_col(
            cols,
            ["Kliento kodas", "Client Code", "Customer Code", "Pirkėjo kodas"],
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
def _client_expr() -> str:
    column = _require_column("client")
    return f"COALESCE({column}, 'Nežinomas klientas')"


@lru_cache(maxsize=1)
def _client_code_column() -> str:
    return _require_column("client_code")


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
        return "0.0 %"
    return f"{value:.1f} %"


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


def _normalized_codes(codes: Optional[Sequence[Any]]) -> Optional[List[str]]:
    if codes is None:
        return None
    if isinstance(codes, str):
        return [codes]
    return [str(code) for code in codes if str(code).strip()]


def _fetch_clients(year: Optional[int], branches: Sequence[str]) -> pd.DataFrame:
    if not year or not branches:
        return pd.DataFrame({"Klientas": []})

    key = ("clients", int(year), tuple(sorted(branches)))
    cached = _cache_get(_CLIENT_OPTIONS_CACHE, key)
    if cached is not None:
        return cached

    year_col = _require_column("year")
    branch_col = _require_column("branch")
    client_expr = _client_expr()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "client_branch")

    stmt = text(
        f"""
        SELECT DISTINCT {client_expr} AS Klientas
        FROM sales
        WHERE CAST({year_col} AS UNSIGNED) = :year
          AND {branch_clause}
        ORDER BY Klientas
        """
    )

    params: Dict[str, Any] = {"year": int(year), **branch_params}

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    df["Klientas"] = df["Klientas"].astype(str)
    _cache_set(_CLIENT_OPTIONS_CACHE, key, df)
    return df


def _fetch_client_codes(
    year: Optional[int], branches: Sequence[str], client: Optional[str]
) -> pd.DataFrame:
    if not year or not branches or not client:
        return pd.DataFrame({"Kliento kodas": []})

    normalized_client = str(client)
    key = ("client_codes", int(year), tuple(sorted(branches)), normalized_client)
    cached = _cache_get(_CLIENT_CODES_CACHE, key)
    if cached is not None:
        return cached

    year_col = _require_column("year")
    branch_col = _require_column("branch")
    client_expr = _client_expr()
    code_col = _client_code_column()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "client_code_branch")

    stmt = text(
        f"""
        SELECT DISTINCT CAST({code_col} AS CHAR) AS ClientCode
        FROM sales
        WHERE CAST({year_col} AS UNSIGNED) = :year
          AND {branch_clause}
          AND {client_expr} = :client
          AND {code_col} IS NOT NULL
        ORDER BY ClientCode
        """
    )

    params: Dict[str, Any] = {"year": int(year), "client": normalized_client, **branch_params}

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        df["ClientCode"] = pd.Series(dtype="object")

    df["Kliento kodas"] = df["ClientCode"].astype(str)
    df = df[["Kliento kodas"]]
    _cache_set(_CLIENT_CODES_CACHE, key, df)
    return df


def _fetch_table_data(
    year: Optional[int],
    branches: Sequence[str],
    client: Optional[str] = None,
    client_codes: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    if not year or not branches:
        return pd.DataFrame(
            columns=["Manufacturer", "Apyvarta", "Pajamos", "Kiekis", "Marža %"]
        )

    normalized_client = str(client) if client else None
    normalized_codes = _normalized_codes(client_codes)

    if normalized_client and normalized_codes is not None and not normalized_codes:
        return pd.DataFrame(
            columns=["Manufacturer", "Apyvarta", "Pajamos", "Kiekis", "Marža %"]
        )

    codes_key: Tuple[Any, ...]
    if normalized_codes is None:
        codes_key = ("__all__",)
    else:
        codes_key = tuple(sorted(normalized_codes)) if normalized_codes else ("__none__",)

    key = (
        "table",
        int(year),
        tuple(sorted(branches)),
        normalized_client or "__all__",
        codes_key,
    )
    cached = _cache_get(_TABLE_CACHE, key)
    if cached is not None:
        return cached

    year_col = _require_column("year")
    branch_col = _require_column("branch")
    turnover_col = _require_column("turnover")
    revenue_col = _require_column("revenue")
    quantity_col = _require_column("quantity")
    manufacturer_expr = _manufacturer_expr()
    client_expr = _client_expr()
    client_code_col = _client_code_column()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "branch")

    where_parts = [f"CAST({year_col} AS UNSIGNED) = :year", branch_clause]
    params: Dict[str, Any] = {"year": int(year), **branch_params}

    if normalized_client:
        where_parts.append(f"{client_expr} = :client")
        params["client"] = normalized_client

    if normalized_codes:
        code_clause, code_params = _build_in_clause(
            client_code_col, normalized_codes, "client_code"
        )
        where_parts.append(code_clause)
        params.update(code_params)

    stmt = text(
        f"""
        SELECT
            {manufacturer_expr} AS Manufacturer,
            SUM(CAST({turnover_col} AS DECIMAL(18,2))) AS Apyvarta,
            SUM(CAST({revenue_col} AS DECIMAL(18,2))) AS Pajamos,
            SUM(CAST({quantity_col} AS DECIMAL(18,2))) AS Kiekis
        FROM sales
        WHERE {' AND '.join(where_parts)}
        GROUP BY {manufacturer_expr}
        """
    )

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
    year: Optional[int],
    branches: Sequence[str],
    manufacturer: Optional[str],
    client: Optional[str] = None,
    client_codes: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    if not year or not branches:
        base = pd.DataFrame({"Month": range(1, 13)})
        base[["Apyvarta", "Pajamos", "Kiekis", "Marža %"]] = np.nan
        return base

    normalized_manufacturer = str(manufacturer) if manufacturer else None
    normalized_client = str(client) if client else None
    normalized_codes = _normalized_codes(client_codes)

    if normalized_client and normalized_codes is not None and not normalized_codes:
        base = pd.DataFrame({"Month": range(1, 13)})
        base[["Apyvarta", "Pajamos", "Kiekis", "Marža %"]] = np.nan
        return base

    codes_key: Tuple[Any, ...]
    if normalized_codes is None:
        codes_key = ("__all__",)
    else:
        codes_key = tuple(sorted(normalized_codes)) if normalized_codes else ("__none__",)

    key = (
        "monthly",
        int(year),
        tuple(sorted(branches)),
        normalized_manufacturer if normalized_manufacturer else "__all__",
        normalized_client or "__all__",
        codes_key,
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
    client_expr = _client_expr()
    client_code_col = _client_code_column()

    branch_clause, branch_params = _build_in_clause(branch_col, branches, "branch")
    where_parts = [f"CAST({year_col} AS UNSIGNED) = :year", branch_clause]
    params: Dict[str, Any] = {"year": int(year), **branch_params}

    if normalized_manufacturer:
        where_parts.append(f"{manufacturer_expr} = :manufacturer")
        params["manufacturer"] = normalized_manufacturer

    if normalized_client:
        where_parts.append(f"{client_expr} = :client")
        params["client"] = normalized_client

    if normalized_codes:
        code_clause, code_params = _build_in_clause(
            client_code_col, normalized_codes, "client_code"
        )
        where_parts.append(code_clause)
        params.update(code_params)

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
    margin_label_points: List[Dict[str, Any]] = []
    quantity_label_points: List[Dict[str, Any]] = []

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
                {
                    "x": month,
                    "y": float(margin_val),
                    "text": formatted_margin,
                }
            )

        if not pd.isna(quantity_val):
            quantity_label_points.append(
                {
                    "x": month,
                    "y": float(quantity_val),
                    "text": _format_quantity_hover(quantity_val),
                }
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
            if min_val == 0:
                return [-1.0, 1.0]
            padding = abs(min_val) * 0.15 or 1.0
            return [min_val - padding, max_val + padding]

        lower = min_val * (0.85 if min_val >= 0 else 1.15)
        upper = max_val * (1.15 if max_val >= 0 else 0.85)

        if math.isclose(lower, min_val):
            adjustment = abs(min_val) * 0.15 or 1.0
            lower = min_val - adjustment

        if math.isclose(upper, max_val):
            adjustment = abs(max_val) * 0.15 or 1.0
            upper = max_val + adjustment

        if math.isclose(lower, upper):
            padding = abs(lower) * 0.15 if lower != 0 else 1.0
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

    annotations: List[Dict[str, Any]] = []

    for point in margin_label_points:
        annotations.append(
            dict(
                x=point["x"],
                y=point["y"],
                xref="x",
                yref="y2",
                text=point["text"],
                showarrow=False,
                font=dict(
                    color="#D62828",
                    size=11,
                    family="Inter SemiBold, Arial, sans-serif",
                ),
                xanchor="left",
                yanchor="top",
                yshift=-10,
                align="left",
                bgcolor="rgba(0,0,0,0.05)",
                bordercolor="rgba(0,0,0,0)",
                borderpad=2,
            )
        )

    for point in quantity_label_points:
        annotations.append(
            dict(
                x=point["x"],
                y=point["y"],
                xref="x",
                yref="y3",
                text=point["text"],
                showarrow=False,
                font=dict(
                    color="#FCA311",
                    size=11,
                    family="Inter SemiBold, Arial, sans-serif",
                ),
                xanchor="right",
                yanchor="bottom",
                yshift=10,
                align="right",
                bgcolor="rgba(0,0,0,0.05)",
                bordercolor="rgba(0,0,0,0)",
                borderpad=2,
            )
        )

    if months:
        x_range = [months[0] - 0.5, months[-1] + 0.5]
    else:
        x_range = [0.5, 12.5]

    layout_kwargs = dict(
        template="plotly_white",
        title=dict(text=f"{title} {subtitle}".strip(), x=0.02, y=0.95),
        height=540,
        margin=dict(t=60, b=60, l=60, r=20),
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
    if annotations:
        layout_kwargs["annotations"] = annotations

    fig.update_layout(**layout_kwargs)

    return fig


@callback(
    Output(f"{PAGE_ID_PREFIX}_manufacturer", "options"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
)
def populate_manufacturers(_: Any) -> List[Dict[str, str]]:
    return [{"label": name, "value": name} for name in _all_manufacturers()]


@callback(
    Output(FILTER_CLIENT_ID, "options"),
    Output(FILTER_CLIENT_ID, "value"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
    Input(f"{PAGE_ID_PREFIX}_branch", "value"),
    State(FILTER_CLIENT_ID, "value"),
)
def populate_clients(
    year: Optional[int], branches: Optional[Sequence[str]], current_value: Optional[str]
):
    normalized_branches = _normalized_branches(branches)
    client_df = _fetch_clients(year, normalized_branches)

    options = (
        [{"label": client, "value": client} for client in client_df["Klientas"].tolist()]
        if not client_df.empty
        else []
    )

    if not options:
        return [], None

    valid_values = {option["value"] for option in options}
    if current_value and current_value in valid_values:
        return options, current_value

    return options, None


@callback(
    Output(FILTER_CLIENT_CODE_ID, "options"),
    Output(FILTER_CLIENT_CODE_ID, "value"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
    Input(f"{PAGE_ID_PREFIX}_branch", "value"),
    Input(FILTER_CLIENT_ID, "value"),
    State(FILTER_CLIENT_CODE_ID, "value"),
)
def populate_client_codes(
    year: Optional[int],
    branches: Optional[Sequence[str]],
    client: Optional[str],
    current_codes: Optional[Sequence[str]],
):
    if not client:
        return [], []

    normalized_branches = _normalized_branches(branches)
    codes_df = _fetch_client_codes(year, normalized_branches, client)

    options = (
        [
            {"label": code, "value": code}
            for code in codes_df["Kliento kodas"].dropna().astype(str).tolist()
        ]
        if not codes_df.empty
        else []
    )

    if not options:
        return [], []

    option_values = [option["value"] for option in options]
    trigger_id = ctx.triggered_id

    if trigger_id in {FILTER_CLIENT_ID, f"{PAGE_ID_PREFIX}_year", f"{PAGE_ID_PREFIX}_branch"}:
        return options, option_values

    normalized_current = _normalized_codes(current_codes)
    if normalized_current:
        filtered = [code for code in normalized_current if code in option_values]
        if filtered:
            return options, filtered

    return options, option_values


@callback(
    Output(FILTER_CLIENT_ID, "value"),
    Output(FILTER_CLIENT_CODE_ID, "value"),
    Input(CLIENT_VIEW_TOGGLE_ID, "n_clicks"),
    prevent_initial_call=True,
)
def disable_client_view(n_clicks: Optional[int]):
    if not n_clicks:
        raise PreventUpdate
    return None, []


@callback(
    Output(CLIENT_VIEW_COLUMN_ID, "style"),
    Input(FILTER_CLIENT_ID, "value"),
)
def toggle_client_column(client_value: Optional[str]):
    if client_value:
        return dict(CLIENT_VIEW_COLUMN_VISIBLE_STYLE)
    return dict(CLIENT_VIEW_COLUMN_HIDDEN_STYLE)


@callback(
    Output(CLIENT_TABLE_ID, "data"),
    Output(CLIENT_TABLE_ID, "active_cell"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
    Input(f"{PAGE_ID_PREFIX}_branch", "value"),
    Input(FILTER_CLIENT_ID, "value"),
    Input(FILTER_CLIENT_CODE_ID, "value"),
)
def update_client_table(
    year: Optional[int],
    branches: Optional[Sequence[str]],
    client: Optional[str],
    client_codes: Optional[Sequence[str]],
):
    if not client:
        return [], None

    normalized_branches = _normalized_branches(branches)
    table_df = _fetch_table_data(year, normalized_branches, client, client_codes)

    if table_df.empty:
        return [], None

    records = [
        {
            "Manufacturer": row["Manufacturer"],
            "Apyvarta": _format_currency(row["Apyvarta"]),
            "Pajamos": _format_currency(row["Pajamos"]),
            "Kiekis": _format_quantity(row["Kiekis"]),
            "Marža %": _format_margin(row["Marža %"]),
        }
        for _, row in table_df.iterrows()
    ]

    return records, None


@callback(
    Output(CLIENT_SELECTED_MANUFACTURER_STORE_ID, "data"),
    Input(CLIENT_TABLE_ID, "active_cell"),
    Input(CLIENT_TABLE_ID, "data"),
)
def sync_client_selected_manufacturer(
    active_cell: Optional[Dict[str, Any]], rows: Optional[List[Dict[str, Any]]]
):
    if not ctx.triggered:
        return None

    triggered_prop = ctx.triggered[0]["prop_id"]

    if triggered_prop.endswith(".data"):
        return None

    if not active_cell or rows is None:
        return None

    row_index = active_cell.get("row")
    if row_index is None:
        return None

    try:
        record = rows[row_index]
    except (IndexError, TypeError):
        return None

    manufacturer = record.get("Manufacturer")
    if not manufacturer:
        return None

    return manufacturer


@callback(
    Output(CLIENT_CHART_ID, "figure"),
    Output(CLIENT_NO_DATA_ID, "hidden"),
    Output(CLIENT_TABLE_WRAPPER_ID, "hidden"),
    Output(CLIENT_CHART_WRAPPER_ID, "hidden"),
    Input(f"{PAGE_ID_PREFIX}_year", "value"),
    Input(f"{PAGE_ID_PREFIX}_branch", "value"),
    Input(FILTER_CLIENT_ID, "value"),
    Input(FILTER_CLIENT_CODE_ID, "value"),
    Input(CLIENT_SELECTED_MANUFACTURER_STORE_ID, "data"),
)
def update_client_chart(
    year: Optional[int],
    branches: Optional[Sequence[str]],
    client: Optional[str],
    client_codes: Optional[Sequence[str]],
    selected_manufacturer: Optional[str],
):
    normalized_branches = _normalized_branches(branches)

    empty_chart_df = pd.DataFrame(
        {
            "Month": pd.Series(dtype="int64"),
            "Apyvarta": pd.Series(dtype="float64"),
            "Pajamos": pd.Series(dtype="float64"),
            "Kiekis": pd.Series(dtype="float64"),
            "Marža %": pd.Series(dtype="float64"),
        }
    )

    if not client:
        figure = _build_chart(empty_chart_df, None, year)
        return figure, True, True, True

    table_df = _fetch_table_data(year, normalized_branches, client, client_codes)

    if table_df.empty:
        figure = _build_chart(empty_chart_df, None, year)
        return figure, False, True, True

    available_manufacturers = set(table_df["Manufacturer"].astype(str))
    normalized_selected = (
        str(selected_manufacturer) if selected_manufacturer in available_manufacturers else None
    )

    chart_df = _fetch_monthly_data(
        year,
        normalized_branches,
        normalized_selected,
        client,
        client_codes,
    )
    figure = _build_chart(chart_df, normalized_selected, year)

    return figure, True, False, False


@callback(
    Output(GENERAL_TABLE_ID, "data"),
    Output(GENERAL_CHART_ID, "figure"),
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
    Input(GENERAL_TABLE_ID, "active_cell"),
    State(GENERAL_TABLE_ID, "data"),
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
