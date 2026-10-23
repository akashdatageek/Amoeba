-- psql variables: \set tid 1   (RLS: SET app.tenant_id = '1' first). Window = 2026-01-01..2026-03-31
-- Q1 daily active users
SELECT ts::date AS day, count(DISTINCT user_id) AS dau FROM events
WHERE tenant_id = :tid GROUP BY 1 ORDER BY 1;
-- Q2 top event types, last 30 days of data
SELECT type, count(*) AS n FROM events
WHERE tenant_id = :tid AND ts >= '2026-03-02' AND ts < '2026-04-01' GROUP BY type ORDER BY n DESC, type;
-- Q3 funnel page_view -> signup -> purchase (ordered, per user)
WITH f AS (SELECT user_id,
  min(ts) FILTER (WHERE type='page_view') v, min(ts) FILTER (WHERE type='signup') s, min(ts) FILTER (WHERE type='purchase') p
  FROM events WHERE tenant_id = :tid GROUP BY user_id)
SELECT count(*) FILTER (WHERE v IS NOT NULL) AS step1_view,
       count(*) FILTER (WHERE v IS NOT NULL AND s >= v) AS step2_signup,
       count(*) FILTER (WHERE v IS NOT NULL AND s >= v AND p >= s) AS step3_purchase FROM f;
-- Q4 rolling 7-day event count
SELECT day, sum(c) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7d
FROM (SELECT ts::date AS day, count(*) AS c FROM events WHERE tenant_id = :tid GROUP BY 1) d ORDER BY day;
-- Q5 latest 100 events
SELECT event_id, ts, type, user_id FROM events WHERE tenant_id = :tid ORDER BY ts DESC, event_id DESC LIMIT 100;
-- Q6 cross-tenant leak check (run as app_user with app.tenant_id set; expected distinct tenants = 1, foreign rows = 0)
SELECT count(DISTINCT tenant_id) AS tenants_visible, count(*) FILTER (WHERE tenant_id <> :tid) AS foreign_rows FROM events;
