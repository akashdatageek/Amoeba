"""D156 — the preflight script: one table, ok / missing / how to fix, before any real run; a non-zero exit when
anything a task category needs is missing. Offline: every outside call goes through a fake World."""
import json

from amoeba.llm.quota import parse_quota
from scripts.preflight import CATEGORIES, LIBS, Row, World, exit_code, main, run_checks, table

PER_MINUTE = ("Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota. * Quota exceeded "
              "for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 15, model: "
              "gemma-4-31b\\nPlease retry in 39.6s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': "
              "'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': "
              "'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': "
              "'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaValue': '15'}]}, {'@type': "
              "'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '39s'}]}}]")
PER_DAY = PER_MINUTE.replace("PerMinute", "PerDay").replace("'quotaValue': '15'", "'quotaValue': '1500'") \
    .replace("limit: 15,", "limit: 1500,")
SECRET = "sk-THIS-MUST-NEVER-PRINT"


def test_quota_replies_are_read():
    m = parse_quota(PER_MINUTE)
    assert (m["kind"], m["limit"], m["retry_s"]) == ("minute", 15, 39.0)
    d = parse_quota(PER_DAY)
    assert (d["kind"], d["limit"]) == ("daily", 1500)
    assert parse_quota("Error code: 500 - internal") is None
    assert parse_quota("RESOURCE_EXHAUSTED quotaId: 'GenerateContentInputTokensPerModelPerMinute-FreeTier'")["kind"] \
        == "minute"


class Box:
    """A toolbox stand-in: answers each local tool call from a table."""
    def __init__(self, answers, attachable=("xlsx", "docx", "pptx", "pdf")):
        self.answers, self.attachable, self.called = answers, attachable, []

    def call(self, tool, text):
        self.called.append(tool)
        a = self.answers.get(tool, "")
        return a(text) if callable(a) else a

    def attach(self, name):
        return name in self.attachable


def lib_answer(missing=(), soffice=True, office=True):
    def bash(text):
        if "import importlib" in text:
            return "[local:Bash]\n" + json.dumps({m: (m not in missing) for m in LIBS})
        if "soffice" in text and "office_check" not in text:
            return "[local:Bash]\n/usr/bin/soffice" if soffice else "[local:Bash error]\n"
        if "office_check" in text or "preflight_office" in text:
            return "[local:Bash]\n" + json.dumps({"ok": office, "detail": "=A1*A2 gave 6" if office else "gave None"})
        return "[local:Bash]\nhello"
    return bash


class Fake(World):
    def __init__(self, mode="sandbox", **kw):
        super().__init__(mode=mode, profile="gemma-api", skip_model_check=False)
        self.env = {"GEMINI_API_KEY": SECRET, "TAVILY_API_KEY": SECRET, "AMOEBA_SANDBOX": "1"}
        self.kw = kw
        self.box = Box({"Bash": lib_answer(kw.get("missing", ()), kw.get("soffice", True), kw.get("office", True)),
                        "Read": "[local:Read]\nhello", "Write": "[local:Write]\nok", "Edit": "[local:Edit]\nok",
                        "Glob": "[local:Glob]\npreflight.txt", "Grep": "[local:Grep]\npreflight.txt"},
                       kw.get("attachable", ("xlsx", "docx", "pptx", "pdf")))

    def chat(self, prompt):
        if "chat_error" in self.kw:
            raise RuntimeError(self.kw["chat_error"])
        return "ok"

    def tavily_search(self, q):
        return [{"url": "https://example.org"}]

    def tavily_usage(self):
        return self.kw.get("usage")

    def model_check(self):
        probes = [{"probe": p, "status": "ok"} for p in ("reading", "planner", "step (native tools)", "Final_Output")]
        for p in probes:
            if p["probe"] in self.kw.get("failed_probes", ()):
                p["status"] = "unreadable"
        return {"protocol": "v2", "probes": probes}

    def sh(self, cmd):
        if cmd[:2] == ["docker", "info"]:
            return (0, "ok") if self.kw.get("docker", True) else (1, "Cannot connect to the Docker daemon")
        if cmd[:3] == ["docker", "image", "inspect"]:
            return (0, "[]") if self.kw.get("image", True) else (1, "No such image")
        return 0, ""

    def gateway_health(self):
        return "healthy"

    def pool_skills(self):
        return [{"name": n} for n in self.kw.get("skills", ("xlsx", "docx", "pptx", "pdf"))]

    def toolbox(self):
        return self.box

    def rate(self):
        return {"rpm": 15, "rpd": 1500, "tpm": None}


def statuses(rows):
    return {r.check: r.status for r in rows}


def test_all_present_is_exit_zero_and_every_check_is_in_the_table(capsys):
    w = Fake()
    rows = run_checks(w)
    st = statuses(rows)
    assert exit_code(rows) == 0, [r for r in rows if r.status == "missing"]
    for name in ("GEMINI_API_KEY", "TAVILY_API_KEY", "gemma call", "tavily call", "model_check v2", "gemma rate limits",
                 "tavily credits", "docker", "openshell gateway", "image amoeba-sandbox:local", "pool skills",
                 "soffice", "office_check", *(f"local:{t}" for t in ("Bash", "Read", "Write", "Edit", "Glob", "Grep")),
                 *(f"import {m}" for m in LIBS), *(f"skill {s}" for s in ("xlsx", "docx", "pptx", "pdf"))):
        assert name in st, name
    assert set(w.box.called) >= {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}
    assert "RPM 15" in next(r.detail for r in rows if r.check == "gemma rate limits")
    assert "RPD 1500" in next(r.detail for r in rows if r.check == "gemma rate limits")
    assert st["tavily credits"] == "warn"                       # the API did not report them: said, not failed
    print(table(rows))
    out = capsys.readouterr().out
    assert "how to fix" in out and SECRET not in out


def test_a_missing_key_fails_with_how_to_fix_and_never_prints_a_key(capsys):
    w = Fake()
    w.env.pop("TAVILY_API_KEY")
    rows = run_checks(w)
    r = next(r for r in rows if r.check == "TAVILY_API_KEY")
    assert r.status == "missing" and "research" in r.needed_by and "environment" in r.fix
    assert exit_code(rows) == 1
    print(table(rows))
    assert SECRET not in capsys.readouterr().out


def test_a_daily_quota_reply_is_missing_and_names_the_day_limit():
    rows = run_checks(Fake(chat_error=PER_DAY))
    st = statuses(rows)
    assert st["gemma call"] == "missing" and st["gemma rate limits"] == "missing"
    assert "daily" in next(r.detail for r in rows if r.check == "gemma rate limits")
    assert set(next(r for r in rows if r.check == "gemma call").needed_by) == set(CATEGORIES)
    assert exit_code(rows) == 1


def test_a_per_minute_reply_is_a_warning_only():
    rows = run_checks(Fake(chat_error=PER_MINUTE))
    assert statuses(rows)["gemma rate limits"] == "warn"


def test_model_check_needs_reading_planner_step_and_final_output():
    rows = run_checks(Fake(failed_probes=("Final_Output",)))
    r = next(r for r in rows if r.check == "model_check v2")
    assert r.status == "missing" and "Final_Output" in r.detail and exit_code(rows) == 1


def test_a_missing_library_names_the_categories_that_need_it():
    rows = run_checks(Fake(missing=("scipy", "pytest")))
    st = {r.check: r for r in rows}
    assert st["import scipy"].status == "missing" and "exact" in st["import scipy"].needed_by
    assert st["import pytest"].status == "missing" and "software" in st["import pytest"].needed_by
    assert st["import numpy"].status == "ok"
    assert "Dockerfile" in st["import scipy"].fix                 # sandbox mode: fix the image
    rows = run_checks(Fake(mode="inprocess", missing=("scipy",)))
    assert "pip install" in next(r.fix for r in rows if r.check == "import scipy")


def test_no_office_and_a_missing_skill_fail_the_files_category():
    rows = run_checks(Fake(soffice=False, office=False, skills=("xlsx", "docx", "pdf"), attachable=("xlsx",)))
    st = {r.check: r for r in rows}
    assert st["soffice"].status == "missing" and st["office_check"].status == "missing"
    assert st["skill pptx"].status == "missing" and "files" in st["skill pptx"].needed_by
    assert st["skill docx"].status == "missing" and "attach" in st["skill docx"].detail


def test_docker_down_fails_sandbox_mode_but_not_inprocess():
    assert statuses(run_checks(Fake(docker=False)))["docker"] == "missing"
    assert statuses(run_checks(Fake(mode="inprocess", docker=False)))["docker"] == "n/a"


def test_a_check_that_crashes_is_a_missing_row_not_a_crash():
    class Broken(Fake):
        def gateway_health(self):
            raise ConnectionError("refused")
    r = next(r for r in run_checks(Broken()) if r.check == "openshell gateway")
    assert r.status == "missing" and "refused" in r.detail


def test_tavily_credits_when_reported():
    usage = {"account": {"plan_usage": 120, "plan_limit": 1000}}
    r = next(r for r in run_checks(Fake(usage=usage)) if r.check == "tavily credits")
    assert r.status == "ok" and "880" in r.detail
    empty = {"account": {"plan_usage": 1000, "plan_limit": 1000}}
    assert next(r for r in run_checks(Fake(usage=empty)) if r.check == "tavily credits").status == "missing"


def test_bash_answers_in_the_servers_json_shape_are_read():
    class Json(Fake):
        def __init__(self, **kw):
            super().__init__(**kw)
            plain = self.box.answers["Bash"]
            self.box.answers["Bash"] = lambda t: "[local:Bash]\n" + json.dumps(
                {"stdout": plain(t).split("\n", 1)[1], "stderr": ""})
    rows = run_checks(Json(missing=("PIL",)))
    st = statuses(rows)
    assert st["import PIL"] == "missing" and st["import numpy"] == "ok" and st["soffice"] == "ok"
    assert st["office_check"] == "ok"


def test_exit_code_rule():
    assert exit_code([Row("a", "warn", "", "", ("research",))]) == 0
    assert exit_code([Row("a", "missing", "", "", ())]) == 0        # needed by no category
    assert exit_code([Row("a", "missing", "", "", ("files",))]) == 1


def test_main_prints_the_table_and_returns_the_code(capsys):
    code = main(["--mode", "sandbox"], world=Fake(missing=("scipy",)))
    out = capsys.readouterr().out
    assert code == 1 and "import scipy" in out and "missing" in out and "exact" in out


def test_a_toolbox_that_will_not_start_names_the_fix():
    class NoBox(Fake):
        def __init__(self, err, **kw):
            super().__init__(**kw)
            self.err = err

        def toolbox(self):
            raise RuntimeError(self.err)
    fix = lambda err: next(r.fix for r in run_checks(NoBox(err)) if r.check == "local toolbox")
    assert "pip install -e ." in fix("python: No module named 'amoeba' | LocalServerError: bridge failed")
    assert "certs" in fix("GatewayError: docker sandboxes require launch-scoped gateway authentication")
    assert "must match" in fix("SandboxError: sandbox am-1 entered error phase")
