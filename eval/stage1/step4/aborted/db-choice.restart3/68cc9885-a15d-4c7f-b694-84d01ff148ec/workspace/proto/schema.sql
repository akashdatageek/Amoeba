-- PostgreSQL prototype schema: shared database, tenant_id column (assumption settled in task)
CREATE TABLE tenants (
  tenant_id   int PRIMARY KEY,
  name        text NOT NULL,
  region      text NOT NULL CHECK (region IN ('eu','non-eu')),  -- drives EU data-residency routing
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
  tenant_id   int         NOT NULL REFERENCES tenants(tenant_id),
  event_id    bigint      NOT NULL,
  ts          timestamptz NOT NULL,
  type        text        NOT NULL,
  user_id     bigint      NOT NULL,
  properties  jsonb       NOT NULL DEFAULT '{}',
  PRIMARY KEY (tenant_id, event_id, ts)          -- PK must include the partition key
) PARTITION BY RANGE (ts);

CREATE TABLE events_2026_01 PARTITION OF events FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE events_2026_02 PARTITION OF events FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE events_2026_03 PARTITION OF events FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE events_2026_04 PARTITION OF events FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE events_default PARTITION OF events DEFAULT;

CREATE INDEX events_tenant_ts_idx   ON events (tenant_id, ts DESC);
CREATE INDEX events_tenant_type_ts  ON events (tenant_id, type, ts);
CREATE INDEX events_props_gin       ON events USING gin (properties jsonb_path_ops);

CREATE TABLE dashboard_daily (
  tenant_id int  NOT NULL REFERENCES tenants(tenant_id),
  day       date NOT NULL,
  metric    text NOT NULL,       -- 'events', 'dau', 'purchases'
  value     double precision NOT NULL,
  PRIMARY KEY (tenant_id, day, metric)
);

-- Optional row-level security: app sets  SET app.tenant_id = '<id>'  per connection/transaction
CREATE ROLE app_user NOLOGIN;
GRANT SELECT, INSERT ON events, dashboard_daily, tenants TO app_user;
ALTER TABLE events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_daily  ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON events
  USING (tenant_id = current_setting('app.tenant_id')::int)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::int);
CREATE POLICY tenant_isolation ON dashboard_daily
  USING (tenant_id = current_setting('app.tenant_id')::int)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::int);
-- Load: \copy events(tenant_id,event_id,ts,type,user_id,properties) FROM 'data/events.csv' CSV HEADER
