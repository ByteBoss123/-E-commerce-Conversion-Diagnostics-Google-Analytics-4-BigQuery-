-- Raw-event diagnostics across the entire selected extraction window.
WITH base AS (
 SELECT event_date,event_name,event_timestamp,user_pseudo_id,
 (SELECT ANY_VALUE(value.int_value) FROM UNNEST(event_params) WHERE key='ga_session_id') AS session_id,
 ecommerce.transaction_id AS transaction_id,ecommerce.purchase_revenue_in_usd AS revenue
 FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
 WHERE _TABLE_SUFFIX BETWEEN @start_date AND @end_date
), duplicates AS (
 SELECT COALESCE(SUM(n-1),0) AS duplicate_transaction_events FROM (
 SELECT transaction_id,COUNT(*) AS n FROM base WHERE event_name='purchase'
 AND transaction_id IS NOT NULL AND transaction_id NOT IN ('','(not set)','<Other>')
 GROUP BY transaction_id HAVING COUNT(*)>1
 ))
SELECT COUNT(*) AS raw_events,COUNT(DISTINCT event_date) AS observed_days,
 COUNTIF(user_pseudo_id IS NULL OR user_pseudo_id='' OR session_id IS NULL) AS excluded_identity_events,
 COUNTIF(event_name='purchase') AS purchase_events,
 COUNTIF(event_name='purchase' AND (transaction_id IS NULL OR transaction_id IN ('','(not set)','<Other>'))) AS missing_transaction_events,
 COUNTIF(event_name='purchase' AND revenue IS NULL) AS missing_revenue_events,
 COUNTIF(event_name='purchase' AND revenue<0) AS negative_revenue_events,
 (SELECT duplicate_transaction_events FROM duplicates) AS duplicate_transaction_events
FROM base
