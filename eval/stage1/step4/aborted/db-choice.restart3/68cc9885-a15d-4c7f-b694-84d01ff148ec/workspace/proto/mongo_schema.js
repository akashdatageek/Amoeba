// MongoDB (Atlas) prototype: run with mongosh <uri> mongo_schema.js
const dbx = db.getSiblingDB("analytics");
dbx.createCollection("tenants", { validator: { $jsonSchema: {
  bsonType: "object", required: ["_id","name","region"],
  properties: { _id:{bsonType:"int"}, name:{bsonType:"string"}, region:{enum:["eu","non-eu"]} } } } });

dbx.createCollection("events", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["tenant_id","event_id","ts","type","user_id"],
    properties: {
      tenant_id:{bsonType:"int"}, event_id:{bsonType:["long","int"]},
      ts:{bsonType:"date"}, type:{bsonType:"string"},
      user_id:{bsonType:["long","int"]}, properties:{bsonType:"object"} } } },
  validationAction: "error"
  // Option for scale: time series collection {timeseries:{timeField:"ts",metaField:"tenant_id"}} (not used: keeps parity with PG rows)
});
dbx.events.createIndex({ tenant_id: 1, ts: -1 });
dbx.events.createIndex({ tenant_id: 1, type: 1, ts: 1 });
dbx.events.createIndex({ tenant_id: 1, event_id: 1 }, { unique: true });

dbx.createCollection("dashboard_daily", { validator: { $jsonSchema: {
  bsonType: "object", required: ["tenant_id","day","metric","value"],
  properties: { tenant_id:{bsonType:"int"}, day:{bsonType:"date"}, metric:{bsonType:"string"}, value:{bsonType:"double"} } } } });
dbx.dashboard_daily.createIndex({ tenant_id: 1, day: 1, metric: 1 }, { unique: true });
// Load: mongoimport --db analytics --collection events --file data/events.jsonl
// Isolation: MongoDB has no row-level security; every access goes through a tenant-scoped data-access layer (see queries_mongo.py scoped()).
