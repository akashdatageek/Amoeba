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
After an accept, the rollback watch reverts to the parent version if the next practice tasks fall below the alarm
window's mean − noise (§9.3).
"""
from __future__ import annotations

import math
from statistics import mean, stdev

from pydantic import BaseModel, Field

from amoeba.adapt.experimenter import ReplayResult
from amoeba.adapt.recipe import Edit, Recipe, adapt_config, validate_recipe
from amoeba.adapt.stream import leaks


def cfg() -> dict:
    return adapt_config()["gate"]


# ---- statistics (no scipy) ------------------------------------------------------------------------------------------
# box: gate
def noise_floor(cal: ReplayResult | list[float]) -> float:
    """2 × std(d_AA) / √n over the calibration's post pairs (A′ − A)."""
    d = [p.d for p in cal.post()] if isinstance(cal, ReplayResult) else list(cal)
    if len(d) < 2:
        return 0.0
    return round(2 * stdev(d) / math.sqrt(len(d)), 4)


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


# box: gate
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


# box: gate
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


# box: gate
def paired_p(d: list[float]) -> tuple[float, str]:
    """§9.2.2: a t-test when every d is distinct and n ≥ ttest_min_n, otherwise the Wilcoxon signed-rank test."""
    if len(d) >= cfg()["ttest_min_n"] and len(set(d)) == len(d):
        return ttest_greater(d), "t-test"
    return wilcoxon_greater(d), "wilcoxon"


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


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


# box: gate
def decide(recipe_A: Recipe, recipe_B: Recipe, h: Hypothesis, res: ReplayResult, noise: float, N: int,
           heldout: list, envelope=None, sample_draft=None) -> Decision:
    """§9.2 rules 1–6 on the experiment's pairs; every failing rule adds its reason."""
    g = cfg()
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
    if hb > ha + g["honesty_margin"]:
        reasons.append(f"5 honesty regression: flags {hb:.2f} > {ha:.2f} + {g['honesty_margin']}")
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
                    n_post=len(post), n_pre=len(pre))


# box: gate
def decision_row(h: Hypothesis, recipe_A: Recipe, recipe_B: Recipe, dec: Decision, runs: str) -> dict:
    """The ledger's decision row (§9.4)."""
    return {"event": "decision", "family": h.family, "hypothesis_id": h.hypothesis_id,
            "recipe_from": recipe_A.version, "recipe_to": recipe_B.version, "edit": h.edit.model_dump(),
            "predicted_delta": h.predicted_delta, **dec.model_dump(exclude={"decision", "reasons"}),
            "decision": dec.decision, "reasons": dec.reasons, "runs": runs}


# box: gate
def rollback_watch(after_accept: list[float], alarm_window_mean: float, noise: float, window: int | None = None) -> str:
    """§9.3: over the first `window` practice scores after an accept — "reverted" if their mean is below the mean of
    the window that raised the alarm minus the noise floor, "kept" otherwise; "watching" until there are enough."""
    window = window or cfg()["rollback_window"]
    if len(after_accept) < window:
        return "watching"
    return "reverted" if mean(after_accept[:window]) < alarm_window_mean - noise else "kept"
