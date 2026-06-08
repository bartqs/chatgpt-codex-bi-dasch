"""
Shared application data, constants, and business logic extracted from the
original single-file Dash notebook implementation.

This module preserves the exact behavior, calculations, and styling helpers
used across the dashboard pages.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dash import html
from plotly import graph_objects as go
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.sql.elements import TextClause


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
ADVISOR_TABLE_COLS = ["Gamintojas", "Apyvarta", "Pajamos", "Marža %", "Kiekis"]


# ==================== Lightweight performance diagnostics ====================
logging.basicConfig(level=os.getenv("APP_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("ic_dashboard.performance")


@contextmanager
def perf_timer(label: str, **details: Any):
    """Log elapsed time for callbacks, SQL calls, and DataFrame transformations."""
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        extra = " ".join(f"{key}={value}" for key, value in details.items() if value is not None)
        logger.info("%s duration_ms=%.1f %s", label, elapsed_ms, extra)


def _log_df(label: str, df: pd.DataFrame) -> None:
    logger.info("%s rows=%s columns=%s", label, len(df), list(df.columns))


# ==================== DB Connection with Proper Pooling ====================
password = os.getenv("DB_PASSWORD", "pass123")  # Use env var, fallback for dev. Do not log this value.
engine = create_engine(
    f"mysql+pymysql://root:{password}@localhost:3306/ic?charset=utf8mb4",
    connect_args={"charset": "utf8mb4"},
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    pool_timeout=30,
    future=True,
)


def _read_sql_timed(label: str, sql: TextClause, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Run a SQL query with timing and returned-row diagnostics."""
    with engine.connect() as conn:
        with perf_timer(f"sql.{label}"):
            df = pd.read_sql(sql, conn, params=params or {})
    _log_df(f"sql.{label}.result", df)
    return df


# ==================== Data Loading Functions ====================
def load_summary_data() -> pd.DataFrame:
    """Load pre-aggregated summary data with efficient memory usage."""
    df = _read_sql_timed(
        "load_summary_data",
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
    )

    with perf_timer("transform.load_summary_data", rows=len(df)):
        df = df.astype({"Metai": "int16", "Filialas": "category", "Segmentas": "category"})
        df["Menuo"] = pd.Categorical(df["Menuo"].astype(str), categories=MENUO_TVARKA, ordered=True)

        for c in ["APYVARTA", "PAJAMOS", "KIEKIS"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")

        df["MARŽA %"] = np.where(
            df["APYVARTA"] != 0,
            (df["PAJAMOS"] / df["APYVARTA"]) * 100.0,
            np.nan,
        ).astype("float32")

    return df


def get_columns() -> List[str]:
    """Get column names from sales table."""
    return _read_sql_timed("get_columns", text("SHOW COLUMNS FROM sales"))["Field"].tolist()


def pick_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    """Pick first matching column from candidates and return a quoted SQL identifier."""
    for c in candidates:
        if c in cols:
            return f"`{c}`"
    return None


_ADVISOR_COLS: Optional[Dict[str, str]] = None


def advisor_columns() -> Dict[str, str]:
    """Resolve optional advisor dimensions once so callbacks can build targeted SQL."""
    global _ADVISOR_COLS
    if _ADVISOR_COLS is None:
        cols_all = get_columns()
        mfr_sql = pick_col(cols_all, ["Gamintojas (pavad)", "Gamintojas", "Gamintojas [Name]", "Manufacturer"])
        cat_sql = pick_col(cols_all, ["Kategorija (pavad)", "Kategorija", "Kategorija [Name]", "Category"])
        seg_sql = pick_col(cols_all, ["Kliento Segmentas", "Segmentas", "Segmentas.1"]) or "`Segmentas`"
        _ADVISOR_COLS = {
            "segment": seg_sql,
            "category": cat_sql or "NULL",
            "manufacturer": mfr_sql or "NULL",
        }
        logger.info("advisor_columns resolved segment=%s category=%s manufacturer=%s", seg_sql, cat_sql, mfr_sql)
    return _ADVISOR_COLS


def _advisor_filter_sql(
    filialai: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    months: Optional[List[str]] = None,
    segmentas: Optional[str] = None,
    kategorija: Optional[str] = None,
    pardavejas_display: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], List[str]]:
    """Build parameterized WHERE predicates for advisor report queries."""
    cols = advisor_columns()
    conditions = ["`Year [Name] PE-Y01` IS NOT NULL", "`Month [Short name] PE-M02` IS NOT NULL"]
    params: Dict[str, Any] = {}
    expanding: List[str] = []

    if filialai:
        conditions.append("`Filialas` IN :filialai")
        params["filialai"] = list(filialai)
        expanding.append("filialai")
    if years:
        conditions.append("CAST(`Year [Name] PE-Y01` AS UNSIGNED) IN :years")
        params["years"] = [int(y) for y in years]
        expanding.append("years")
    if months:
        conditions.append("`Month [Short name] PE-M02` IN :months")
        params["months"] = list(months)
        expanding.append("months")
    if segmentas and segmentas != "Visi":
        conditions.append(f"COALESCE({cols['segment']}, 'Nepriskirta') = :segmentas")
        params["segmentas"] = segmentas
    if kategorija and kategorija != "Visos":
        conditions.append(f"COALESCE({cols['category']}, 'Nepriskirta') = :kategorija")
        params["kategorija"] = kategorija
    if pardavejas_display:
        internal = "(ND)" if pardavejas_display == "E-commerce" else pardavejas_display
        conditions.append("TRIM(COALESCE(`Pardavėjas`, '')) = :pardavejas")
        params["pardavejas"] = internal

    return " AND ".join(conditions), params, expanding


def _bind_expanding(sql: TextClause, expanding: List[str]) -> TextClause:
    for name in expanding:
        sql = sql.bindparams(bindparam(name, expanding=True))
    return sql


def load_advisor_filter_options() -> Tuple[List[int], List[str], List[str], List[str], List[str]]:
    """Load only DISTINCT advisor filter values instead of the full sales table."""
    cols = advisor_columns()
    base_where = "`Year [Name] PE-Y01` IS NOT NULL AND `Month [Short name] PE-M02` IS NOT NULL"

    years_df = _read_sql_timed(
        "load_advisor_filter_options.years",
        text(
            f"""
            SELECT DISTINCT CAST(`Year [Name] PE-Y01` AS UNSIGNED) AS value
            FROM sales
            WHERE {base_where}
            ORDER BY value
            """
        ),
    )
    filialai_df = _read_sql_timed(
        "load_advisor_filter_options.filialai",
        text(
            f"""
            SELECT DISTINCT `Filialas` AS value
            FROM sales
            WHERE {base_where} AND `Filialas` IS NOT NULL
            ORDER BY value
            """
        ),
    )
    segmentai_df = _read_sql_timed(
        "load_advisor_filter_options.segmentai",
        text(
            f"""
            SELECT DISTINCT COALESCE({cols['segment']}, 'Nepriskirta') AS value
            FROM sales
            WHERE {base_where}
            ORDER BY value
            """
        ),
    )
    kategorijos_df = _read_sql_timed(
        "load_advisor_filter_options.kategorijos",
        text(
            f"""
            SELECT DISTINCT COALESCE({cols['category']}, 'Nepriskirta') AS value
            FROM sales
            WHERE {base_where}
            ORDER BY value
            """
        ),
    )
    sellers_df = _read_sql_timed(
        "load_advisor_filter_options.sellers",
        text(
            f"""
            SELECT DISTINCT COALESCE(NULLIF(TRIM(`Pardavėjas`), ''), 'Nežinoma') AS value
            FROM sales
            WHERE {base_where}
            ORDER BY value
            """
        ),
    )

    with perf_timer(
        "transform.load_advisor_filter_options",
        years=len(years_df),
        filialai=len(filialai_df),
        segmentai=len(segmentai_df),
        kategorijos=len(kategorijos_df),
        sellers=len(sellers_df),
    ):
        years = years_df["value"].dropna().astype(int).tolist()
        filialai = filialai_df["value"].dropna().astype(str).tolist()
        segmentai = segmentai_df["value"].dropna().astype(str).tolist()
        kategorijos = kategorijos_df["value"].dropna().astype(str).tolist()
        sellers = sellers_df["value"].replace({"(ND)": "E-commerce"}).dropna().astype(str).sort_values().unique().tolist()
    return years, filialai, segmentai, kategorijos, sellers

def query_advisor_seller_options(
    filialai: Optional[List[str]],
    years: Optional[List[int]],
    months: Optional[List[str]],
    segmentas: str,
    kategorija: str,
) -> List[str]:
    """Return sellers matching current filters using SELECT DISTINCT in MySQL."""
    where_sql, params, expanding = _advisor_filter_sql(filialai, years, months, segmentas, kategorija)
    sql = _bind_expanding(
        text(
            f"""
            SELECT DISTINCT
                COALESCE(NULLIF(TRIM(`Pardavėjas`), ''), 'Nežinoma') AS Pardavejas_display
            FROM sales
            WHERE {where_sql}
            ORDER BY Pardavejas_display
            """
        ),
        expanding,
    )
    df = _read_sql_timed("advisor_seller_options", sql, params)
    return df["Pardavejas_display"].replace({"(ND)": "E-commerce"}).dropna().astype(str).sort_values().unique().tolist()


def query_advisor_vendor_aggregate(
    filialai: Optional[List[str]],
    years: Optional[List[int]],
    months: Optional[List[str]],
    segmentas: str = "Visi",
    kategorija: str = "Visos",
    pardavejas_display: Optional[str] = None,
) -> pd.DataFrame:
    """Aggregate manufacturer results in MySQL for the selected advisor filters."""
    cols = advisor_columns()
    where_sql, params, expanding = _advisor_filter_sql(filialai, years, months, segmentas, kategorija, pardavejas_display)
    sql = _bind_expanding(
        text(
            f"""
            SELECT
                COALESCE({cols['manufacturer']}, 'Nepriskirta') AS Gamintojas,
                SUM(CAST(`APYVARTA` AS DECIMAL(18,2))) AS Apyvarta,
                SUM(CAST(`PAJAMOS` AS DECIMAL(18,2))) AS Pajamos,
                SUM(CAST(`KIEKIS` AS DECIMAL(18,2))) AS Kiekis
            FROM sales
            WHERE {where_sql}
            GROUP BY COALESCE({cols['manufacturer']}, 'Nepriskirta')
            ORDER BY Apyvarta DESC
            """
        ),
        expanding,
    )
    df = _read_sql_timed("advisor_vendor_aggregate", sql, params)
    with perf_timer("transform.advisor_vendor_aggregate", rows=len(df)):
        for c in ["Apyvarta", "Pajamos", "Kiekis"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
    return df


def query_advisor_vendor_timeseries(
    filialai: Optional[List[str]],
    years: Optional[List[int]],
    months: Optional[List[str]],
    segmentas: str,
    kategorija: str,
    pardavejas_display: str,
) -> pd.DataFrame:
    """Return seller monthly aggregates; charting remains in Dash/Plotly unchanged."""
    where_sql, params, expanding = _advisor_filter_sql(filialai, years, months, segmentas, kategorija, pardavejas_display)
    sql = _bind_expanding(
        text(
            f"""
            SELECT
                CAST(`Year [Name] PE-Y01` AS UNSIGNED) AS Metai,
                `Month [Short name] PE-M02` AS Menuo,
                SUM(CAST(`APYVARTA` AS DECIMAL(18,2))) AS Apyvarta,
                SUM(CAST(`PAJAMOS` AS DECIMAL(18,2))) AS Pajamos,
                SUM(CAST(`KIEKIS` AS DECIMAL(18,2))) AS Kiekis
            FROM sales
            WHERE {where_sql}
            GROUP BY CAST(`Year [Name] PE-Y01` AS UNSIGNED), `Month [Short name] PE-M02`
            ORDER BY Metai, Menuo
            """
        ),
        expanding,
    )
    df = _read_sql_timed("advisor_vendor_timeseries", sql, params)
    with perf_timer("transform.advisor_vendor_timeseries", rows=len(df)):
        for c in ["Apyvarta", "Pajamos", "Kiekis"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
        df["Menuo"] = df["Menuo"].astype(str)
    return df


# Backward-compatible raw loader kept for ad-hoc debugging only. It is no longer
# called at startup or from callbacks because it materializes the full sales table.
def load_advisor_data() -> pd.DataFrame:
    """Load raw advisor rows. Avoid in callbacks; use SQL aggregate query helpers instead."""
    cols = advisor_columns()
    df = _read_sql_timed(
        "load_advisor_data_full_table",
        text(
            f"""
            SELECT
                CAST(`Year [Name] PE-Y01` AS UNSIGNED) AS Metai,
                `Month [Short name] PE-M02` AS Menuo,
                `Filialas`,
                COALESCE({cols['segment']}, 'Nepriskirta') AS Segmentas,
                COALESCE({cols['category']}, 'Nepriskirta') AS Kategorija,
                COALESCE({cols['manufacturer']}, 'Nepriskirta') AS Gamintojas,
                `Pardavėjas` AS Pardavejas,
                CAST(`APYVARTA` AS DECIMAL(18,2)) AS Apyvarta,
                CAST(`PAJAMOS` AS DECIMAL(18,2)) AS Pajamos,
                CAST(`KIEKIS` AS DECIMAL(18,2)) AS Kiekis
            FROM sales
            WHERE `Year [Name] PE-Y01` IS NOT NULL
              AND `Month [Short name] PE-M02` IS NOT NULL
            """
        ),
    )
    with perf_timer("transform.load_advisor_data_full_table", rows=len(df)):
        df["Menuo"] = pd.Categorical(df["Menuo"].astype(str), categories=MENUO_TVARKA, ordered=True)
        for c in ["Apyvarta", "Pajamos", "Kiekis"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float32")
        df["Marza_pct"] = np.where(df["Apyvarta"] != 0, (df["Pajamos"] / df["Apyvarta"]) * 100.0, np.nan).astype("float32")
        df["Pardavejas_display"] = df["Pardavejas"].replace({"(ND)": "E-commerce"}).fillna("Nežinoma")
        for col in ["Filialas", "Segmentas", "Kategorija", "Gamintojas"]:
            df[col] = df[col].fillna("Nežinoma")
    return df


# Load small startup datasets only. Summary is pre-aggregated; advisor uses DISTINCT values.
df_sums = load_summary_data()

SEGMENT_OPTIONS = sorted([s for s in df_sums["Segmentas"].cat.categories if s is not None])
FILIALAS_OPTIONS = sorted([f for f in df_sums["Filialas"].cat.categories if f is not None])
YEAR_OPTIONS = sorted(df_sums["Metai"].unique().tolist())

YEARS_ADV, FILIALAI_ADV, SEGMENTAI_ADV, KATEGORIJOS, PARDAVEJAI_ADV = load_advisor_filter_options()


# ==================== Efficient DataFrame Filtering ====================
def filter_dataframe(
    df: pd.DataFrame,
    segments: Optional[List[str]] = None,
    filialai: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    months: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Single-pass efficient DataFrame filtering for already-aggregated in-memory data."""
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


# ==================== Helper Functions ====================
def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data by month."""
    if df.empty:
        return pd.DataFrame(columns=["Filialas", "Metai", "Menuo", "APYVARTA", "PAJAMOS", "KIEKIS", "MARŽA %"])

    g = df.groupby(["Filialas", "Metai", "Menuo"], as_index=False)[["APYVARTA", "PAJAMOS", "KIEKIS"]].sum()
    g["MARŽA %"] = np.where(g["APYVARTA"] != 0, (g["PAJAMOS"] / g["APYVARTA"]) * 100.0, np.nan).astype("float32")
    return g


def active_months_for_latest_year(g: pd.DataFrame, years_sel: List[int], branch: Optional[str], months_sel: Optional[List[str]]) -> List[str]:
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
def format_vendor_aggregate(dd: pd.DataFrame) -> pd.DataFrame:
    """Format SQL-aggregated manufacturer data for the existing Dash table."""
    cols = ADVISOR_TABLE_COLS
    if dd.empty:
        return pd.DataFrame(columns=cols)

    out = dd.copy()
    for c in ["Apyvarta", "Pajamos", "Kiekis"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out["Marža %"] = np.where(out["Apyvarta"] != 0, (out["Pajamos"] / out["Apyvarta"]) * 100.0, np.nan)
    out = out.sort_values("Apyvarta", ascending=False, kind="mergesort")

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

    out["Apyvarta"] = out["Apyvarta"].map(_fmt_eur)
    out["Pajamos"] = out["Pajamos"].map(_fmt_eur)
    out["Marža %"] = out["Marža %"].map(lambda v: "-" if pd.isna(v) else f"{round(float(v), 1)} %")
    out["Kiekis"] = out["Kiekis"].map(_fmt_qty)
    return out[cols]


def aggregate_by_vendor(dd: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data by vendor/manufacturer for already-loaded DataFrames."""
    cols = ADVISOR_TABLE_COLS
    if dd.empty:
        return pd.DataFrame(columns=cols)
    g = dd.groupby("Gamintojas", as_index=False)[["Apyvarta", "Pajamos", "Kiekis"]].sum()
    return format_vendor_aggregate(g)


class SummaryCalculator:
    """Encapsulate summary tab business logic."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.monthly_agg = aggregate_monthly(df)

    def create_branch_figure(self, branch: str, metric: str, chart_type: str, years_sel: List[int], months_sel: Optional[List[str]]) -> go.Figure:
        """Create figure for a specific branch."""
        b = self.monthly_agg[self.monthly_agg["Filialas"] == branch]
        fig = go.Figure()

        if b.empty:
            fig.update_layout(
                title=f"{branch} – {metric}: duomenų nėra",
                height=360,
                annotations=[{"text": "Nėra duomenų su pasirinktais filtrais", "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5, "showarrow": False, "font": {"size": 14, "color": IC_GRAY}}],
            )
            return fig

        months_axis = [m for m in MENUO_TVARKA if (not months_sel) or (m in months_sel)]
        p = b.pivot_table(index="Menuo", columns="Metai", values=metric, aggfunc="first").reindex(months_axis)
        latest_year = int(sorted(years_sel)[-1])
        b_latest = b[b["Metai"] == latest_year]
        active_latest = set(b_latest.loc[(b_latest[["APYVARTA", "PAJAMOS", "KIEKIS"]].fillna(0).sum(axis=1) > 0), "Menuo"].astype(str).tolist())

        for y in years_sel:
            if y not in p.columns:
                continue
            color = COLORWAY_YEARS.get(int(y), IC_BLACK)
            yvals = p[y].copy()
            if int(y) == latest_year:
                mask = [m not in active_latest for m in months_axis]
                yvals.loc[mask] = np.nan
            if chart_type == "line":
                fig.add_trace(go.Scatter(x=months_axis, y=yvals, mode="lines+markers", name=str(y), line=dict(color=color)))
            else:
                fig.add_trace(go.Bar(x=months_axis, y=yvals, name=str(y), marker=dict(color=color)))

        fig.update_layout(
            height=360,
            margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            paper_bgcolor=IC_WHITE,
            plot_bgcolor=IC_WHITE,
            hovermode="x unified",
        )
        return fig

    def build_monthly_table(self, years_sel: List[int], months_sel: Optional[List[str]], metric: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Build monthly summary table data."""
        months_axis_table = active_months_for_latest_year(self.monthly_agg, years_sel, None, months_sel)

        if metric == "MARŽA %":
            use = self.monthly_agg[["Filialas", "Metai", "Menuo", "PAJAMOS", "APYVARTA"]].copy()
            use["value"] = np.where(use["APYVARTA"] != 0, (use["PAJAMOS"] / use["APYVARTA"]) * 100.0, np.nan)
            totals = self.monthly_agg.groupby(["Filialas", "Metai"], as_index=False)[["PAJAMOS", "APYVARTA"]].sum().assign(
                Bendra=lambda d: np.where(d["APYVARTA"] != 0, (d["PAJAMOS"] / d["APYVARTA"]) * 100.0, np.nan)
            )
        else:
            use = self.monthly_agg[["Filialas", "Metai", "Menuo", metric]].rename(columns={metric: "value"})
            totals = self.monthly_agg.groupby(["Filialas", "Metai"], as_index=False)[metric].sum().rename(columns={metric: "Bendra"})

        p = use.pivot_table(index=["Filialas", "Metai"], columns="Menuo", values="value", aggfunc="first").reindex(columns=months_axis_table)
        tdf = p.reset_index().merge(totals[["Filialas", "Metai", "Bendra"]], on=["Filialas", "Metai"], how="left")
        columns = [{"name": c, "id": c} for c in tdf.columns]

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

    def calculate_kpis(self, this_year: int, prev_year: Optional[int], metric: str, months_sel: Optional[List[str]]) -> List[html.Div]:
        """Calculate KPI cards with YoY comparison."""

        def sum_metric_block(dd: pd.DataFrame) -> Tuple[float, float]:
            cur = dd[dd["Metai"] == this_year].copy()
            active_cur = set(cur.loc[(cur[["APYVARTA", "PAJAMOS", "KIEKIS"]].fillna(0).sum(axis=1) > 0), "Menuo"].astype(str).tolist())
            if months_sel:
                active_cur = {m for m in active_cur if m in months_sel}
            if not active_cur:
                return (np.nan, np.nan)

            def agg(df: pd.DataFrame) -> float:
                if metric == "MARŽA %":
                    ap = df["APYVARTA"].sum()
                    pj = df["PAJAMOS"].sum()
                    return (pj / ap) * 100.0 if ap else np.nan
                return df[metric].sum()

            this_sum = agg(cur[cur["Menuo"].astype(str).isin(active_cur)])
            if prev_year is None:
                prev_sum = np.nan
            else:
                prev = dd[dd["Metai"] == prev_year]
                prev_sum = agg(prev[prev["Menuo"].astype(str).isin(active_cur)])
            return (this_sum, prev_sum)

        def yoy_text_color(this_val: float, prev_val: float) -> Tuple[str, str]:
            if pd.isna(prev_val) or float(prev_val) == 0 or pd.isna(this_val):
                return "–", IC_GRAY
            yoy = (float(this_val) / float(prev_val) - 1.0) * 100.0
            return _fmt_signed_pct(yoy), GREEN if yoy >= 0 else RED

        def fmt_main(v: float) -> str:
            if metric in ["APYVARTA", "PAJAMOS"]:
                return _fmt_eur(v)
            if metric == "MARŽA %":
                return _fmt_pct(v)
            return _fmt_qty(v)

        def card(lbl: str, v: float, yoy_text: str, yoy_color: str) -> html.Div:
            return html.Div(
                [
                    html.Div(lbl, style={"fontSize": "12px", "color": IC_NAVY, "fontWeight": 700}),
                    html.Div(fmt_main(v), style={"fontSize": "22px", "fontWeight": 700, "color": IC_BLACK}),
                    html.Div(f"YoY: {yoy_text}", style={"fontSize": "12px", "marginTop": "2px", "color": yoy_color}),
                ],
                style={"background": IC_WHITE, "border": f"1px solid {IC_GRAY}", "borderRadius": "10px", "padding": "10px 12px"},
            )

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
    "ADVISOR_TABLE_COLS",
    "df_sums",
    "SEGMENT_OPTIONS",
    "FILIALAS_OPTIONS",
    "YEAR_OPTIONS",
    "YEARS_ADV",
    "FILIALAI_ADV",
    "SEGMENTAI_ADV",
    "KATEGORIJOS",
    "PARDAVEJAI_ADV",
    "perf_timer",
    "filter_dataframe",
    "aggregate_by_vendor",
    "format_vendor_aggregate",
    "query_advisor_seller_options",
    "query_advisor_vendor_aggregate",
    "query_advisor_vendor_timeseries",
    "SummaryCalculator",
]
