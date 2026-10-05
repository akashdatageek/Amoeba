"""D84 — Box 8, the Gate (Phase 2 spec §9). Plain code only; no model call. Thresholds: amoeba/config/adapt.yaml gate.

Noise floor (once per family and recipe version, §9.1): recipe A against itself (A vs A′, other seeds) on the held-out
post slice; noise = 2 × std(d_AA) / √n.

Decision, in order (§9.2) — any failure rejects and its reason is recorded (every failing rule is listed):
  1. valid: the recipe validates (V1–V5) and the edit passes the leakage screen (re-checked here)
  2. real gain: mean(d) > max(noise, min_gain) over the post pairs, and a one-sided paired test (Wilcoxon signed-rank;
     a t-test when every d is distinct and n ≥ 10) has p × N < alpha, N = hypotheses tried since the last accept
  3. prediction held: sign(mean d) = sign(predicted_delta); an unpredicted gain is rejected as unexplained_gain
  4. cost justified: mean(tokens_B) / mean(tokens_A) ≤ 1.25, or ≤ 2.0 when mean(d) ≥ 0.15
  5. no honesty regression: mean(honesty_B) ≤ mean(honesty_A) + 0.2, and no new sandbox or side-effect refusal
  6. retention: mean(score_B − score_A) on the held-out pre tasks ≥ −noise
Gate v3 (D91, the default): rule 2 on per-task means (repeats averaged first) with a one-sided paired permutation test
(exact when ≤ 20 tasks), each hypothesis tested at its pre-set alpha_i from a fixed quota of 6 per family per stream
(no reset on accept); no prediction rule (predicted_delta is kept and its accuracy reported); rules 1, 4, 5, 5b, 6 as
in v2, rule 6 on per-task means. Noise v3 = 2 × std(per-task mean d_AA) / √n_tasks.
After an accept, the rollback watch reverts to the parent version if the next practice tasks fall below the alarm
window's mean − noise (§9.3).
"""
from __future__ import annotations

import math
from statistics import mean, stdev

from pydantic import BaseModel, Field

from amoeba.adapt.experimenter import ReplayResult, flagged
from amoeba.task.models import infra_error
from amoeba.adapt.recipe import Edit, Recipe, adapt_config, validate_recipe
from amoeba.adapt.stream import leaks


# box: gate
def cfg() -> dict:
    return adapt_config()["gate"]


# ---- statistics (no scipy) ------------------------------------------------------------------------------------------
# box: gate_stats
def noise_floor(cal: ReplayResult | list[float]) -> float:
    """2 × std(d_AA) / √n over the calibration's post pairs (A′ − A)."""
    d = [p.d for p in cal.post()] if isinstance(cal, ReplayResult) else list(cal)
    if len(d) < 2:
        return 0.0
    return round(2 * stdev(d) / math.sqrt(len(d)), 4)


# box: gate_stats
def _ranks(xs: list[float]) -> list[float]:
    """Average ranks (1-based) of xs, ties sharing the mean rank."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


# box: gate_stats
def wilcoxon_greater(d: list[float]) -> float:
    """One-sided Wilcoxon signed-rank p-value for H1: the median of d is > 0 (zeros dropped; exact, ties by mean
    rank: the null distribution of W+ over the 2^n sign assignments, by dynamic programming on doubled ranks)."""
    x = [v for v in d if abs(v) > 1e-12]
    n = len(x)
    if n == 0:
        return 1.0
    ranks = [int(round(2 * r)) for r in _ranks([abs(v) for v in x])]
    w = sum(r for r, v in zip(ranks, x) if v > 0)
    dist = {0: 1}
    for r in ranks:
        nxt = dict(dist)
        for s, c in dist.items():
            nxt[s + r] = nxt.get(s + r, 0) + c
        dist = nxt
    return sum(c for s, c in dist.items() if s >= w) / 2 ** n


# box: gate_stats
def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c, dd = 1.0, 1 - qab * x / qap
    dd = 1 / (dd if abs(dd) > 1e-30 else 1e-30)
    h = dd
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        dd = 1 + aa * dd
        dd = 1 / (dd if abs(dd) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30
        h *= dd * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        dd = 1 + aa * dd
        dd = 1 / (dd if abs(dd) > 1e-30 else 1e-30)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-30 else 1e-30
        de = dd * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


# box: gate_stats
def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lb) * _betacf(a, b, x) / a
    return 1 - math.exp(lb) * _betacf(b, a, 1 - x) / b


# box: gate_stats
def ttest_greater(d: list[float]) -> float:
    """One-sided paired t-test p-value for H1: mean(d) > 0."""
    n = len(d)
    if n < 2:
        return 1.0
    s = stdev(d)
    if s == 0:
        return 0.0 if mean(d) > 0 else 1.0
    t, df = mean(d) / (s / math.sqrt(n)), n - 1
    tail = 0.5 * _betainc(df / 2, 0.5, df / (df + t * t))     # P(T > |t|)
    return tail if t > 0 else 1 - tail


# box: gate_stats
def paired_p(d: list[float]) -> tuple[float, str]:
    """§9.2.2: a t-test when every d is distinct and n ≥ ttest_min_n, otherwise the Wilcoxon signed-rank test."""
    if len(d) >= cfg()["ttest_min_n"] and len(set(d)) == len(d):
        return ttest_greater(d), "t-test"
    return wilcoxon_greater(d), "wilcoxon"


# box: gate_stats
def task_means(pairs: list) -> dict[str, float]:
    """D91: d_t = mean over the repeats of score_B − mean over the repeats of score_A, per task (task order kept)."""
    by: dict[str, list] = {}
    for p in pairs:
        by.setdefault(p.task_id, []).append(p)
    return {k: round(mean(x.score_B for x in v) - mean(x.score_A for x in v), 6) for k, v in by.items()}


# box: gate_stats
def permutation_greater(d: list[float], exact_max: int | None = None, n_random: int | None = None,
                        seed: int | None = None) -> float:
    """D91: one-sided paired permutation (sign-flip) test of H1: mean(d) > 0. p = share of the 2^n sign assignments
    whose sum is ≥ the observed sum (identity included); exact when n ≤ exact_max, otherwise n_random assignments
    drawn with a fixed seed."""
    v3 = cfg().get("v3", {})
    exact_max = exact_max if exact_max is not None else int(v3.get("exact_max_tasks", 20))
    n_random = n_random if n_random is not None else int(v3.get("random_assignments", 100_000))
    seed = seed if seed is not None else int(v3.get("seed", 0))
    n = len(d)
    if n == 0:
        return 1.0
    obs = sum(d) - 1e-9
    if n <= exact_max:
        sums = [0.0]
        for x in d:                       # every signed sum, by doubling
            sums = [s + x for s in sums] + [s - x for s in sums]
        return sum(s >= obs for s in sums) / len(sums)
    import random
    rng = random.Random(seed)
    hits = 1                              # the identity
    for _ in range(n_random - 1):
        hits += sum(x if rng.random() < 0.5 else -x for x in d) >= obs
    return hits / n_random


# box: gate_stats
def noise_floor_tasks(cal: ReplayResult) -> float:
    """D91: 2 × std(per-task mean d_AA) / √n_tasks over the calibration's post (gate-set) pairs."""
    d = list(task_means(cal.post()).values())
    if len(d) < 2:
        return 0.0
    return round(2 * stdev(d) / math.sqrt(len(d)), 4)


# box: gate_stats
def task_spread(cal: ReplayResult) -> dict[str, dict]:
    """D91: each gate task's scores across seeds in the calibration (A and A′) and their standard deviation."""
    out: dict[str, dict] = {}
    for p in cal.post():
        e = out.setdefault(p.task_id, {"scores_A": [], "scores_A2": []})
        e["scores_A"].append(p.score_A)
        e["scores_A2"].append(p.score_B)
    for e in out.values():
        allv = e["scores_A"] + e["scores_A2"]
        e["spread"] = round(stdev(allv), 4) if len(allv) > 1 else 0.0
        e["range"] = round(max(allv) - min(allv), 4)
    return out


# box: gate
def alpha_for(i: int) -> float | None:
    """D91: the pre-set alpha of the family's i-th hypothesis in a stream (1-based); None once the quota is spent."""
    alphas = list(cfg().get("v3", {}).get("alphas", []))
    return float(alphas[i - 1]) if 1 <= i <= len(alphas) else None


# ---- the decision ---------------------------------------------------------------------------------------------------
# box: gate
class Hypothesis(BaseModel):
    """A hand-written hypothesis (week 1) — the Architect's output has the same shape (D87)."""

    hypothesis_id: str
    family: str
    edit: Edit
    rationale: str = ""
    metric: str = "score"
    predicted_delta: float
    diagnosis_ref: str = ""


# box: gate
class Decision(BaseModel):
    decision: str                               # accept | reject
    reasons: list[str] = Field(default_factory=list)
    observed_delta: float | None = None
    noise: float = 0.0
    p: float | None = None
    test: str = ""
    N: int = 1
    p_adj: float | None = None
    cost_ratio: float | None = None
    honesty_A: float | None = None
    honesty_B: float | None = None
    refusals_A: int = 0
    refusals_B: int = 0
    retention_delta: float | None = None
    unexplained_gain: bool = False
    n_post: int = 0
    n_pre: int = 0
    gate_version: str = "v2"
    honesty_share_A: float | None = None      # v2 rule 5: share of post runs with >= 1 honesty signal
    honesty_share_B: float | None = None
    error_rate_A: float | None = None         # v2 rule 5b: share of post runs that ended in an error
    error_rate_B: float | None = None
    honesty_counts_A: dict = Field(default_factory=dict)   # per-tag totals over the post runs: information only
    honesty_counts_B: dict = Field(default_factory=dict)
    n_tasks: int | None = None                 # v3 (D91): rule 2 on per-task means
    repeats: int | None = None
    task_d: dict = Field(default_factory=dict)
    hypothesis_index: int | None = None            # v3: the i-th hypothesis of the family in this stream ...
    alpha: float | None = None                 # ... tested at alpha_i (pre-set in adapt.yaml)
    prediction: dict = Field(default_factory=dict)   # v3: sign_ok, abs_error (reported, never a rule)
    cost_basis: str = "tokens"                 # D97: rule 4 on USD when both arms have prices, else on tokens
    usd_A: float | None = None
    usd_B: float | None = None


# box: gate
def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


# box: gate, ov_m8
def decide(recipe_A: Recipe, recipe_B: Recipe, h: Hypothesis, res: ReplayResult, noise: float, N: int,
           heldout: list, envelope=None, sample_draft=None, version: str | None = None,
           hypothesis_index: int | None = None, alpha: float | None = None) -> Decision:
    """§9.2 rules 1–6 on the experiment's pairs; every failing rule adds its reason. version: "v1" (Stage A rule 5:
    summed flags per run, errors included), "v2" (D84b: rule 5 per run, rule 5b for errors) or "v3" (D91: rule 2 on
    per-task means with a permutation test at alpha_i of the fixed quota, no prediction rule; N is not used);
    default adapt.yaml. alpha overrides alpha_i (the single pre-registered check)."""
    g = cfg()
    version = version or g.get("version", "v2")
    if version == "v3":
        return _decide_v3(recipe_B, h, res, noise, heldout, envelope, sample_draft, hypothesis_index, alpha)
    reasons: list[str] = []
    post, pre = res.post(), res.pre()
    # 1. valid (re-checked here; the Architect's own check is not trusted)
    bad = validate_recipe(recipe_B, envelope, sample_draft)
    if bad:
        reasons.append("1 invalid recipe: " + "; ".join(f"{v.rule} {v.detail}" for v in bad))
    leak = [x for t in h.edit.texts() for x in leaks(t, heldout)]
    if leak:
        reasons.append("1 leakage: " + "; ".join(leak))
    # 2. real gain
    d = [p.d for p in post]
    md = round(mean(d), 4) if d else 0.0
    p, test = paired_p(d) if d else (1.0, "none")
    p_adj = min(1.0, p * N)
    if not d:
        reasons.append("2 no post pairs")
    elif not md > max(noise, g["min_gain"]):
        reasons.append(f"2 no real gain: mean d {md:+.3f} <= max(noise {noise:.3f}, {g['min_gain']})")
    elif not p_adj < g["alpha"]:
        reasons.append(f"2 not significant: p {p:.4f} x N {N} = {p_adj:.4f} >= {g['alpha']} ({test})")
    # 3. prediction held
    unexplained = False
    if d and _sign(md) != _sign(h.predicted_delta):
        unexplained = md > 0
        reasons.append(("3 unexplained_gain" if unexplained else "3 prediction failed") +
                       f": observed {md:+.3f}, predicted {h.predicted_delta:+.3f}")
    # 4. cost justified
    ta, tb = (mean([x.tokens_A for x in post]), mean([x.tokens_B for x in post])) if post else (0, 0)
    ratio = round(tb / ta, 3) if ta else None
    cap = g["cost_ratio_big_gain"] if md >= g["big_gain"] else g["cost_ratio"]
    if ratio is not None and ratio > cap:
        reasons.append(f"4 cost not justified: token ratio {ratio:.2f} > {cap}")
    # 5. no honesty regression
    ha, hb = (round(mean([x.honesty_A for x in post]), 3), round(mean([x.honesty_B for x in post]), 3)) if post else (0, 0)
    sa, sb, ea, eb = honesty_shares(post)
    if version == "v1":
        if hb > ha + g["honesty_margin"]:
            reasons.append(f"5 honesty regression: flags {hb:.2f} > {ha:.2f} + {g['honesty_margin']}")
    else:                                       # v2 (D84b): per run, errors apart
        n = len(post)                            # compared as whole runs, so a difference of exactly the margin passes
        fa, fb, xa, xb = (round(v * n) if v is not None else None for v in (sa, sb, ea, eb))
        if sb is not None and fb - fa > g["honesty_share_margin"] * n + 1e-9:
            reasons.append(f"5 honesty regression: flagged runs {sb:.2f} - {sa:.2f} > {g['honesty_share_margin']}")
        if eb is not None and xb - xa > g["error_rate_margin"] * n + 1e-9:
            reasons.append(f"5b reliability regression: error rate {eb:.2f} - {ea:.2f} > {g['error_rate_margin']}")
    ra, rb = sum(x.refusals_A for x in res.pairs), sum(x.refusals_B for x in res.pairs)
    if rb > ra:
        reasons.append(f"5 new refusals: {rb} in arm B against {ra} in arm A")
    # 6. retention on the held-out pre tasks
    ret = round(mean([x.d for x in pre]), 4) if pre else None
    if ret is not None and ret < -noise:
        reasons.append(f"6 retention: pre-task mean d {ret:+.3f} < -noise {-noise:.3f}")
    return Decision(decision="reject" if reasons else "accept", reasons=reasons, observed_delta=md, noise=noise,
                    p=round(p, 6), test=test, N=N, p_adj=round(p_adj, 6), cost_ratio=ratio, honesty_A=ha,
                    honesty_B=hb, refusals_A=ra, refusals_B=rb, retention_delta=ret, unexplained_gain=unexplained,
                    n_post=len(post), n_pre=len(pre), gate_version=version, honesty_share_A=sa, honesty_share_B=sb,
                    error_rate_A=ea, error_rate_B=eb, honesty_counts_A=_counts(post, "A"),
                    honesty_counts_B=_counts(post, "B"))


# box: gate_rules
def _rules_1_4_5(recipe_B: Recipe, h: Hypothesis, res: ReplayResult, md: float, heldout: list, envelope,
                 sample_draft, reasons: list[str]) -> dict:
    """Rules 1, 4, 5 (v2, per run) and 5b, shared by v3."""
    g = cfg()
    post = res.post()
    bad = validate_recipe(recipe_B, envelope, sample_draft)
    if bad:
        reasons.append("1 invalid recipe: " + "; ".join(f"{v.rule} {v.detail}" for v in bad))
    leak = [x for t in h.edit.texts() for x in leaks(t, heldout)]
    if leak:
        reasons.append("1 leakage: " + "; ".join(leak))
    ta, tb = (mean([x.tokens_A for x in post]), mean([x.tokens_B for x in post])) if post else (0, 0)
    ua, ub = (mean([x.usd_A for x in post]), mean([x.usd_B for x in post])) if post else (0, 0)
    basis = "usd" if ua > 0 and ub > 0 else "tokens"   # D97: USD from registry prices; tokens while prices are 0
    ratio = round((ub / ua) if basis == "usd" else (tb / ta), 3) if (ua if basis == "usd" else ta) else None
    cap = g["cost_ratio_big_gain"] if md >= g["big_gain"] else g["cost_ratio"]
    if ratio is not None and ratio > cap:
        reasons.append(f"4 cost not justified: {'USD' if basis == 'usd' else 'token'} ratio {ratio:.2f} > {cap}")
    ha, hb = (round(mean([x.honesty_A for x in post]), 3), round(mean([x.honesty_B for x in post]), 3)) if post else (0, 0)
    sa, sb, ea, eb = honesty_shares(post)
    n = len(post)
    fa, fb, xa, xb = (round(v * n) if v is not None else None for v in (sa, sb, ea, eb))
    if sb is not None and fb - fa > g["honesty_share_margin"] * n + 1e-9:
        reasons.append(f"5 honesty regression: flagged runs {sb:.2f} - {sa:.2f} > {g['honesty_share_margin']}")
    if eb is not None and xb - xa > g["error_rate_margin"] * n + 1e-9:
        reasons.append(f"5b reliability regression: error rate {eb:.2f} - {ea:.2f} > {g['error_rate_margin']}")
    ra, rb = sum(x.refusals_A for x in res.pairs), sum(x.refusals_B for x in res.pairs)
    if rb > ra:
        reasons.append(f"5 new refusals: {rb} in arm B against {ra} in arm A")
    return dict(cost_ratio=ratio, cost_basis=basis, usd_A=round(ua, 6), usd_B=round(ub, 6), honesty_A=ha,
                honesty_B=hb, refusals_A=ra, refusals_B=rb, honesty_share_A=sa,
                honesty_share_B=sb, error_rate_A=ea, error_rate_B=eb, honesty_counts_A=_counts(post, "A"),
                honesty_counts_B=_counts(post, "B"))


# box: gate
def _decide_v3(recipe_B: Recipe, h: Hypothesis, res: ReplayResult, noise: float, heldout: list, envelope,
               sample_draft, hypothesis_index: int | None, alpha: float | None) -> Decision:
    """D91: Gate v3 (spec §9.2, Gate v3)."""
    g = cfg()
    reasons: list[str] = []
    post, pre = res.post(), res.pre()
    td = task_means(post)
    d = list(td.values())
    md = round(mean(d), 4) if d else 0.0
    a = alpha if alpha is not None else (alpha_for(hypothesis_index) if hypothesis_index else None)
    p = permutation_greater(d) if d else 1.0
    if not d:
        reasons.append("2 no post pairs")
    elif a is None:
        reasons.append(f"2 quota spent: hypothesis {hypothesis_index} of {len(g.get('v3', {}).get('alphas', []))}")
    elif not md > max(noise, g["min_gain"]):
        reasons.append(f"2 no real gain: mean task d {md:+.3f} <= max(noise {noise:.3f}, {g['min_gain']})")
    elif not p <= a:
        reasons.append(f"2 not significant: permutation p {p:.4f} > alpha {a:.4f} ({len(d)} tasks)")
    rest = _rules_1_4_5(recipe_B, h, res, md, heldout, envelope, sample_draft, reasons)
    ret_d = list(task_means(pre).values())
    ret = round(mean(ret_d), 4) if ret_d else None
    if ret is not None and ret < -noise:
        reasons.append(f"6 retention: pre-task mean d {ret:+.3f} < -noise {-noise:.3f}")
    reps = round(len(post) / len(td)) if td else None
    pred = {"sign_ok": _sign(md) == _sign(h.predicted_delta), "abs_error": round(abs(h.predicted_delta - md), 4)} \
        if d else {}
    return Decision(decision="reject" if reasons else "accept", reasons=reasons, observed_delta=md, noise=noise,
                    p=round(p, 6), test="permutation", N=hypothesis_index or 0, p_adj=None, retention_delta=ret,
                    n_post=len(post), n_pre=len(pre), gate_version="v3", n_tasks=len(td), repeats=reps,
                    task_d=td, hypothesis_index=hypothesis_index, alpha=a, prediction=pred, **rest)


# box: gate_rules
def honesty_shares(post: list) -> tuple:
    """v2: (flagged share A, flagged share B, error rate A, error rate B) over the post pairs; None without pairs."""
    if not post:
        return None, None, None, None
    n = len(post)

    def share(arm):
        return round(sum(flagged(getattr(p, f"flags_{arm}")) for p in post) / n, 3)

    def errs(arm):                              # D111: agent errors only; an infra error is never the team's
        return round(sum(bool(e := getattr(p, f"error_{arm}")) and not infra_error(e) for p in post) / n, 3)
    return share("A"), share("B"), errs("A"), errs("B")


# box: gate_rules
def _counts(post: list, arm: str) -> dict:
    out: dict = {}
    for p in post:
        for k, v in (getattr(p, f"flags_{arm}") or {}).items():
            out[k] = out.get(k, 0) + v
    return out


# box: gate
def decision_row(h: Hypothesis, recipe_A: Recipe, recipe_B: Recipe, dec: Decision, runs: str,
                 post_hoc: bool = False) -> dict:
    """The ledger's decision row (§9.4), with its gate version and whether it was decided after the fact."""
    return {"event": "decision", "family": h.family, "hypothesis_id": h.hypothesis_id,
            "recipe_from": recipe_A.version, "recipe_to": recipe_B.version, "edit": h.edit.model_dump(),
            "predicted_delta": h.predicted_delta, **dec.model_dump(exclude={"decision", "reasons"}),
            "decision": dec.decision, "reasons": dec.reasons, "runs": runs, "post_hoc": post_hoc}


# box: gate_rollback
def rollback_watch(after_accept: list[float], alarm_window_mean: float, noise: float, window: int | None = None) -> str:
    """§9.3: over the first `window` practice scores after an accept — "reverted" if their mean is below the mean of
    the window that raised the alarm minus the noise floor, "kept" otherwise; "watching" until there are enough."""
    window = window or cfg()["rollback_window"]
    if len(after_accept) < window:
        return "watching"
    return "reverted" if mean(after_accept[:window]) < alarm_window_mean - noise else "kept"


# box: prune
def decide_prune(res, noise: float) -> dict:
    """D100: the Gate on a prune (arm A = the recipe, arm B = it without one line, on the gate set). Accept when
    removing the line does not lower the score beyond noise AND lowers cost (USD when both arms have prices, else
    tokens). Plain code; the same noise floor as the family's hypotheses."""
    pairs = res.pairs
    if not pairs:
        return {"decision": "reject", "reasons": ["no pairs"], "observed_delta": None}
    ma, mb = mean(p.score_A for p in pairs), mean(p.score_B for p in pairs)
    ua, ub = mean(p.usd_A or 0.0 for p in pairs), mean(p.usd_B or 0.0 for p in pairs)
    ta, tb = mean(p.tokens_A for p in pairs), mean(p.tokens_B for p in pairs)
    basis = "usd" if ua > 0 and ub > 0 else "tokens"
    ca, cb = (ua, ub) if basis == "usd" else (ta, tb)
    reasons = []
    if ma - mb > noise:
        reasons.append(f"score falls without the line: {ma:.3f} -> {mb:.3f} (noise {noise:.3f})")
    if not cb < ca:
        reasons.append(f"no cost saved: {basis} {ca:.4g} -> {cb:.4g}")
    return {"decision": "reject" if reasons else "accept", "reasons": reasons or ["no loss beyond noise, cheaper"],
            "observed_delta": round(mb - ma, 4), "score_A": round(ma, 4), "score_B": round(mb, 4),
            "cost_basis": basis, "cost_A": round(ca, 6), "cost_B": round(cb, 6), "n_pairs": len(pairs)}
