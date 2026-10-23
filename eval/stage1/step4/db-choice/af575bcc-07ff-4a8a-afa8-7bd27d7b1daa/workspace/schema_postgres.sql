-- PostgreSQL 16+ schema (vanilla; works on RDS/Aurora/Cloud SQL/AlloyDB). NOT EXECUTED in this sandbox (no server binaries).
CREATE TABLE events (
  event_id    bigint       NOT NULL,
  tenant_id   int          NOT NULL,
  occurred_at timestamptz  NOT NULL,
  event_type  text         NOT NULL,
  user_id     text         NOT NULL,
  session_id  text         NOT NULL,
  properties  jsonb        NOT NULL,
  amount      numeric(14,2),
  PRIMARY KEY (tenant_id, occurred_at, event_id)   -- PK must contain the partition key
) PARTITION BY RANGE (occurred_at);
CREATE TABLE events_2026_07 PARTITION OF events FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE events_2026_08 PARTITION OF events FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE events_2026_09 PARTITION OF events FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE events_2026_10 PARTITION OF events FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE events_default PARTITION OF events DEFAULT;
-- tenant-leading composite indexes (created on parent, cascade to partitions)
CREATE INDEX events_tenant_type_time ON events (tenant_id, event_type, occurred_at DESC);
CREATE INDEX events_tenant_user_time ON events (tenant_id, user_id, occurred_at);
CREATE INDEX events_time_brin ON events USING brin (occurred_at) WITH (pages_per_range=32);
CREATE INDEX events_props_gin ON events USING gin (properties jsonb_path_ops);

CREATE TABLE dashboards (
  dashboard_id text PRIMARY KEY,
  tenant_id    int  NOT NULL,
  name         text NOT NULL,
  owner        text NOT NULL,
  widgets      jsonb NOT NULL,   -- [{widget_id,type,query_def,layout}, ...]
  updated_at   timestamptz NOT NULL
);
CREATE INDEX dashboards_tenant ON dashboards (tenant_id, updated_at DESC);

-- Tenant isolation option: shared tables + row-level security keyed on a session GUC.
-- (Table owner/superuser bypasses RLS unless FORCE is set; the app must connect as a non-owner role.)
CREATE ROLE app_user NOLOGIN;
GRANT SELECT, INSERT, UPDATE ON events, dashboards TO app_user;
ALTER TABLE events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_iso ON events     USING (tenant_id = current_setting('app.tenant_id')::int);
CREATE POLICY tenant_iso ON dashboards USING (tenant_id = current_setting('app.tenant_id')::int);
-- usage: SET ROLE app_user; SET app.tenant_id = '7';
