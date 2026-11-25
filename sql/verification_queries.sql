-- ============================================================
-- QUERY 1: GOLDEN MASTER INTEGRITY
-- ============================================================
SELECT
    vendor_id,
    vendor_name,
    country,
    onboarded_date,
    lead_time_days,
    is_lead_time_imputed,
    contract_value_usd,
    source_system,
    last_modified
FROM gold_vendor_master
ORDER BY vendor_id;

-- ============================================================
-- QUERY 1B: TOTAL PORTFOLIO SPEND
-- ============================================================
SELECT COALESCE(SUM(contract_value_usd), 0) AS total_portfolio_spend
FROM gold_vendor_master;

-- ============================================================
-- QUERY 2: CATEGORY BREAKDOWN VIA RELATIONAL BRIDGE
-- ============================================================
SELECT
    c.material_category,
    COUNT(DISTINCT v.vendor_id) AS supplier_count,
    SUM(v.contract_value_usd) AS category_total_spend
FROM gold_vendor_categories c
JOIN gold_vendor_master v
    ON c.vendor_id = v.vendor_id
GROUP BY c.material_category
ORDER BY supplier_count DESC, category_total_spend DESC;

-- ============================================================
-- QUERY 3: QUARANTINE AUDIT REVIEW
-- ============================================================
SELECT
    vendor_id,
    vendor_name,
    source_system,
    rejection_reason
FROM err_vendor_quarantine
ORDER BY vendor_id;
