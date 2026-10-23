import inspect, json, datetime as dt
from datetime import timedelta, timezone
import watchdog as w
UTC=timezone.utc
SLA=dt.datetime(2026,10,22,4,0,tzinfo=UTC); RUN="2026-10-21"
m=lambda x: SLA+timedelta(minutes=x)
def find(prefix_all):
    for n,f in inspect.getmembers(w,inspect.isfunction):
        if all(p in n for p in prefix_all): return f
trig=find(["build","trigger"]) or find(["trigger"]); res=find(["resolve"])
def call(f,**avail):
    kw={}
    for p,v in inspect.signature(f).parameters.items():
        if p in avail: kw[p]=avail[p]
        elif v.default is inspect._empty: raise SystemExit(f"cannot map param {p} of {f.__name__}")
    return f(**kw)
def trig_payload(now,last_stage="dedup (no SUCCESS row)"):
    return call(trig,run_date=RUN,sla_deadline=SLA,sla=SLA,now=now,last_stage=last_stage,stage=last_stage,last_success_ts=None)
def save(name,p):
    json.dump({"STATUS":"NOT SENT - simulation only; routing_key is a placeholder","payload":p},open(f"payloads/{name}.NOT_SENT.json","w"),indent=2)
rows=[]
def add(sc,exp,act,note=""): rows.append((sc,exp,act,"PASS" if exp==act else "FAIL",note))
yn=lambda b:"page" if b else "no page"
add("1 On time: success at SLA-10 min, checked at SLA+5","no page",yn(w.should_page(m(5),SLA,m(-10))))
add("1b On time: success at SLA-10 min, checked at SLA+45","no page",yn(w.should_page(m(45),SLA,m(-10))))
add("2 Not finished, checked at SLA+29 min","no page",yn(w.should_page(m(29),SLA,None)))
add("3 Not finished, checked at exactly SLA+30 min","no page",yn(w.should_page(m(30),SLA,None)))
add("4 Not finished, checked at SLA+31 min","page",yn(w.should_page(m(31),SLA,None)))
add("5 Finished late at SLA+31 min, checked at SLA+31","page",yn(w.should_page(m(31),SLA,m(31))))
add("6 Finished at SLA+29 min, checked at SLA+45","no page",yn(w.should_page(m(45),SLA,m(29))))
add("7 Never started, no run row, at SLA+30","no page",yn(w.should_page(m(30),SLA,None)),"exactly +30 is not a page")
add("7b Never started, at SLA+30 min 1 s","page",yn(w.should_page(m(30)+timedelta(seconds=1),SLA,None)))
add("8 Still running (no SUCCESS row) at SLA+30","no page",yn(w.should_page(m(30),SLA,None)))
add("8b Still running (no SUCCESS row) at SLA+31","page",yn(w.should_page(m(31),SLA,None)),"payload last_stage shows where it is")
# dedup
keys=[]; pages=0
for t in (31,36,41):
    if w.should_page(m(t),SLA,None):
        pages+=1; p=trig_payload(m(t)); keys.append(p["dedup_key"])
add("9 Repeated checks at +31,+36,+41: distinct dedup_key values (PagerDuty folds same key into one incident)","1 distinct key, 3 identical triggers",f"{len(set(keys))} distinct key, {pages} identical triggers" if len(set(keys))==1 else f"{len(set(keys))} distinct keys","dedup_key="+(keys[0] if keys else "-"))
# naive datetime
try: w.should_page(dt.datetime(2026,10,22,4,31),SLA,None); r="no error"
except ValueError: r="ValueError"
add("10 Naive (timezone-less) datetime passed","ValueError",r)
p=trig_payload(m(31),"dedup (MERGE CLEAN.EVENTS)"); save("trigger",p)
rp=call(res,run_date=RUN); save("resolve",rp)
add("11 Resolve payload carries same dedup_key as trigger","True",str(rp["dedup_key"]==p["dedup_key"] and rp["event_action"]=="resolve"))
add("12 Trigger payload fields (event_action trigger, severity critical, placeholder routing key)","True",str(p["event_action"]=="trigger" and p["payload"]["severity"]=="critical" and "PLACEHOLDER" in p["routing_key"]))
ok=all(r[3]=="PASS" for r in rows)
t="| Scenario | Expected | Actual | Result | Note |\n|---|---|---|---|---|\n"+"\n".join("| "+" | ".join(r)+" |" for r in rows)
rep=f"""# watchdog_report.md - late-job watchdog simulation (NOT SENT)

Rule: page when the job has not finished by SLA deadline + 30 min. Exactly +30 min is not a page; +31 min is. Simulated SLA deadline = {SLA.isoformat()} (example), run_date = {RUN}.

Simulation was run with Python (`python3 sim_watchdog.py`). Result: {"ALL PASS" if ok else "FAILURES PRESENT"} ({sum(r[3]=="PASS" for r in rows)}/{len(rows)}).

## Scenario x expected x actual
{t}

## Payload files (all marked NOT SENT)
- payloads/trigger.NOT_SENT.json
- payloads/resolve.NOT_SENT.json

Trigger payload (NOT SENT):
```json
{json.dumps(p,indent=2)}
```
Resolve payload (NOT SENT):
```json
{json.dumps(rp,indent=2)}
```

## How the dedup_key works
Every check for the same run date builds the same dedup_key (`dau-nightly-<run_date>`). Repeated triggers within the same open incident are folded by PagerDuty into one incident (PagerDuty behaviour, not exercised here: nothing was sent). The watchdog may re-send every 5 min; scenario 9 shows 3 triggers with 1 distinct key. Success sends a resolve with the same key.

## watchdog.py
```python
{open('watchdog.py').read()}
```

Limitations: nothing was sent; Snowflake and PagerDuty were not reached. The routing key is a placeholder, last_success_ts is passed in by the test rather than read from OPS.JOB_RUNS, and PagerDuty-side dedup is assumed from the Events API v2 contract, not observed. The 04:00 UTC SLA is an example value.
"""
open("watchdog_report.md","w").write(rep)
print(t); print("trigger fn:",trig.__name__,inspect.signature(trig)); print("ALL PASS" if ok else "FAIL")
