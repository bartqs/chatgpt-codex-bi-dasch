"""
Shared application data, constants, and business logic extracted from the
original single-file Dash notebook implementation.

This module preserves the exact behavior, calculations, and styling helpers
used across the dashboard pages.
"""

from __future__ import annotations

import os
import re
import time
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
COLORWAY_YEARS = {2022: IC_NAVY, 2023: IC_GRAY, 2024: IC_BLACK, 2025: IC_RED, 2026: "#444"}
GREEN = "#198754"
RED = "#C62828"

MENUO_TVARKA = [f"M-{i:02d}" for i in range(1, 13)]
MENUO_LABELS_LT = ["Sau", "Vas", "Kov", "Bal", "Geg", "Bir", "Lie", "Rgp", "Rgs", "Spa", "Lap", "Gru"]
METRICS = ["APYVARTA", "PAJAMOS", "MARŽA %", "KIEKIS"]

CATEGORY_GROUP_PRIORITY = (
    "FILTERS",
    "SUSPENSION",
    "ENGINE",
    "LUBRICANTS & LIQUIDS",
    "BODY PARTS",
    "GASKETS",
    "SHOCK ABSORBTION",
    "BRAKES, OTHER ELEMENTS",
    "OTHER PRODUCTS",
    "TIMING",
    "BRAKE PADS",
    "ELECTRIC",
    "BRAKE DISCS",
    "WHEEL",
    "IGNITION AND PLUGS",
    "GARAGE EQUIPMENT",
    "COOLING",
    "DRIVE",
    "EXHAUST SYSTEM",
    "WHEEL BEARING, HUB",
    "WIPER BLADE",
    "CLUTCH",
    "AIR CONDITIONING",
    "ACCESSORIES",
    "PNEUMATICS",
    "BATTERY",
    "CLOTHES AND HELMETS",
)


def _normalize_category_group_name(name: Any) -> str:
    if name is None:
        return ""
    normalized = re.sub(r"[^A-Z0-9]+", "", str(name).upper())
    return normalized


_CATEGORY_GROUP_PRIORITY_MAP = {
    _normalize_category_group_name(label): idx
    for idx, label in enumerate(CATEGORY_GROUP_PRIORITY)
}


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

CUSTOMER_METRICS = ["APYVARTA", "PAJAMOS", "MARŽA %", "KIEKIS"]
CUSTOMER_COLORWAY = {2022: IC_NAVY, 2023: IC_GRAY, 2024: IC_BLACK, 2025: IC_RED, 2026: "#444"}
MONTH_ORDER = {code: idx + 1 for idx, code in enumerate(MENUO_TVARKA)}
MONTH_NAME_MAP = {code: MENUO_LABELS_LT[idx] for idx, code in enumerate(MENUO_TVARKA)}


def _add_expanding_params(stmt, params):
    """Attach SQLAlchemy expanding bind parameters for IN clauses."""

    for key, value in list(params.items()):
        if isinstance(value, (list, tuple, set)) and value:
            stmt = stmt.bindparams(bindparam(key, expanding=True))
    return stmt


def _resolve_customer_columns() -> Dict[str, Optional[str]]:
    """Identify source columns for the customer overview page."""

    cols = get_columns()
    manager_candidates = [
        "Pardavimų vadybininkas",
        "Vadybininkas",
        "Pardavėjas",
        "Account manager",
    ]
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
        "Kategorija [Name]",
        "Category",
    ]

    vendor_candidates = [
        "Gamintojas (pavad)",
        "Gamintojas",
        "Gamintojas [Name]",
        "Manufacturer",
        "Gamintojas pavadinimas",
    ]

    return {
        "year": "`Year [Name] PE-Y01`",
        "month": "`Month [Short name] PE-M02`",
        "manager": pick_col(cols, manager_candidates) or "`Vadybininkas`",
        "customer": pick_col(cols, customer_candidates) or "`Klientas`",
        "customer_code": pick_col(cols, customer_code_candidates),
        "category": pick_col(cols, category_candidates),
        "vendor": pick_col(cols, vendor_candidates),
        "turnover": "`APYVARTA`",
        "profit": "`PAJAMOS`",
        "quantity": "`KIEKIS`",
    }


CUSTOMER_COLUMNS = _resolve_customer_columns()


def _coalesce_expr(column: Optional[str], default: str) -> str:
    """Return SQL that replaces NULLs with a default value."""

    if not column:
        return f"'{default}'"
    return f"COALESCE({column}, '{default}')"


_CACHE_TTL_SECONDS = 300
_customer_transactions_cache: Dict[Tuple[Any, ...], Tuple[float, pd.DataFrame]] = {}
_customer_metric_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_customer_category_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_customer_category_detail_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_customer_category_vendor_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}


@lru_cache(maxsize=1)
def _load_category_mapping() -> pd.DataFrame:
    """Fetch category → category group relationships."""

    stmt = text(
        """
        SELECT
            COALESCE(`Kategorija`, 'Nepriskirta')        AS Kategorija,
            COALESCE(`Kategorijos_grupe`, 'Nepriskirta') AS Kategorijos_grupe
        FROM kategorijos
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)

    df["Kategorija"] = df["Kategorija"].fillna("Nepriskirta")
    df["Kategorijos_grupe"] = df["Kategorijos_grupe"].fillna("Nepriskirta")
    df = df.drop_duplicates(subset=["Kategorija"])
    return df


def _cache_key_from_filters(prefix: str, filters: Dict[str, Any]) -> Tuple[Any, ...]:
    """Create a stable cache key from filter selections."""

    normalized: List[Any] = [prefix]
    for key in sorted(filters.keys()):
        value = filters[key]
        if value is None or value == []:
            normalized.append((key, None))
            continue

        if isinstance(value, (list, tuple, set)):
            normalized.append((key, tuple(sorted(map(str, value)))))
        else:
            normalized.append((key, value))
    return tuple(normalized)


def _cache_get(cache: Dict[Tuple[Any, ...], Tuple[float, Any]], key: Tuple[Any, ...]):
    entry = cache.get(key)
    if not entry:
        return None

    timestamp, value = entry
    if time.time() - timestamp > _CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None

    if isinstance(value, pd.DataFrame):
        return value.copy(deep=False)
    return value


def _cache_set(cache: Dict[Tuple[Any, ...], Tuple[float, Any]], key: Tuple[Any, ...], value: Any) -> None:
    if isinstance(value, pd.DataFrame):
        cache[key] = (time.time(), value.copy(deep=False))
    else:
        cache[key] = (time.time(), value)


@lru_cache(maxsize=1)
def get_customer_filter_frame() -> pd.DataFrame:
    """Return a frame with manager → client → code relationships."""

    year_col = CUSTOMER_COLUMNS["year"]
    month_col = CUSTOMER_COLUMNS["month"]
    manager_expr = _coalesce_expr(CUSTOMER_COLUMNS["manager"], "Nežinomas")
    customer_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer"], "Nežinomas klientas")
    code_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer_code"], "ND")

    stmt = text(
        f"""
        SELECT DISTINCT
            {manager_expr} AS Vadybininkas,
            {customer_expr} AS Klientas,
            {code_expr}     AS KlientoKodas
        FROM sales
        WHERE {year_col} IS NOT NULL
          AND {month_col} IS NOT NULL
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)

    df["Vadybininkas"] = df["Vadybininkas"].fillna("Nežinomas")
    df["Klientas"] = df["Klientas"].fillna("Nežinomas klientas")
    df["KlientoKodas"] = df["KlientoKodas"].fillna("ND").astype(str)
    df.rename(columns={"KlientoKodas": "Kliento kodas"}, inplace=True)
    return df


@lru_cache(maxsize=1)
def get_customer_year_options() -> List[int]:
    """Return sorted list of available years."""

    year_col = CUSTOMER_COLUMNS["year"]
    month_col = CUSTOMER_COLUMNS["month"]

    stmt = text(
        f"""
        SELECT DISTINCT CAST({year_col} AS UNSIGNED) AS Metai
        FROM sales
        WHERE {year_col} IS NOT NULL
          AND {month_col} IS NOT NULL
        ORDER BY Metai
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn)

    df["Metai"] = pd.to_numeric(df["Metai"], errors="coerce")
    years = df.dropna()["Metai"].astype(int).tolist()
    return years


def get_latest_customer_year() -> Optional[int]:
    years = get_customer_year_options()
    return max(years) if years else None


def _normalize_filter_payload(filters: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "vadybininkas": filters.get("vadybininkas") or [],
        "klientas": filters.get("klientas") or [],
        "kliento_kodas": filters.get("kliento_kodas") or [],
        "metai": filters.get("metai") or [],
    }


def fetch_customer_transactions(filters: Dict[str, Any]) -> pd.DataFrame:
    """Load transaction-level data for the selected customer context."""

    normalized = _normalize_filter_payload(filters)
    if not normalized["klientas"]:
        return pd.DataFrame(
            columns=[
                "Metai",
                "Menuo",
                "Vadybininkas",
                "Klientas",
                "Kliento kodas",
                "Kategorija",
                "Gamintojas (pavad)",
                "Apyvarta",
                "Pajamos",
                "Kiekis",
            ]
        )

    cache_key = _cache_key_from_filters("customer_tx", normalized)
    cached = _cache_get(_customer_transactions_cache, cache_key)
    if cached is not None:
        return cached.copy(deep=False)

    year_col = CUSTOMER_COLUMNS["year"]
    month_col = CUSTOMER_COLUMNS["month"]
    manager_expr = _coalesce_expr(CUSTOMER_COLUMNS["manager"], "Nežinomas")
    customer_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer"], "Nežinomas klientas")
    code_expr = _coalesce_expr(CUSTOMER_COLUMNS["customer_code"], "ND")
    category_expr = _coalesce_expr(CUSTOMER_COLUMNS.get("category"), "Nepriskirta")
    vendor_expr = _coalesce_expr(CUSTOMER_COLUMNS.get("vendor"), "Nežinomas gamintojas")
    turnover_col = CUSTOMER_COLUMNS["turnover"]
    profit_col = CUSTOMER_COLUMNS["profit"]
    quantity_col = CUSTOMER_COLUMNS["quantity"]

    where_clauses = [f"{year_col} IS NOT NULL", f"{month_col} IS NOT NULL"]
    params: Dict[str, Any] = {}

    if normalized["metai"]:
        where_clauses.append("CAST(" + year_col + " AS UNSIGNED) IN :metai")
        params["metai"] = [int(y) for y in normalized["metai"]]

    if normalized["vadybininkas"]:
        where_clauses.append(f"{manager_expr} IN :vadybininkas")
        params["vadybininkas"] = list(normalized["vadybininkas"])

    if normalized["klientas"]:
        where_clauses.append(f"{customer_expr} IN :klientas")
        params["klientas"] = list(normalized["klientas"])

    if normalized["kliento_kodas"] and CUSTOMER_COLUMNS["customer_code"]:
        where_clauses.append(f"{code_expr} IN :kliento_kodas")
        params["kliento_kodas"] = list(normalized["kliento_kodas"])

    where_sql = "\n          AND ".join(where_clauses)

    stmt = text(
        f"""
        SELECT
            CAST({year_col} AS UNSIGNED) AS Metai,
            {month_col}                  AS Menuo,
            {manager_expr}               AS Vadybininkas,
            {customer_expr}              AS Klientas,
            {code_expr}                  AS KlientoKodas,
            {category_expr}                 AS Kategorija,
            {vendor_expr}                   AS GamintojasPavad,
            CAST({turnover_col} AS DECIMAL(18,2)) AS Apyvarta,
            CAST({profit_col}   AS DECIMAL(18,2)) AS Pajamos,
            CAST({quantity_col} AS DECIMAL(18,2)) AS Kiekis
        FROM sales
        WHERE {where_sql}
        """
    )

    stmt = _add_expanding_params(stmt, params)

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        _cache_set(_customer_transactions_cache, cache_key, df)
        return df

    df["Metai"] = pd.to_numeric(df["Metai"], errors="coerce").astype("int32", errors="ignore")
    df["Menuo"] = df["Menuo"].astype(str)
    df.rename(
        columns={
            "KlientoKodas": "Kliento kodas",
            "GamintojasPavad": "Gamintojas (pavad)",
        },
        inplace=True,
    )
    df["Vadybininkas"] = df["Vadybininkas"].fillna("Nežinomas")
    df["Klientas"] = df["Klientas"].fillna("Nežinomas klientas")
    df["Kliento kodas"] = df["Kliento kodas"].fillna("ND").astype(str)
    df["Kategorija"] = df["Kategorija"].fillna("Nepriskirta")
    df["Gamintojas (pavad)"] = df["Gamintojas (pavad)"].fillna("Nežinomas gamintojas")
    for col in ["Apyvarta", "Pajamos", "Kiekis"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    _cache_set(_customer_transactions_cache, cache_key, df)
    return df.copy(deep=False)


def compute_customer_monthly_aggregation(
    filters: Dict[str, Any], metric: str
) -> Tuple[pd.DataFrame, List[int]]:
    """Aggregate customer transactions by year and month.

    Returns a tuple with the aggregated DataFrame and the list of month indexes
    that exist for the latest year (used for comparable-month calculations).
    """

    normalized = _normalize_filter_payload(filters)
    normalized["metric"] = metric
    cache_key = _cache_key_from_filters("customer_metric", normalized)
    cached = _cache_get(_customer_metric_cache, cache_key)
    if cached is not None:
        frame, latest_months_cached = cached
        return frame.copy(deep=False), list(latest_months_cached)

    tx = fetch_customer_transactions(filters)
    empty = pd.DataFrame(
        columns=["Metai", "Menuo", "Mėnuo", "Apyvarta", "Pajamos", "Kiekis", "MARŽA %"]
    )

    if tx.empty:
        _cache_set(_customer_metric_cache, cache_key, (empty, tuple()))
        return empty, []

    years = normalized["metai"] or sorted(tx["Metai"].dropna().unique().tolist())
    if not years:
        _cache_set(_customer_metric_cache, cache_key, (empty, tuple()))
        return empty, []

    tx = tx[tx["Metai"].isin([int(y) for y in years])]
    grouped = (
        tx.groupby(["Metai", "Menuo"], as_index=False)[["Apyvarta", "Pajamos", "Kiekis"]]
        .sum()
        .sort_values(["Metai", "Menuo"], kind="mergesort")
    )

    if grouped.empty:
        _cache_set(_customer_metric_cache, cache_key, (empty, tuple()))
        return empty, []

    grouped["Menuo"] = grouped["Menuo"].astype(str)
    grouped["Mėnuo"] = grouped["Menuo"].map(MONTH_ORDER)
    grouped = grouped.dropna(subset=["Mėnuo"])
    grouped["Mėnuo"] = grouped["Mėnuo"].astype(int)

    grouped["MARŽA %"] = np.where(
        grouped["Apyvarta"] != 0,
        (grouped["Pajamos"] / grouped["Apyvarta"]) * 100.0,
        np.nan,
    )

    latest_year = max(grouped["Metai"].unique().tolist())
    latest_months = sorted(
        grouped.loc[grouped["Metai"] == latest_year, "Mėnuo"].astype(int).unique().tolist()
    )

    grouped = grouped.sort_values(["Mėnuo", "Metai"], kind="mergesort").reset_index(drop=True)
    _cache_set(
        _customer_metric_cache,
        cache_key,
        (grouped.copy(deep=False), tuple(latest_months)),
    )
    return grouped.copy(deep=False), latest_months


# ==================== Customer Category Aggregations ====================
def _previous_month(year: int, month: int) -> Tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _metric_sum_for_entries(metric: str, entries: List[Dict[str, float]], average: bool) -> Optional[float]:
    if not entries:
        return None

    if metric == "MARŽA %":
        turnover = sum(item.get("Apyvarta", 0.0) for item in entries)
        profit = sum(item.get("Pajamos", 0.0) for item in entries)
        if turnover == 0:
            return None
        return (profit / turnover) * 100.0

    field = {
        "APYVARTA": "Apyvarta",
        "PAJAMOS": "Pajamos",
        "KIEKIS": "Kiekis",
    }.get(metric)

    if not field:
        return None

    total = sum(item.get(field, 0.0) for item in entries)
    if average:
        count = len(entries)
        return (total / count) if count else None
    return total


def compute_customer_category_group_summary(
    filters: Dict[str, Any], metric: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Aggregate customer results by category group with rolling windows."""

    normalized = _normalize_filter_payload(filters)
    normalized["metric"] = metric
    cache_key = _cache_key_from_filters("customer_category", normalized)
    cached = _cache_get(_customer_category_cache, cache_key)
    if cached is not None:
        frame, meta = cached
        return frame.copy(deep=False), dict(meta)

    empty = pd.DataFrame(
        columns=[
            "Kategorijos grupe",
            "last_value",
            "previous_value",
            "avg_3m",
            "avg_6m",
        ]
    )

    tx = fetch_customer_transactions(filters)
    if tx.empty:
        _cache_set(_customer_category_cache, cache_key, (empty, {}))
        return empty, {}

    years = normalized["metai"] or sorted(tx["Metai"].dropna().unique().tolist())
    if years:
        tx = tx[tx["Metai"].isin([int(y) for y in years])]

    if tx.empty:
        _cache_set(_customer_category_cache, cache_key, (empty, {}))
        return empty, {}

    mapping = _load_category_mapping()
    tx = tx.merge(mapping, how="left", on="Kategorija")
    tx["Kategorijos_grupe"] = tx["Kategorijos_grupe"].fillna("Nepriskirta")

    tx["Menuo"] = tx["Menuo"].astype(str)
    tx["Mėnuo"] = tx["Menuo"].map(MONTH_ORDER)
    tx = tx.dropna(subset=["Mėnuo"])
    tx["Mėnuo"] = tx["Mėnuo"].astype(int)

    if tx.empty:
        _cache_set(_customer_category_cache, cache_key, (empty, {}))
        return empty, {}

    tx["YearMonth"] = tx["Metai"] * 100 + tx["Mėnuo"]
    last_idx = tx["YearMonth"].max()
    if pd.isna(last_idx):
        _cache_set(_customer_category_cache, cache_key, (empty, {}))
        return empty, {}

    last_year = int(last_idx // 100)
    last_month = int(last_idx % 100)
    prev_year, prev_month = _previous_month(last_year, last_month)

    available_periods = set(
        (int(row.Metai), int(row.Mėnuo))
        for row in tx[["Metai", "Mėnuo"]].drop_duplicates().itertuples(index=False)
    )

    prev_period = (prev_year, prev_month) if (prev_year, prev_month) in available_periods else None

    grouped = (
        tx.groupby(["Kategorijos_grupe", "Metai", "Mėnuo"], as_index=False)[
            ["Apyvarta", "Pajamos", "Kiekis"]
        ]
        .sum()
    )

    group_records: Dict[str, Dict[Tuple[int, int], Dict[str, float]]] = {}
    for row in grouped.itertuples(index=False):
        key = row.Kategorijos_grupe
        group_records.setdefault(key, {})[(int(row.Metai), int(row.Mėnuo))] = {
            "Apyvarta": float(row.Apyvarta),
            "Pajamos": float(row.Pajamos),
            "Kiekis": float(row.Kiekis),
        }

    def periods_window(length: int) -> List[Tuple[int, int]]:
        periods: List[Tuple[int, int]] = []
        year, month = last_year, last_month
        for _ in range(length):
            periods.append((year, month))
            year, month = _previous_month(year, month)
        return periods

    window3 = [p for p in periods_window(3) if p in available_periods]
    window6 = [p for p in periods_window(6) if p in available_periods]

    rows: List[Dict[str, Any]] = []
    for group, values in group_records.items():
        last_entries = [values[p] for p in [(last_year, last_month)] if p in values]
        prev_entries = [values[p] for p in [prev_period] if p and p in values]
        win3_entries = [values[p] for p in window3 if p in values]
        win6_entries = [values[p] for p in window6 if p in values]

        last_value = _metric_sum_for_entries(metric, last_entries, average=False)
        previous_value = _metric_sum_for_entries(metric, prev_entries, average=False)
        avg_3m = _metric_sum_for_entries(metric, win3_entries, average=True)
        avg_6m = _metric_sum_for_entries(metric, win6_entries, average=True)

        rows.append(
            {
                "Kategorijos grupe": group,
                "last_value": last_value,
                "previous_value": previous_value,
                "avg_3m": avg_3m,
                "avg_6m": avg_6m,
            }
        )

    if not rows:
        _cache_set(_customer_category_cache, cache_key, (empty, {}))
        return empty, {}

    result = pd.DataFrame(rows)
    if not result.empty:
        result["_normalized"] = result["Kategorijos grupe"].map(
            _normalize_category_group_name
        )
        result["_priority_rank"] = result["_normalized"].map(
            _CATEGORY_GROUP_PRIORITY_MAP
        )
        max_rank = len(CATEGORY_GROUP_PRIORITY)
        result["_priority_flag"] = result["_priority_rank"].isna().astype(int)
        result["_priority_rank"] = (
            result["_priority_rank"].fillna(max_rank).astype(int)
        )
        result["_alpha"] = result["Kategorijos grupe"].astype(str).str.casefold()
        result.loc[result["_priority_flag"] == 0, "_alpha"] = ""
        result.sort_values(
            by=["_priority_flag", "_priority_rank", "_alpha", "last_value"],
            ascending=[True, True, True, False],
            inplace=True,
            kind="mergesort",
        )
        result.drop(
            columns=["_normalized", "_priority_rank", "_priority_flag", "_alpha"],
            inplace=True,
        )

    metadata = {
        "last_period": (last_year, last_month),
        "previous_period": prev_period,
        "window3_periods": [
            (int(period[0]), int(period[1])) for period in window3
        ],
        "window6_periods": [
            (int(period[0]), int(period[1])) for period in window6
        ],
    }

    _cache_set(_customer_category_cache, cache_key, (result.copy(deep=False), metadata))
    return result.copy(deep=False), metadata


def compute_customer_category_detail_summary(
    filters: Dict[str, Any], metric: str, category_group: Optional[str]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return category-level breakdown for a selected category group."""

    normalized = _normalize_filter_payload(filters)
    normalized["metric"] = metric
    normalized["category_group"] = category_group or None
    cache_key = _cache_key_from_filters("customer_category_detail", normalized)
    cached = _cache_get(_customer_category_detail_cache, cache_key)
    if cached is not None:
        frame, meta = cached
        return frame.copy(deep=False), dict(meta)

    empty = pd.DataFrame(
        columns=[
            "Kategorija",
            "last_value",
            "previous_value",
            "avg_3m",
            "avg_6m",
        ]
    )

    if not category_group:
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    tx = fetch_customer_transactions(filters)
    if tx.empty:
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    mapping = _load_category_mapping()
    tx = tx.merge(mapping, how="left", on="Kategorija")
    tx["Kategorijos_grupe"] = tx["Kategorijos_grupe"].fillna("Nepriskirta")

    tx["Menuo"] = tx["Menuo"].astype(str)
    tx["Mėnuo"] = tx["Menuo"].map(MONTH_ORDER)
    tx = tx.dropna(subset=["Mėnuo"])
    if tx.empty:
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    tx["Mėnuo"] = tx["Mėnuo"].astype(int)
    tx["YearMonth"] = tx["Metai"] * 100 + tx["Mėnuo"]

    last_idx = tx["YearMonth"].max()
    if pd.isna(last_idx):
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    last_year = int(last_idx // 100)
    last_month = int(last_idx % 100)
    prev_year, prev_month = _previous_month(last_year, last_month)

    available_periods = set(
        (int(row.Metai), int(row.Mėnuo))
        for row in tx[["Metai", "Mėnuo"]].drop_duplicates().itertuples(index=False)
    )
    prev_period = (prev_year, prev_month) if (prev_year, prev_month) in available_periods else None

    def periods_window(length: int) -> List[Tuple[int, int]]:
        periods: List[Tuple[int, int]] = []
        year, month = last_year, last_month
        for _ in range(length):
            periods.append((year, month))
            year, month = _previous_month(year, month)
        return periods

    window3 = [p for p in periods_window(3) if p in available_periods]
    window6 = [p for p in periods_window(6) if p in available_periods]

    tx_group = tx[tx["Kategorijos_grupe"] == category_group]
    if tx_group.empty:
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    grouped = (
        tx_group.groupby(["Kategorija", "Metai", "Mėnuo"], as_index=False)[
            ["Apyvarta", "Pajamos", "Kiekis"]
        ]
        .sum()
    )

    category_records: Dict[str, Dict[Tuple[int, int], Dict[str, float]]] = {}
    for row in grouped.itertuples(index=False):
        key = row.Kategorija
        category_records.setdefault(key, {})[(int(row.Metai), int(row.Mėnuo))] = {
            "Apyvarta": float(row.Apyvarta),
            "Pajamos": float(row.Pajamos),
            "Kiekis": float(row.Kiekis),
        }

    rows: List[Dict[str, Any]] = []
    for category, values in category_records.items():
        last_entries = [values[p] for p in [(last_year, last_month)] if p in values]
        prev_entries = [values[p] for p in [prev_period] if p and p in values]
        win3_entries = [values[p] for p in window3 if p in values]
        win6_entries = [values[p] for p in window6 if p in values]

        rows.append(
            {
                "Kategorija": category,
                "last_value": _metric_sum_for_entries(metric, last_entries, average=False),
                "previous_value": _metric_sum_for_entries(metric, prev_entries, average=False),
                "avg_3m": _metric_sum_for_entries(metric, win3_entries, average=True),
                "avg_6m": _metric_sum_for_entries(metric, win6_entries, average=True),
            }
        )

    if not rows:
        _cache_set(_customer_category_detail_cache, cache_key, (empty, {}))
        return empty, {}

    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(
            by="last_value",
            ascending=False,
            inplace=True,
            kind="mergesort",
        )

    metadata = {
        "last_period": (last_year, last_month),
        "previous_period": prev_period,
        "window3_periods": [
            (int(period[0]), int(period[1])) for period in window3
        ],
        "window6_periods": [
            (int(period[0]), int(period[1])) for period in window6
        ],
    }

    _cache_set(_customer_category_detail_cache, cache_key, (result.copy(deep=False), metadata))
    return result.copy(deep=False), metadata


def compute_customer_category_vendor_summary(
    filters: Dict[str, Any],
    metric: str,
    category_group: Optional[str],
    category_name: Optional[str],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Return vendor-level breakdown for the selected category."""

    normalized = _normalize_filter_payload(filters)
    normalized["metric"] = metric
    normalized["category_group"] = category_group or None
    normalized["category_name"] = category_name or None
    cache_key = _cache_key_from_filters("customer_category_vendor", normalized)
    cached = _cache_get(_customer_category_vendor_cache, cache_key)
    if cached is not None:
        frame, meta = cached
        return frame.copy(deep=False), dict(meta)

    empty = pd.DataFrame(
        columns=[
            "Gamintojas (pavad)",
            "last_value",
            "previous_value",
            "avg_3m",
            "avg_6m",
        ]
    )

    if not category_group or not category_name:
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    tx = fetch_customer_transactions(filters)
    if tx.empty:
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    mapping = _load_category_mapping()
    tx = tx.merge(mapping, how="left", on="Kategorija")
    tx["Kategorijos_grupe"] = tx["Kategorijos_grupe"].fillna("Nepriskirta")

    tx = tx[(tx["Kategorijos_grupe"] == category_group) & (tx["Kategorija"] == category_name)]
    if tx.empty:
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    tx["Gamintojas (pavad)"] = tx["Gamintojas (pavad)"].fillna("Nežinomas gamintojas")
    tx["Menuo"] = tx["Menuo"].astype(str)
    tx["Mėnuo"] = tx["Menuo"].map(MONTH_ORDER)
    tx = tx.dropna(subset=["Mėnuo"])
    if tx.empty:
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    tx["Mėnuo"] = tx["Mėnuo"].astype(int)
    tx["YearMonth"] = tx["Metai"] * 100 + tx["Mėnuo"]

    last_idx = tx["YearMonth"].max()
    if pd.isna(last_idx):
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    last_year = int(last_idx // 100)
    last_month = int(last_idx % 100)
    prev_year, prev_month = _previous_month(last_year, last_month)

    available_periods = set(
        (int(row.Metai), int(row.Mėnuo))
        for row in tx[["Metai", "Mėnuo"]].drop_duplicates().itertuples(index=False)
    )
    prev_period = (prev_year, prev_month) if (prev_year, prev_month) in available_periods else None

    def periods_window(length: int) -> List[Tuple[int, int]]:
        periods: List[Tuple[int, int]] = []
        year, month = last_year, last_month
        for _ in range(length):
            periods.append((year, month))
            year, month = _previous_month(year, month)
        return periods

    window3 = [p for p in periods_window(3) if p in available_periods]
    window6 = [p for p in periods_window(6) if p in available_periods]

    grouped = (
        tx.groupby(["Gamintojas (pavad)", "Metai", "Mėnuo"], as_index=False)[
            ["Apyvarta", "Pajamos", "Kiekis"]
        ]
        .sum()
    )

    vendor_records: Dict[str, Dict[Tuple[int, int], Dict[str, float]]] = {}
    for vendor, year, month, apyvarta, pajamos, kiekis in grouped.itertuples(
        index=False, name=None
    ):
        vendor_records.setdefault(vendor, {})[(int(year), int(month))] = {
            "Apyvarta": float(apyvarta),
            "Pajamos": float(pajamos),
            "Kiekis": float(kiekis),
        }

    rows: List[Dict[str, Any]] = []
    for vendor, values in vendor_records.items():
        last_entries = [values[p] for p in [(last_year, last_month)] if p in values]
        prev_entries = [values[p] for p in [prev_period] if p and p in values]
        win3_entries = [values[p] for p in window3 if p in values]
        win6_entries = [values[p] for p in window6 if p in values]

        rows.append(
            {
                "Gamintojas (pavad)": vendor,
                "last_value": _metric_sum_for_entries(metric, last_entries, average=False),
                "previous_value": _metric_sum_for_entries(metric, prev_entries, average=False),
                "avg_3m": _metric_sum_for_entries(metric, win3_entries, average=True),
                "avg_6m": _metric_sum_for_entries(metric, win6_entries, average=True),
            }
        )

    if not rows:
        _cache_set(_customer_category_vendor_cache, cache_key, (empty, {}))
        return empty, {}

    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(
            by="last_value",
            ascending=False,
            inplace=True,
            kind="mergesort",
        )

    metadata = {
        "last_period": (last_year, last_month),
        "previous_period": prev_period,
        "window3_periods": [
            (int(period[0]), int(period[1])) for period in window3
        ],
        "window6_periods": [
            (int(period[0]), int(period[1])) for period in window6
        ],
    }

    _cache_set(_customer_category_vendor_cache, cache_key, (result.copy(deep=False), metadata))
    return result.copy(deep=False), metadata


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


# ==================== Common filtering helper ====================
def filter_dataframe(
    df: pd.DataFrame,
    segments: Optional[List[str]] = None,
    filialai: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    months: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Apply common dashboard filters to a dataframe."""

    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    if segments:
        mask &= df["Segmentas"].isin(segments)

    if filialai:
        mask &= df["Filialas"].isin(filialai)

    if years:
        mask &= df["Metai"].isin(years)

    if months:
        mask &= df["Menuo"].astype(str).isin(months)

    return df[mask]


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
