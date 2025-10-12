"""
Shared application data, constants, and business logic extracted from the
original single-file Dash notebook implementation.

This module preserves the exact behavior, calculations, and styling helpers
used across the dashboard pages.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from dash import html
from plotly import graph_objects as go
from sqlalchemy import bindparam, create_engine, text


# ==================== Spalvos / konfigas ====================
IC_RED = "#E30613"
IC_NAVY = "#002F6C"
IC_GRAY = "#B2B2B2"
IC_BLACK = "#000000"
IC_WHITE = "#FFFFFF"
IC_BG = "#F5F6F8"
COLORWAY_YEARS = {2022: IC_NAVY, 2023: IC_RED, 2024: IC_GRAY, 2025: IC_BLACK, 2026: "#444"}
GREEN = "#198754"
RED = "#C62828"

MENUO_TVARKA = [f"M-{i:02d}" for i in range(1, 13)]
MENUO_LABELS_LT = ["Sau", "Vas", "Kov", "Bal", "Geg", "Bir", "Lie", "Rgp", "Rgs", "Spa", "Lap", "Gru"]
METRICS = ["APYVARTA", "PAJAMOS", "MARŽA %", "KIEKIS"]


# ==================== DB Connection with Proper Pooling ====================
# FIX #1: Improved database connection management
password = os.getenv("DB_PASSWORD", "pass123")  # Use env var, fallback for dev
engine = create_engine(
    f"mysql+pymysql://root:{password}@localhost:3306/ic?charset=utf8mb4",
    connect_args={"charset": "utf8mb4"},
    pool_size=5,  # Maximum number of connections to keep persistently
    max_overflow=10,  # Maximum overflow connections beyond pool_size
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before using
    pool_timeout=30,  # Wait 30s for connection from pool
    future=True,
)


# ==================== Data Loading Functions ====================
# FIX #4: Efficient data type conversion with proper dtype specification
def load_summary_data() -> pd.DataFrame:
    """Load and prepare summary data with efficient memory usage."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                """
            SELECT
                CAST(`Year [Name] PE-Y01` AS UNSIGNED)  AS Metai,
                `Month [Short name] PE-M02`             AS Menuo,
                `Filialas`,
                COALESCE(`Segmentas`, 'Nepriskirta')    AS Segmentas,
                SUM(CAST(`APYVARTA` AS DECIMAL(18,2)))  AS APYVARTA,
                SUM(CAST(`PAJAMOS`  AS DECIMAL(18,2)))  AS PAJAMOS,
                SUM(CAST(`KIEKIS`   AS DECIMAL(18,2)))  AS KIEKIS
            FROM sales
            WHERE `Year [Name] PE-Y01` IS NOT NULL
              AND `Month [Short name] PE-M02` IS NOT NULL
            GROUP BY `Filialas`,
                     COALESCE(`Segmentas`, 'Nepriskirta'),
                     CAST(`Year [Name] PE-Y01` AS UNSIGNED),
                     `Month [Short name] PE-M02`
        """
            ),
            conn,
        )

    # FIX #4: Use astype with dict for efficient conversion (single pass)
    df = df.astype({
        "Metai": "int16",
        "Filialas": "category",
        "Segmentas": "category",
    })

    # Convert Menuo to ordered categorical
    df["Menuo"] = pd.Categorical(df["Menuo"].astype(str), categories=MENUO_TVARKA, ordered=True)

    # Convert numeric columns efficiently
    numeric_cols = ["APYVARTA", "PAJAMOS", "KIEKIS"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")

    # Calculate margin
    df["MARŽA %"] = np.where(
        df["APYVARTA"] != 0,
        (df["PAJAMOS"] / df["APYVARTA"]) * 100.0,
        np.nan,
    ).astype("float32")

    return df


@lru_cache(maxsize=1)
def _get_columns_cached() -> Tuple[str, ...]:
    """Cache sales table column names to avoid repeated SHOW COLUMNS queries."""
    with engine.connect() as conn:
        cols = pd.read_sql(text("SHOW COLUMNS FROM sales"), conn)["Field"].tolist()
    return tuple(cols)


def get_columns() -> List[str]:
    """Public helper returning cached sales column names as a list."""
    return list(_get_columns_cached())


def pick_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    """Pick first matching column from candidates."""
    for c in candidates:
        if c in cols:
            return f"`{c}`"
    return None


def load_advisor_data() -> pd.DataFrame:
    """Load and prepare advisor data with efficient memory usage."""
    cols_all = get_columns()
    mfr_sql = pick_col(cols_all, ["Gamintojas (pavad)", "Gamintojas", "Gamintojas [Name]", "Manufacturer"])
    cat_sql = pick_col(cols_all, ["Kategorija (pavad)", "Kategorija", "Kategorija [Name]", "Category"])
    seg_sql = pick_col(cols_all, ["Kliento Segmentas", "Segmentas", "Segmentas.1"]) or "`Segmentas`"

    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                f"""
            SELECT
                CAST(`Year [Name] PE-Y01` AS UNSIGNED)                                AS Metai,
                `Month [Short name] PE-M02`                                           AS Menuo,
                `Filialas`,
                COALESCE({seg_sql}, 'Nepriskirta')                                     AS Segmentas,
                { ("COALESCE(" + cat_sql + ", 'Nepriskirta')") if cat_sql else "'Nepriskirta'"} AS Kategorija,
                { ("COALESCE(" + mfr_sql + ", 'Nepriskirta')") if mfr_sql else "'Nepriskirta'"} AS Gamintojas,
                `Pardavėjas`                                                          AS Pardavejas,
                CAST(`APYVARTA` AS DECIMAL(18,2))                                      AS Apyvarta,
                CAST(`PAJAMOS`  AS DECIMAL(18,2))                                      AS Pajamos,
                CAST(`KIEKIS`   AS DECIMAL(18,2))                                      AS Kiekis
            FROM sales
            WHERE `Year [Name] PE-Y01` IS NOT NULL
              AND `Month [Short name] PE-M02` IS NOT NULL
        """
            ),
            conn,
        )

    # Efficient type conversion
    df["Menuo"] = pd.Categorical(df["Menuo"].astype(str), categories=MENUO_TVARKA, ordered=True)

    for c in ["Apyvarta", "Pajamos", "Kiekis"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")

    df["Marza_pct"] = np.where(
        df["Apyvarta"] != 0,
        (df["Pajamos"] / df["Apyvarta"]) * 100.0,
        np.nan,
    ).astype("float32")

    # Prepare display columns
    df["Pardavejas_display"] = df["Pardavejas"].replace({"(ND)": "E-commerce"}).fillna("Nežinoma")
    for col in ["Filialas", "Segmentas", "Kategorija", "Gamintojas"]:
        df[col] = df[col].fillna("Nežinoma")

    return df


# Load data once at startup
df_sums = load_summary_data()
df_adv = load_advisor_data()

# Extract filter options
SEGMENT_OPTIONS = sorted([s for s in df_sums["Segmentas"].cat.categories if s is not None])
FILIALAS_OPTIONS = sorted([f for f in df_sums["Filialas"].cat.categories if f is not None])
YEAR_OPTIONS = sorted(df_sums["Metai"].unique().tolist())

YEARS_ADV = sorted(df_adv["Metai"].dropna().unique().tolist())
FILIALAI_ADV = sorted(df_adv["Filialas"].dropna().unique().tolist())
SEGMENTAI_ADV = sorted(df_adv["Segmentas"].dropna().unique().tolist())
KATEGORIJOS = sorted(df_adv["Kategorija"].dropna().unique().tolist())


# ==================== Customer Overview Configuration ====================

CUSTOMER_METRIC_OPTIONS = ["Apyvarta", "Pajamos", "Kiekis", "Marža %", "VPK", "VPP"]
CUSTOMER_DEFAULT_YEAR = 2025


def _resolve_customer_columns() -> Dict[str, Optional[str]]:
    """Determine source column names for the customer overview queries."""

    cols = get_columns()
    customer_candidates = [
        "Klientas",
        "Klientas (pavad)",
        "Pirkėjas",
        "Customer",
        "Customer name",
    ]
    customer_code_candidates = [
        "Kliento kodas",
        "Kliento kodas [Code]",
        "Pirkėjo kodas",
        "Customer code",
    ]
    category_candidates = [
        "Kategorija",
        "Kategorija (pavad)",
        "Category",
        "Category name",
    ]

    return {
        "year": "`Year [Name] PE-Y01`",
        "month": "`Month [Short name] PE-M02`",
        "branch": "`Filialas`",
        "segment": pick_col(cols, ["Kliento Segmentas", "Segmentas", "Segmentas.1"]) or "`Segmentas`",
        "category": pick_col(cols, category_candidates) or "`Kategorija`",
        "customer": pick_col(cols, customer_candidates) or "`Klientas`",
        "customer_code": pick_col(cols, customer_code_candidates),
        "turnover": "`APYVARTA`",
        "profit": "`PAJAMOS`",
        "quantity": "`KIEKIS`",
    }


CUSTOMER_COLUMNS = _resolve_customer_columns()


def _coalesce_expr(column: Optional[str], default: str) -> str:
    """Return a COALESCE expression (or literal fallback) for SQL generation."""

    if not column:
        return f"'{default}'"
    return f"COALESCE({column}, '{default}')"


def load_customer_filter_values() -> Dict[str, List[str]]:
    """Load distinct filter values used across the customer overview page."""

    year_col = CUSTOMER_COLUMNS["year"]
    month_col = CUSTOMER_COLUMNS["month"]
    branch_expr = _coalesce_expr(CUSTOMER_COLUMNS["branch"], "Nežinomas")
    segment_expr = _coalesce_expr(CUSTOMER_COLUMNS["segment"], "Nepriskirta")
    category_expr = _coalesce_expr(CUSTOMER_COLUMNS["category"], "Nepriskirta")
    customer_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer"], "Nežinomas klientas")
    code_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer_code"], "ND")

    query = text(
        f"""
        SELECT DISTINCT
            CAST({year_col} AS UNSIGNED) AS Metai,
            {branch_expr}                   AS Filialas,
            {segment_expr}                  AS Segmentas,
            {category_expr}                 AS Kategorija,
            {customer_expr}                 AS Klientas,
            {code_expr}                     AS KlientoKodas
        FROM sales
        WHERE {year_col} IS NOT NULL
          AND {month_col} IS NOT NULL
        """
    )

    with engine.connect() as conn:
        df_filters = pd.read_sql(query, conn)

    df_filters["Metai"] = pd.to_numeric(df_filters["Metai"], errors="coerce")
    df_filters = df_filters.dropna(subset=["Metai"])
    df_filters["Metai"] = df_filters["Metai"].astype("int16")

    return {
        "years": sorted(df_filters["Metai"].unique().tolist()),
        "branches": sorted(df_filters["Filialas"].dropna().unique().tolist()),
        "segments": sorted(df_filters["Segmentas"].dropna().unique().tolist()),
        "categories": sorted(df_filters["Kategorija"].dropna().unique().tolist()),
        "customers": sorted(df_filters["Klientas"].dropna().unique().tolist()),
        "customer_codes": sorted(df_filters["KlientoKodas"].dropna().unique().tolist()),
    }


CUSTOMER_FILTER_VALUES = load_customer_filter_values()

CUSTOMER_YEAR_OPTIONS = CUSTOMER_FILTER_VALUES["years"]
CUSTOMER_FILIALAI = CUSTOMER_FILTER_VALUES["branches"]
CUSTOMER_SEGMENTAI = CUSTOMER_FILTER_VALUES["segments"]
CUSTOMER_KATEGORIJOS = CUSTOMER_FILTER_VALUES["categories"]
CUSTOMER_LIST = CUSTOMER_FILTER_VALUES["customers"]
CUSTOMER_CODES = CUSTOMER_FILTER_VALUES["customer_codes"]


def _month_order_map() -> Dict[str, int]:
    """Return mapping from month code (M-01) to month order (1-based)."""

    return {code: idx + 1 for idx, code in enumerate(MENUO_TVARKA)}


MONTH_ORDER = _month_order_map()


def _add_expanding_params(stmt, params: Dict[str, Any]) -> Any:
    """Bind SQLAlchemy expanding parameters for sequence values."""

    for key, value in params.items():
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            stmt = stmt.bindparams(bindparam(key, expanding=True))
    return stmt


def load_customer_overview_df(filters: Dict[str, Any]) -> pd.DataFrame:
    """Fetch aggregated customer overview data with SQL pushdown filtering."""

    year = int(filters.get("metai") or CUSTOMER_DEFAULT_YEAR)
    years_window = sorted({y for y in range(year - 3, year + 1) if y > 0})

    year_col = CUSTOMER_COLUMNS["year"]
    month_col = CUSTOMER_COLUMNS["month"]
    branch_expr = _coalesce_expr(CUSTOMER_COLUMNS["branch"], "Nežinomas")
    segment_expr = _coalesce_expr(CUSTOMER_COLUMNS["segment"], "Nepriskirta")
    category_expr = _coalesce_expr(CUSTOMER_COLUMNS["category"], "Nepriskirta")
    customer_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer"], "Nežinomas klientas")
    code_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer_code"], "ND")
    turnover_col = CUSTOMER_COLUMNS["turnover"]
    profit_col = CUSTOMER_COLUMNS["profit"]
    quantity_col = CUSTOMER_COLUMNS["quantity"]

    where_clauses = [f"CAST({year_col} AS UNSIGNED) IN :years"]
    params: Dict[str, Any] = {"years": years_window}

    if filters.get("filialas"):
        params["filialas"] = filters["filialas"]
        where_clauses.append(f"{branch_expr} IN :filialas")

    if filters.get("segmentas"):
        params["segmentas"] = filters["segmentas"]
        where_clauses.append(f"{segment_expr} IN :segmentas")

    if filters.get("kategorija"):
        params["kategorija"] = filters["kategorija"]
        where_clauses.append(f"{category_expr} IN :kategorija")

    if filters.get("klientas"):
        params["klientas"] = [filters["klientas"]] if isinstance(filters["klientas"], str) else filters["klientas"]
        where_clauses.append(f"{customer_expr} IN :klientas")

    if filters.get("kliento_kodas") and CUSTOMER_COLUMNS["customer_code"]:
        params["kliento_kodas"] = [filters["kliento_kodas"]] if isinstance(filters["kliento_kodas"], str) else filters["kliento_kodas"]
        where_clauses.append(f"{code_expr} IN :kliento_kodas")

    if filters.get("menuo"):
        params["menuo"] = filters["menuo"]
        where_clauses.append(f"{month_col} IN :menuo")

    where_sql = "\n      AND ".join(where_clauses)

    stmt = text(
        f"""
        SELECT
            CAST({year_col} AS UNSIGNED)                                     AS Metai,
            {month_col}                                                      AS Menuo,
            {branch_expr}                                                    AS Filialas,
            {segment_expr}                                                   AS Segmentas,
            {category_expr}                                                  AS Kategorija,
            {customer_expr}                                                  AS Klientas,
            {code_expr}                                                      AS KlientoKodas,
            SUM(CAST({turnover_col} AS DECIMAL(18,2)))                        AS Apyvarta,
            SUM(CAST({profit_col}   AS DECIMAL(18,2)))                        AS Pajamos,
            SUM(CAST({quantity_col} AS DECIMAL(18,2)))                        AS Kiekis
        FROM sales
        WHERE {year_col} IS NOT NULL
          AND {month_col} IS NOT NULL
          AND {where_sql}
        GROUP BY Metai, Menuo, Filialas, Segmentas, Kategorija, Klientas, KlientoKodas
        """
    )

    stmt = _add_expanding_params(stmt, params)

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        return df.assign(**{
            "MARŽA %": pd.Series(dtype="float32"),
            "VPK": pd.Series(dtype="float32"),
            "VPP": pd.Series(dtype="float32"),
            "Kliento kodas": pd.Series(dtype="object"),
        })

    df["Metai"] = pd.to_numeric(df["Metai"], errors="coerce").astype("int16")
    df["Menuo"] = pd.Categorical(df["Menuo"].astype(str), categories=MENUO_TVARKA, ordered=True)

    for col in ["Apyvarta", "Pajamos", "Kiekis"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    df["Segmentas"] = df["Segmentas"].fillna("Nepriskirta")
    df["Kategorija"] = df["Kategorija"].fillna("Nepriskirta")
    df["Filialas"] = df["Filialas"].fillna("Nežinomas")
    df["Klientas"] = df["Klientas"].fillna("Nežinomas klientas")
    df["KlientoKodas"] = df["KlientoKodas"].fillna("ND").astype(str)
    df.rename(columns={"KlientoKodas": "Kliento kodas"}, inplace=True)

    turnover_sum = df["Apyvarta"].sum()
    profit_sum = df["Pajamos"].sum()

    df["MARŽA %"] = np.where(
        df["Apyvarta"] != 0,
        (df["Pajamos"] / df["Apyvarta"]) * 100.0,
        np.nan,
    ).astype("float32")

    df["VPK"] = np.where(
        df["Kiekis"] != 0,
        df["Apyvarta"] / df["Kiekis"],
        np.nan,
    ).astype("float32")

    df["VPP"] = np.where(
        df["Kiekis"] != 0,
        df["Pajamos"] / df["Kiekis"],
        np.nan,
    ).astype("float32")

    df["_customer_key"] = df["Kliento kodas"].where(
        df["Kliento kodas"].str.strip().ne("ND"), df["Klientas"]
    )

    if turnover_sum != 0:
        margin_from_totals = (profit_sum / turnover_sum) * 100.0
        assert not np.isnan(margin_from_totals), "Margin calculation resulted in NaN"

    return df


def _filter_by_year_and_month(
    df: pd.DataFrame,
    year: int,
    months: Optional[Sequence[str]],
) -> pd.DataFrame:
    """Return slice of df limited to requested year and optional month list."""

    subset = df[df["Metai"] == year]
    if months:
        subset = subset[subset["Menuo"].astype(str).isin(months)]
    return subset


def _determine_comparable_months(
    df: pd.DataFrame,
    year: int,
    months_filter: Optional[Sequence[str]],
) -> List[str]:
    """Identify comparable months window according to the latest month with data."""

    if df.empty:
        return []

    subset = _filter_by_year_and_month(df, year, months_filter)
    if subset.empty:
        return []

    subset = subset.copy()
    subset["_has_value"] = subset[["Apyvarta", "Pajamos", "Kiekis"]].fillna(0).sum(axis=1) != 0
    active_months = (
        subset.loc[subset["_has_value"], "Menuo"].astype(str).dropna().unique().tolist()
    )

    if not active_months:
        return []

    active_months.sort(key=lambda m: MONTH_ORDER.get(m, 0))
    latest = active_months[-1]
    latest_idx = MONTH_ORDER.get(latest, len(MENUO_TVARKA))
    comparable = [m for m in MENUO_TVARKA[:latest_idx] if m in set(active_months)]

    assert comparable, "Comparable months should not be empty when active months exist"
    return comparable


def _aggregate_metric(
    df: pd.DataFrame,
    year: int,
    months: Optional[Sequence[str]],
    metric: str,
) -> float:
    """Aggregate requested metric for the provided year and comparable month window."""

    subset = _filter_by_year_and_month(df, year, months)
    if subset.empty:
        return float("nan")

    turnover = subset["Apyvarta"].sum()
    profit = subset["Pajamos"].sum()
    quantity = subset["Kiekis"].sum()

    if metric == "Apyvarta":
        return float(turnover)
    if metric == "Pajamos":
        return float(profit)
    if metric == "Kiekis":
        return float(quantity)
    if metric == "Marža %":
        return float((profit / turnover) * 100.0) if turnover else float("nan")
    if metric == "VPK":
        return float((turnover / quantity)) if quantity else float("nan")
    if metric == "VPP":
        return float((profit / quantity)) if quantity else float("nan")
    if metric == "Klientai":
        distinct = subset[["Klientas", "Kliento kodas"]].drop_duplicates()
        count = float(len(distinct))
        assert count == float(len(distinct)), "Distinct client count mismatch"
        return count

    raise ValueError(f"Nežinomas matas: {metric}")


def _format_value(metric: str, value: float) -> str:
    """Format metric values for display in tables and KPI cards."""

    if pd.isna(value):
        return "–"

    if metric in ("Apyvarta", "Pajamos", "VPK", "VPP"):
        return _fmt_eur(value)
    if metric == "Marža %":
        return _fmt_pct(value)
    if metric in ("Kiekis", "Klientai"):
        return _fmt_qty(value)
    return f"{value:.2f}"


def compute_kpis(
    df: pd.DataFrame,
    year: int,
    months_filter: Optional[Sequence[str]],
) -> List[Dict[str, Any]]:
    """Calculate KPI card values together with YoY deltas."""

    months = _determine_comparable_months(df, year, months_filter)
    prev_year = year - 1

    results: List[Dict[str, Any]] = []

    for metric in CUSTOMER_METRIC_OPTIONS + ["Klientai"]:
        current_val = _aggregate_metric(df, year, months, metric)
        prev_val = _aggregate_metric(df, prev_year, months, metric) if months else float("nan")

        if metric == "Marža %":
            yoy_unit = "pp"
            yoy_val = current_val - prev_val if not (pd.isna(current_val) or pd.isna(prev_val)) else float("nan")
        else:
            yoy_unit = "%"
            if pd.isna(prev_val) or prev_val == 0:
                yoy_val = float("nan")
            else:
                yoy_val = ((current_val - prev_val) / prev_val) * 100.0

        results.append(
            {
                "metric": metric,
                "value": current_val,
                "formatted": _format_value(metric, current_val),
                "yoy": yoy_val,
                "yoy_unit": yoy_unit,
            }
        )

    if months:
        subset = _filter_by_year_and_month(df, year, months)
    else:
        subset = df[df["Metai"] == year]

    if not subset.empty:
        margin_total = _aggregate_metric(df, year, months, "Marža %")
        sums_margin = float("nan")
        total_turnover = subset["Apyvarta"].sum()
        if total_turnover:
            sums_margin = (subset["Pajamos"].sum() / total_turnover) * 100.0
        if not pd.isna(margin_total) and not pd.isna(sums_margin):
            assert abs(margin_total - sums_margin) < 1e-6, "Margin % must be computed from sums"

        distinct_clients = subset[["Klientas", "Kliento kodas"]].drop_duplicates()
        assert len(distinct_clients) == int(round(results[-1]["value"] or 0)), "Distinct client mismatch"

    return results


def build_general_table(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Construct columns and data for the left-hand summary DataTable."""

    columns = [
        {"name": "Segmentas", "id": "Segmentas"},
        {"name": "Apyvarta", "id": "Apyvarta"},
        {"name": "Pajamos", "id": "Pajamos"},
        {"name": "Kiekis", "id": "Kiekis"},
        {"name": "Marža %", "id": "Marža %"},
    ]

    if df.empty:
        return columns, []

    agg = (
        df.groupby("Segmentas", as_index=False)[["Apyvarta", "Pajamos", "Kiekis"]].sum()
    )
    agg["Marža %"] = np.where(
        agg["Apyvarta"] != 0,
        (agg["Pajamos"] / agg["Apyvarta"]) * 100.0,
        np.nan,
    )

    total_turnover = agg["Apyvarta"].sum()
    total_profit = agg["Pajamos"].sum()
    total_quantity = agg["Kiekis"].sum()
    total_margin = (total_profit / total_turnover) * 100.0 if total_turnover else np.nan

    totals_row = {
        "Segmentas": "Iš viso",
        "Apyvarta": _format_value("Apyvarta", total_turnover),
        "Pajamos": _format_value("Pajamos", total_profit),
        "Kiekis": _format_value("Kiekis", total_quantity),
        "Marža %": _format_value("Marža %", total_margin),
    }

    data_rows = []
    for _, row in agg.iterrows():
        data_rows.append(
            {
                "Segmentas": row["Segmentas"],
                "Apyvarta": _format_value("Apyvarta", row["Apyvarta"]),
                "Pajamos": _format_value("Pajamos", row["Pajamos"]),
                "Kiekis": _format_value("Kiekis", row["Kiekis"]),
                "Marža %": _format_value("Marža %", row["Marža %"]),
            }
        )

    data_rows.append(totals_row)
    return columns, data_rows


def build_client_matrix(
    df: pd.DataFrame,
    years: Sequence[int],
    metric: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Create the monthly dynamic table for the selected client."""

    columns = [{"name": "Metai", "id": "Metai"}] + [
        {"name": str(i), "id": str(i)} for i in range(1, 13)
    ]

    if df.empty:
        return columns, []

    data_rows: List[Dict[str, Any]] = []

    for year in years:
        subset = df[df["Metai"] == year]
        if subset.empty:
            continue

        row = {"Metai": int(year)}
        for idx, month_code in enumerate(MENUO_TVARKA, start=1):
            month_slice = subset[subset["Menuo"].astype(str) == month_code]
            value = _aggregate_metric(month_slice, year, None, metric) if not month_slice.empty else float("nan")
            row[str(idx)] = _format_value(metric, value) if not pd.isna(value) else ""
        data_rows.append(row)

    return columns, data_rows

# ==================== FIX #2: Efficient DataFrame Filtering ====================
def filter_dataframe(
    df: pd.DataFrame,
    segments: Optional[List[str]] = None,
    filialai: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    months: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Single-pass efficient DataFrame filtering.

    FIX: Instead of multiple sequential filters creating intermediate DataFrames,
    build a combined boolean mask in a single pass.
    """
    # Start with all True mask
    mask = pd.Series(True, index=df.index)

    # Apply filters using bitwise AND (&) for efficiency
    if segments:
        mask &= df["Segmentas"].isin(segments)

    if filialai:
        mask &= df["Filialas"].isin(filialai)

    if years:
        mask &= df["Metai"].isin(years)

    if months:
        mask &= df["Menuo"].astype(str).isin(months)

    # Single filter operation
    return df[mask]


# ==================== Helper Functions ====================
def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data by month."""
    if df.empty:
        return pd.DataFrame(columns=["Filialas", "Metai", "Menuo", "APYVARTA", "PAJAMOS", "KIEKIS", "MARŽA %"])

    g = df.groupby(["Filialas", "Metai", "Menuo"], as_index=False)[["APYVARTA", "PAJAMOS", "KIEKIS"]].sum()
    g["MARŽA %"] = np.where(
        g["APYVARTA"] != 0,
        (g["PAJAMOS"] / g["APYVARTA"]) * 100.0,
        np.nan,
    ).astype("float32")

    return g


def active_months_for_latest_year(
    g: pd.DataFrame,
    years_sel: List[int],
    branch: Optional[str],
    months_sel: Optional[List[str]],
) -> List[str]:
    """Determine active months for the latest selected year."""
    if g.empty:
        return []

    latest = int(sorted(years_sel)[-1])
    dd = g[g["Metai"] == latest]

    if branch:
        dd = dd[dd["Filialas"] == branch]

    months = dd["Menuo"].astype(str).dropna().unique().tolist()

    if months_sel:
        months = [m for m in months if m in set(months_sel)]

    return months or ([m for m in MENUO_TVARKA if (not months_sel) or (m in months_sel)])


# Formatting functions
def _fmt_eur(x):
    if pd.isna(x):
        return "-"
    return f"{int(round(float(x))):,}".replace(",", " ") + " €"


def _fmt_pct(x):
    if pd.isna(x):
        return "-"
    return f"{float(x):.2f} %"


def _fmt_qty(x):
    if pd.isna(x):
        return "-"
    return f"{int(float(x)):,}".replace(",", " ")


def _fmt_signed_pct(x):
    if pd.isna(x):
        return "–"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f} %"


def _fmt_signed_pp(x):
    if pd.isna(x):
        return "–"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f} pp"


# ==================== Advisor Functions ====================
def aggregate_by_vendor(dd: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data by vendor/manufacturer."""
    cols = ["Gamintojas", "Apyvarta", "Pajamos", "Marža %", "Kiekis"]

    if dd.empty:
        return pd.DataFrame(columns=cols)

    # Aggregate sums by manufacturer
    g = dd.groupby("Gamintojas", as_index=False)[["Apyvarta", "Pajamos", "Kiekis"]].sum()

    # Calculate margin correctly: (Pajamos / Apyvarta) * 100
    # This is the CORRECT formula - not weighted average!
    g["Marža %"] = np.where(
        g["Apyvarta"] != 0,
        (g["Pajamos"] / g["Apyvarta"]) * 100.0,
        np.nan,
    )

    # Sort by turnover
    out = g.sort_values("Apyvarta", ascending=False, kind="mergesort")

    # Calculate total row
    total_apyvarta = out["Apyvarta"].sum()
    total_pajamos = out["Pajamos"].sum()
    total_marza = (total_pajamos / total_apyvarta * 100.0) if total_apyvarta != 0 else np.nan

    total = pd.DataFrame({
        "Gamintojas": ["Iš viso"],
        "Apyvarta": [total_apyvarta],
        "Pajamos": [total_pajamos],
        "Marža %": [total_marza],
        "Kiekis": [out["Kiekis"].sum()],
    })

    out = pd.concat([out, total], ignore_index=True)

    # Format for display
    out["Apyvarta"] = out["Apyvarta"].map(_fmt_eur)
    out["Pajamos"] = out["Pajamos"].map(_fmt_eur)
    out["Marža %"] = out["Marža %"].map(lambda v: "-" if pd.isna(v) else f"{round(float(v), 1)} %")
    out["Kiekis"] = out["Kiekis"].map(_fmt_qty)

    return out[cols]


# ==================== FIX #3: Extract Business Logic from Callbacks ====================
class SummaryCalculator:
    """Encapsulate summary tab business logic."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.monthly_agg = aggregate_monthly(df)

    def create_branch_figure(
        self,
        branch: str,
        metric: str,
        chart_type: str,
        years_sel: List[int],
        months_sel: Optional[List[str]],
    ) -> go.Figure:
        """Create figure for a specific branch."""
        b = self.monthly_agg[self.monthly_agg["Filialas"] == branch]
        fig = go.Figure()

        if b.empty:
            fig.update_layout(
                title=f"{branch} – {metric}: duomenų nėra",
                height=360,
                annotations=[
                    {
                        "text": "Nėra duomenų su pasirinktais filtrais",
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "showarrow": False,
                        "font": {"size": 14, "color": IC_GRAY},
                    }
                ],
            )
            return fig

        months_axis = [m for m in MENUO_TVARKA if (not months_sel) or (m in months_sel)]
        p = b.pivot_table(index="Menuo", columns="Metai", values=metric, aggfunc="first").reindex(months_axis)

        # Identify active months for latest year
        latest_year = int(sorted(years_sel)[-1])
        b_latest = b[b["Metai"] == latest_year]
        active_latest = set(
            b_latest.loc[
                (b_latest[["APYVARTA", "PAJAMOS", "KIEKIS"]].fillna(0).sum(axis=1) > 0),
                "Menuo",
            ]
            .astype(str)
            .tolist()
        )

        # Add traces for each year
        for y in years_sel:
            if y not in p.columns:
                continue

            color = COLORWAY_YEARS.get(int(y), IC_BLACK)
            yvals = p[y].copy()

            # Hide future months for latest year
            if int(y) == latest_year:
                mask = [m not in active_latest for m in months_axis]
                yvals.loc[mask] = np.nan

            if chart_type == "line":
                fig.add_trace(
                    go.Scatter(
                        x=months_axis,
                        y=yvals,
                        mode="lines+markers",
                        name=str(y),
                        line=dict(color=color),
                    )
                )
            else:
                fig.add_trace(
                    go.Bar(
                        x=months_axis,
                        y=yvals,
                        name=str(y),
                        marker=dict(color=color),
                    )
                )

        fig.update_layout(
            height=360,
            margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            paper_bgcolor=IC_WHITE,
            plot_bgcolor=IC_WHITE,
            hovermode="x unified",
        )

        return fig

    def build_monthly_table(
        self,
        years_sel: List[int],
        months_sel: Optional[List[str]],
        metric: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Build monthly summary table data."""
        months_axis_table = active_months_for_latest_year(self.monthly_agg, years_sel, None, months_sel)

        if metric == "MARŽA %":
            use = self.monthly_agg[["Filialas", "Metai", "Menuo", "PAJAMOS", "APYVARTA"]].copy()
            use["value"] = np.where(
                use["APYVARTA"] != 0,
                (use["PAJAMOS"] / use["APYVARTA"]) * 100.0,
                np.nan,
            )
            totals = (
                self.monthly_agg.groupby(["Filialas", "Metai"], as_index=False)[["PAJAMOS", "APYVARTA"]]
                .sum()
                .assign(
                    Bendra=lambda d: np.where(
                        d["APYVARTA"] != 0,
                        (d["PAJAMOS"] / d["APYVARTA"]) * 100.0,
                        np.nan,
                    )
                )
            )
        else:
            use = self.monthly_agg[["Filialas", "Metai", "Menuo", metric]].rename(columns={metric: "value"})
            totals = (
                self.monthly_agg.groupby(["Filialas", "Metai"], as_index=False)[metric]
                .sum()
                .rename(columns={metric: "Bendra"})
            )

        p = (
            use.pivot_table(index=["Filialas", "Metai"], columns="Menuo", values="value", aggfunc="first")
            .reindex(columns=months_axis_table)
        )
        tdf = p.reset_index().merge(totals[["Filialas", "Metai", "Bendra"]], on=["Filialas", "Metai"], how="left")

        columns = [{"name": c, "id": c} for c in tdf.columns]

        # Format for display
        disp = tdf.copy()
        vals = [c for c in tdf.columns if c in months_axis_table + ["Bendra"]]

        if metric in ["APYVARTA", "PAJAMOS"]:
            for c in vals:
                disp[c] = disp[c].map(_fmt_eur)
        elif metric == "MARŽA %":
            for c in vals:
                disp[c] = disp[c].map(_fmt_pct)
        else:
            for c in vals:
                disp[c] = disp[c].map(_fmt_qty)

        return columns, disp.to_dict("records")

    def calculate_kpis(
        self,
        this_year: int,
        prev_year: Optional[int],
        metric: str,
        months_sel: Optional[List[str]],
    ) -> List[html.Div]:
        """Calculate KPI cards with YoY comparison."""

        def sum_metric_block(dd: pd.DataFrame) -> Tuple[float, float]:
            """Sum metric for active months, comparing same months YoY."""
            cur = dd[dd["Metai"] == this_year].copy()
            active_cur = set(
                cur.loc[
                    (cur[["APYVARTA", "PAJAMOS", "KIEKIS"]].fillna(0).sum(axis=1) > 0),
                    "Menuo",
                ]
                .astype(str)
                .tolist()
            )

            if months_sel:
                active_cur = {m for m in active_cur if m in months_sel}

            if not active_cur:
                return (np.nan, np.nan)

            def agg(df: pd.DataFrame) -> float:
                if metric == "MARŽA %":
                    ap = df["APYVARTA"].sum()
                    pj = df["PAJAMOS"].sum()
                    return (pj / ap) * 100.0 if ap else np.nan
                else:
                    return df[metric].sum()

            this_sum = agg(cur[cur["Menuo"].astype(str).isin(active_cur)])

            if prev_year is None:
                prev_sum = np.nan
            else:
                prev = dd[dd["Metai"] == prev_year]
                prev_sum = agg(prev[prev["Menuo"].astype(str).isin(active_cur)])

            return (this_sum, prev_sum)

        def yoy_text_color(this_val: float, prev_val: float) -> Tuple[str, str]:
            """Calculate YoY percentage change and color."""
            if pd.isna(prev_val) or float(prev_val) == 0 or pd.isna(this_val):
                return "–", IC_GRAY

            yoy = (float(this_val) / float(prev_val) - 1.0) * 100.0
            txt = _fmt_signed_pct(yoy)
            col = GREEN if yoy >= 0 else RED
            return txt, col

        def fmt_main(v: float) -> str:
            """Format main metric value."""
            if metric in ["APYVARTA", "PAJAMOS"]:
                return _fmt_eur(v)
            if metric == "MARŽA %":
                return _fmt_pct(v)
            return _fmt_qty(v)

        def card(lbl: str, v: float, yoy_text: str, yoy_color: str) -> html.Div:
            """Create KPI card."""
            return html.Div(
                [
                    html.Div(lbl, style={"fontSize": "12px", "color": IC_NAVY, "fontWeight": 700}),
                    html.Div(fmt_main(v), style={"fontSize": "22px", "fontWeight": 700, "color": IC_BLACK}),
                    html.Div(f"YoY: {yoy_text}", style={"fontSize": "12px", "marginTop": "2px", "color": yoy_color}),
                ],
                style={"background": IC_WHITE, "border": f"1px solid {IC_GRAY}", "borderRadius": "10px", "padding": "10px 12px"},
            )

        # Calculate for each branch
        g_l51 = self.monthly_agg[self.monthly_agg["Filialas"] == "L51"]
        g_l52 = self.monthly_agg[self.monthly_agg["Filialas"] == "L52"]

        v_l51_this, v_l51_prev = sum_metric_block(g_l51)
        v_l52_this, v_l52_prev = sum_metric_block(g_l52)
        v_tot_this, v_tot_prev = sum_metric_block(self.monthly_agg)

        yoy_l51_txt, col_l51 = yoy_text_color(v_l51_this, v_l51_prev)
        yoy_l52_txt, col_l52 = yoy_text_color(v_l52_this, v_l52_prev)
        yoy_tot_txt, col_tot = yoy_text_color(v_tot_this, v_tot_prev)

        return [
            card(f"L51 – {metric}", v_l51_this, yoy_l51_txt, col_l51),
            card(f"L52 – {metric}", v_l52_this, yoy_l52_txt, col_l52),
            card(f"Bendra – {metric}", v_tot_this, yoy_tot_txt, col_tot),
        ]


__all__ = [
    "IC_RED",
    "IC_NAVY",
    "IC_GRAY",
    "IC_BLACK",
    "IC_WHITE",
    "IC_BG",
    "COLORWAY_YEARS",
    "GREEN",
    "RED",
    "MENUO_TVARKA",
    "MENUO_LABELS_LT",
    "METRICS",
    "df_sums",
    "df_adv",
    "SEGMENT_OPTIONS",
    "FILIALAS_OPTIONS",
    "YEAR_OPTIONS",
    "YEARS_ADV",
    "FILIALAI_ADV",
    "SEGMENTAI_ADV",
    "KATEGORIJOS",
    "filter_dataframe",
    "aggregate_by_vendor",
    "SummaryCalculator",
]
