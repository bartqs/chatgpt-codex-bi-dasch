-- Performance support for the Dash BI app against the MySQL `sales` table.
-- Run these manually during a maintenance window after checking existing indexes.
-- The statements are intentionally separate so you can skip indexes that already exist.

-- 1) Inspect current indexes first.
SHOW INDEX FROM sales;

-- 2) Recommended indexes for filters used by both dashboard pages.
-- Year/month are present in every report query; Filialas is a common branch filter.
CREATE INDEX idx_sales_year_month_filialas
    ON sales (`Year [Name] PE-Y01`, `Month [Short name] PE-M02`, `Filialas`);

-- Segment is used by the overview page and advisor filters.
CREATE INDEX idx_sales_segment_year_month
    ON sales (`Segmentas`, `Year [Name] PE-Y01`, `Month [Short name] PE-M02`);

-- Seller-specific advisor report and seller time-series queries filter on Pardavėjas.
CREATE INDEX idx_sales_seller_year_month_filialas
    ON sales (`Pardavėjas`, `Year [Name] PE-Y01`, `Month [Short name] PE-M02`, `Filialas`);

-- Manufacturer aggregation groups by manufacturer after applying filters.
-- Use this if your table has column `Gamintojas (pavad)`.
CREATE INDEX idx_sales_mfr_year_month_filialas
    ON sales (`Gamintojas (pavad)`, `Year [Name] PE-Y01`, `Month [Short name] PE-M02`, `Filialas`);

-- Category filtering. Use this if your table has column `Kategorija (pavad)`.
CREATE INDEX idx_sales_cat_year_month_filialas
    ON sales (`Kategorija (pavad)`, `Year [Name] PE-Y01`, `Month [Short name] PE-M02`, `Filialas`);

-- If your schema uses alternate names instead of the columns above, create the equivalent
-- indexes for the actual column chosen by data/app_data.py advisor_columns():
--   Manufacturer candidates: `Gamintojas (pavad)`, `Gamintojas`, `Gamintojas [Name]`, `Manufacturer`
--   Category candidates:     `Kategorija (pavad)`, `Kategorija`, `Kategorija [Name]`, `Category`
--   Segment candidates:      `Kliento Segmentas`, `Segmentas`, `Segmentas.1`

-- 3) Diagnostics for the optimized advisor table query.
-- Replace bind values with the filters you select in the UI.
EXPLAIN
SELECT
    COALESCE(`Gamintojas (pavad)`, 'Nepriskirta') AS Gamintojas,
    SUM(CAST(`APYVARTA` AS DECIMAL(18,2))) AS Apyvarta,
    SUM(CAST(`PAJAMOS` AS DECIMAL(18,2))) AS Pajamos,
    SUM(CAST(`KIEKIS` AS DECIMAL(18,2))) AS Kiekis
FROM sales
WHERE `Year [Name] PE-Y01` IS NOT NULL
  AND `Month [Short name] PE-M02` IS NOT NULL
  AND `Filialas` IN ('L51', 'L52')
  AND CAST(`Year [Name] PE-Y01` AS UNSIGNED) IN (2025)
GROUP BY COALESCE(`Gamintojas (pavad)`, 'Nepriskirta')
ORDER BY Apyvarta DESC;

-- MySQL 8.0.18+ only: use EXPLAIN ANALYZE to see actual execution timing/rows.
EXPLAIN ANALYZE
SELECT
    COALESCE(`Gamintojas (pavad)`, 'Nepriskirta') AS Gamintojas,
    SUM(CAST(`APYVARTA` AS DECIMAL(18,2))) AS Apyvarta,
    SUM(CAST(`PAJAMOS` AS DECIMAL(18,2))) AS Pajamos,
    SUM(CAST(`KIEKIS` AS DECIMAL(18,2))) AS Kiekis
FROM sales
WHERE `Year [Name] PE-Y01` IS NOT NULL
  AND `Month [Short name] PE-M02` IS NOT NULL
  AND `Filialas` IN ('L51', 'L52')
  AND CAST(`Year [Name] PE-Y01` AS UNSIGNED) IN (2025)
GROUP BY COALESCE(`Gamintojas (pavad)`, 'Nepriskirta')
ORDER BY Apyvarta DESC;

-- 4) Diagnostics for the selected-seller time-series query.
EXPLAIN
SELECT
    CAST(`Year [Name] PE-Y01` AS UNSIGNED) AS Metai,
    `Month [Short name] PE-M02` AS Menuo,
    SUM(CAST(`APYVARTA` AS DECIMAL(18,2))) AS Apyvarta,
    SUM(CAST(`PAJAMOS` AS DECIMAL(18,2))) AS Pajamos,
    SUM(CAST(`KIEKIS` AS DECIMAL(18,2))) AS Kiekis
FROM sales
WHERE `Year [Name] PE-Y01` IS NOT NULL
  AND `Month [Short name] PE-M02` IS NOT NULL
  AND `Filialas` IN ('L51', 'L52')
  AND CAST(`Year [Name] PE-Y01` AS UNSIGNED) IN (2025)
  AND TRIM(COALESCE(`Pardavėjas`, '')) = 'REPLACE_WITH_SELLER_NAME'
GROUP BY CAST(`Year [Name] PE-Y01` AS UNSIGNED), `Month [Short name] PE-M02`
ORDER BY Metai, Menuo;
