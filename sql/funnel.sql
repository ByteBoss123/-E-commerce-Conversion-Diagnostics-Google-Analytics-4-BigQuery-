-- Standard SQL. Session-bound, ordered funnel; tied timestamps do not establish order.
WITH base AS (
 SELECT event_date, event_timestamp, event_name, user_pseudo_id,
   (SELECT ANY_VALUE(value.int_value) FROM UNNEST(event_params) WHERE key='ga_session_id') AS session_id,
   COALESCE(NULLIF(device.category,''),'unknown') AS device,
   COALESCE(NULLIF(traffic_source.source,''),'unknown') AS acquisition_source
 FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
 WHERE _TABLE_SUFFIX BETWEEN @start_date AND @end_date
), sessions AS (
 SELECT user_pseudo_id, session_id,
   ARRAY_AGG(STRUCT(event_date,device,acquisition_source) ORDER BY event_timestamp,event_date,device,acquisition_source LIMIT 1)[OFFSET(0)] AS first_event,
   ARRAY_AGG(STRUCT(event_timestamp AS ts,event_name AS name)) AS events
 FROM base WHERE user_pseudo_id IS NOT NULL AND user_pseudo_id!='' AND session_id IS NOT NULL
 GROUP BY user_pseudo_id,session_id
), views AS (
 SELECT *, (SELECT MIN(ts) FROM UNNEST(events) WHERE name='view_item') AS v,
 (SELECT COUNTIF(name='purchase')>0 FROM UNNEST(events)) AS any_purchase FROM sessions
), carts AS (
 SELECT *, (SELECT MIN(ts) FROM UNNEST(events) WHERE name='add_to_cart' AND ts>v) AS c FROM views
), checkouts AS (
 SELECT *, (SELECT MIN(ts) FROM UNNEST(events) WHERE name='begin_checkout' AND ts>c) AS b FROM carts
), purchases AS (
 SELECT *, (SELECT MIN(ts) FROM UNNEST(events) WHERE name='purchase' AND ts>b) AS p FROM checkouts
)
SELECT PARSE_DATE('%Y%m%d',first_event.event_date) AS date,
 first_event.device AS device, first_event.acquisition_source AS acquisition_source,
 COUNT(*) AS sessions, COUNTIF(v IS NOT NULL) AS views,
 COUNTIF(c IS NOT NULL) AS carts, COUNTIF(b IS NOT NULL) AS checkouts,
 COUNTIF(p IS NOT NULL) AS purchases, COUNTIF(any_purchase) AS purchasing_sessions
FROM purchases GROUP BY 1,2,3 ORDER BY 1,2,3
