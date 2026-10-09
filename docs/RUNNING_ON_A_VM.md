# Running Amoeba on a VM

This page says how to run Amoeba on a persistent Linux VM: single tasks and batches of tasks with
`scripts.run_task`, such as the probe tasks and the `--adapt on/off` comparison. (D117 removed the offline learning
loop and its `run_loop` / `run_experiment` scripts.)

Why a VM. In one day the cloud session restarted its container five times or more. Each restart killed the
detached runs. The HTTPS proxy port also changed once. Runs started before the change kept the old address and
ended with `api: APIConnectionError`. A VM with a service manager and direct network access avoids both.

## 1. The machine

- **Size.** 8 vCPU, 16 GB RAM, 60 GB SSD. Each run is one Python process; run several at once only on separate
  keys. With local tools on, each run also gets its own sandbox (1 CPU and 1 GiB each,
  `amoeba/config/localtools.yaml` `sandbox`). The cloud session had 4 CPUs and 15 GB; that is the minimum.
- **OS.** Ubuntu 24.04 LTS (any Linux with Landlock works). The sandbox needs Landlock as a hard requirement.
  Check: `cat /sys/kernel/security/lsm` must list `landlock`.
- **Python** 3.11 or newer (`requires-python = ">=3.11"` in `pyproject.toml`).
- **Docker** with Compose and BuildKit, only if you run with `--local-tools on` (the probes do):
  `sudo apt install docker.io docker-compose-v2 docker-buildx`, then `sudo systemctl enable --now docker`.
- **Node and the `claude` CLI are not needed on the host.** The sandbox image carries Claude Code 2.1.289 and runs
  `claude mcp serve` inside the sandbox. The host needs them only for `--local-tools-mode inprocess`, which also needs
  `AMOEBA_SANDBOX=1` and is not meant for a VM you care about.
- **Playwright/Chromium is not needed** for runs. Only `eval/bench5/make_pdf.py` uses it.
- **Time zone.** Pass `--timezone America/Chicago` on every run so "today" matches the earlier runs. Without it the
  machine's zone is used.

Use one unprivileged user for everything, for example `amoeba`. Add it to the `docker` group if you use the sandbox
(that group is root-equivalent; keep the VM single-purpose).

## 2. Setup

```bash
git clone git@github.com:<owner>/Amoeba.git ~/Amoeba && cd ~/Amoeba
git checkout v1-dev                          # or the branch you run
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test,local]"
pip install openshell                        # OpenShell client, only for --local-tools on (0.1.2 was used)
./clone_sources.sh                           # read-only source repos under repos/ (never imported)
pytest -q                                    # all offline; no key, no network
git config core.hooksPath tools/hooks        # as-built page rebuild after each commit (D55)
```

**The tool/skill pool.** `data/` is not in git. To keep the same pool and pins as the earlier runs, copy `data/pool/`
from the old checkout. Only for a new pool run `python -m amoeba pool refresh` (needs `registry.modelcontextprotocol.io`
and `github.com`).

**The LLM cache.** `runs/` is not in git either. Copy `runs/cache/` from the old checkout (rsync or scp). Then calls
already paid for replay for free when a run is resumed.

**The sandbox** (only for `--local-tools on`). Do this after the pool is in place, since the image bakes in
`data/pool/repos/anthropics_skills`:

```bash
sudo mkdir -p /var/lib/openshell
docker run --rm --user 0 -v /var/lib/openshell:/var/lib/openshell \
  ghcr.io/nvidia/openshell/gateway:latest generate-certs --output-dir /var/lib/openshell/tls   # once
CA_BUNDLE=<proxy CA, only behind a TLS-inspecting proxy> amoeba/config/sandbox/build.sh        # amoeba-sandbox:local
docker compose -p amoeba-sandbox -f amoeba/config/sandbox/docker-compose.yml up -d             # the gateway
docker compose -p amoeba-sandbox -f amoeba/config/sandbox/docker-compose.yml ps                # must show it running
```

The gateway listens on `127.0.0.1:17680` only. It has `restart: unless-stopped`, so it comes back after a reboot
once Docker is enabled.

## 3. Secrets

- Put the keys in one env file **outside the repo**, for example `~/work/keys.env`. Write plain `KEY=VALUE` lines.
  Use the names the code reads: `GEMINI_API_KEY` (Gemma and the `arch-text` profile), `TAVILY_API_KEY`
  (`--web-tools`), `OPENROUTER_API_KEY` (only for that profile).
- `chmod 600 ~/work/keys.env`. Never commit it. Never `cat` it into a log.
- Do not set `AMOEBA_API_KEY`, `AMOEBA_BASE_URL` or `AMOEBA_MODEL` in it. They override the profile; unset them.
- Do not put `GIT_*`, `GH_*`, `GITHUB_*`, cloud or SSH-agent variables in it.
- `run_task` has no `--env-file`; load the file into its environment (`set -a; . ~/work/keys.env; set +a`), as the
  scripts below do.
- **Agents never see the keys.** Every command an agent runs executes in the OpenShell sandbox with `LANG` as its
  only variable, no network, and no view of the repo, `eval/` or env files (`amoeba/localtools/sandbox.py`).
- **Evidence branch credentials stay in the harness.** Shipping (`git push origin` to `evidence`) runs in the
  harness process only, never in an agent. Give the `amoeba` user a GitHub deploy key with write access in `~/.ssh`
  (a key file in `~/.ssh/config`, not an SSH agent: services have none) and an SSH `origin` URL.
- **Key scan before every commit.** Stage, then run (exit 1 and the file names on a hit):

```bash
git diff --cached --name-only -z | python -c 'import sys; from pathlib import Path; from amoeba.adapt.evidence import key_scan, secret_values; env = dict(l.split("=", 1) for l in Path(sys.argv[1]).read_text().splitlines() if "=" in l and not l.startswith("#")); s = secret_values(env); h = [x for f in sys.stdin.read().split("\0") if f and Path(f).is_file() for x in key_scan(Path(f), s)]; print("\n".join(h) or "clean"); sys.exit(1 if h else 0)' ~/work/keys.env
```

It looks for key shapes (`AIza…`, `tvly-…`, `sk-…`, `ghp_…`, private keys) and for the values in your env file.

## 4. Network

- **Prefer direct egress.** The runs need `generativelanguage.googleapis.com` (Gemma) and `api.tavily.com`
  (`--web-tools`). Shipping needs `github.com`. Setup also needs PyPI, `ghcr.io`, Docker Hub and the npm registry
  (image build), and the pool hosts above.
- **If you must use a proxy,** set `HTTPS_PROXY`, `HTTP_PROXY` and `NO_PROXY=127.0.0.1,localhost` in the service
  (section 5). `NO_PROXY` keeps the gateway at `127.0.0.1:17680` off the proxy. Behind a TLS-inspecting proxy also
  set `SSL_CERT_FILE` to its CA, and pass `CA_BUNDLE` to `build.sh`.
- **A process reads the proxy once, at start** (the model client and the web tools' `urllib` opener). If the proxy
  address or port changes, a process started before it fails its calls with `api: APIConnectionError`.
- **D111.** Set `AMOEBA_PROXY_FILE` to a file that always holds the current proxy (`HTTPS_PROXY=…`). Then the model
  client re-reads it on a dropped connection and reconnects through the new proxy, and each new run starts with it.
  The web tools do not re-read it; restart the batch after a proxy change anyway (see section 5).
  A run that still ends in an infrastructure error gets `status: infra_error` in result.json and is never counted as
  the team's failure. On a VM with a fixed proxy or none, leave `AMOEBA_PROXY_FILE` unset.

## 5. Running long jobs

Run every long job as a **systemd service**. tmux also works, but nothing restarts it after a crash or reboot.

**Nobody answers questions in a service (D116).** `run_task` asks you about a name or term with close readings
before it plans. Under systemd there is no terminal, so such a run stops with status `needs_clarification` and
writes `clarification.json`. Answer ahead of time with `--clarify 'TERM=READING'`, or pass `--ask-assumed off` (the
answer then states its assumption).

**A batch script**, `~/work/batch.sh` (`chmod 700`), for example the probe tasks:

```bash
#!/bin/bash
# One batch of tasks. Running it again runs every task again; model calls already made replay from --llm-cache.
W=$HOME/work
cd "$HOME/Amoeba" && . .venv/bin/activate
set -a; . "$W/keys.env"; set +a; unset AMOEBA_MODEL AMOEBA_BASE_URL AMOEBA_API_KEY
python -m scripts.run_task --tasks tasks/probe_hard.jsonl --topology plan --llm openai --routing routed --niche general \
  --local-tools on --local-tools-mode sandbox --web-tools --replan on --timezone America/Chicago --draft-prompts d24 \
  --llm-cache runs/cache --llm-cache-mode record --max-rate-retries 8 --ask-assumed off \
  --runs-dir eval/probe_hard/runs || { echo "batch rc=$?"; exit 1; }
echo "== done $(date -u +%FT%TZ)"
```

`--min-seconds-between-calls` only acts with `--routing fixed` or `role`; with `--routing routed` a shared per-model
bucket spaces the calls (15 requests per minute for Gemma, `amoeba/config/models.yaml`).

**The unit**, `/etc/systemd/system/amoeba-batch.service`:

```ini
[Unit]
Description=Amoeba batch
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
User=amoeba
WorkingDirectory=/home/amoeba/Amoeba
ExecStart=/home/amoeba/work/batch.sh
Environment=PYTHONUNBUFFERED=1
# only with a proxy:
# Environment=HTTPS_PROXY=http://proxy:3128 HTTP_PROXY=http://proxy:3128 NO_PROXY=127.0.0.1,localhost
StandardOutput=append:/home/amoeba/work/logs/batch.log
StandardError=append:/home/amoeba/work/logs/batch.log
```

Run `mkdir -p ~/work/logs`, then `sudo systemctl daemon-reload && sudo systemctl start amoeba-batch`.

**After a crash or reboot: run the same command again.** `run_task` starts every task afresh in a new run folder,
but with the same `--llm-cache` folder every model call already made replays from the cache for free; local tool
commands run again, since they change files. To skip tasks that finished, remove them from the tasks file first.

**Rules.**

- **One batch per key at a time.** The key's limits (15 requests per minute, 1,500 per day for Gemma) are shared by
  everything that uses it. The shared bucket covers the processes of one user on one machine only
  (`~/.cache/amoeba/rate`, or `AMOEBA_RATE_DIR`). Stop the cloud session's runs before you start on the VM.
- A killed sandbox run can leave a container behind: check `docker ps --filter label=openshell`.

### The Stage E pilot: --adapt off vs on (D117)

The cloud session cannot hold it: its container restarted twice in 25 minutes during the first attempt and each
restart killed the run in progress (`docs/eval/stage_e/PLAN.md`). Run it here. `scripts/stage_e.py` runs each task
and seed with `--adapt off`, then `--adapt on` with the off run's draft and pool picks, so only Box 3 differs; it is
resumable (an arm with a result.json is skipped), but a run killed half-way starts again from the beginning.

`~/work/stage_e.sh` (`chmod 700`):

```bash
#!/bin/bash
# D117 Stage E pilot: H1-H3 x (adapt off, adapt on) x seed 0, then three injected H1 pairs (D119); one run at a time.
W=$HOME/work
cd "$HOME/Amoeba" && . .venv/bin/activate
set -a; . "$W/keys.env"; set +a; unset AMOEBA_MODEL AMOEBA_BASE_URL AMOEBA_API_KEY AMOEBA_TEST_FAULTS
echo "== code $(git rev-parse --short HEAD) $(date -u +%FT%TZ)"
OUT=eval/stage_e/pilot
FLAGS=(--topology plan --llm openai --routing routed --niche general
       --local-tools on --local-tools-mode sandbox --web-tools --replan off --timezone America/Chicago
       --draft-prompts d24 --max-rate-retries 8 --ask-assumed off)
python -m scripts.stage_e --tasks tasks/probe_hard.jsonl \
  --ids probe-h1-freight,probe-h2-income,probe-h3-ev-trucks --seeds 0 --out $OUT -- "${FLAGS[@]}"
echo "== clean pairs done rc=$? $(date -u +%FT%TZ)"
for F in capability:auto missing_input:auto tool_error:auto; do     # D119: after the clean H1 pair
  python -m scripts.stage_e --tasks tasks/probe_hard.jsonl --ids probe-h1-freight --seeds 0 --out $OUT \
    --inject-fault $F -- "${FLAGS[@]}"
  echo "== injected $F done rc=$? $(date -u +%FT%TZ)"
done
python -m scripts.stage_e_report $OUT > /dev/null && echo "== report written"
```

- **`--replan off` in both arms** (user decision, Oct 7): D63's mid-run re-plan changed H1's plan in one arm of the
  first attempt, so the arms differed for a reason other than `--adapt`.
- **No `--llm-cache`.** A cache would replay the off arm's calls into the on arm wherever the prompts match and make
  the arms look more alike than they are.
- **Check out a fixed commit** before starting (`git checkout --detach <commit>`) and leave it there until the pilot is
  done; the report names the commit on its first line.
- **Unit:** the oneshot unit of section 5 with `ExecStart=/home/amoeba/work/stage_e.sh` and
  `StandardOutput=append:/home/amoeba/work/logs/stage_e.log` (same for StandardError).
- **Injected pairs (D119).** The `for` loop runs H1 three more times per arm, each with one fault (`capability`,
  `missing_input`, `tool_error`, step picked by code). Both arms reuse the clean H1 off run's plan.json, so they must
  run after it; a missing clean run is skipped with a message. The pair runner sets `AMOEBA_TEST_FAULTS=1` for those
  run_task processes only; never put it in `keys.env` or the unit. Their runs go to
  `$OUT/<arm>/probe-h1-freight.s0.fault-<cause>/` and the report lists them apart (section "Injected faults").
- **Expected:** six clean runs, about 1.5 M billed tokens and 3–5 hours one at a time (H1 measured 24 and 23 minutes;
  one H2 attempt passed 77 minutes before it was killed); the six injected runs about 0.85–1.0 M more and 2.5–3 hours
  (`docs/eval/stage_e/PLAN.md`).
- **Results back:** `eval/stage_e/pilot/REPORT.md` and `report.json`, plus the run folders. Key scan (section 3),
  commit `eval/stage_e/pilot`, push; or copy the folder back and the report is re-run from it.

## 6. Monitoring

Use `tail -f ~/work/logs/batch.log`, `systemctl status amoeba-batch` and `grep -n 'error=api:' ~/work/logs/batch.log`.
Each finished run prints one line: `[plan] <task> score=… tokens=… calls=… status=… error=…`, then its cost line; the
batch ends with `== plan n=… mean_score=…`. Several `error=api:` lines in a row mean the network, proxy, key or quota
is broken: stop, fix the cause, start again. `… 429` lines mean the key is shared or over quota.

**Disk.** `du -sh runs/cache eval/*/runs; docker system df; df -h ~`. The sandbox and gateway images take a few GB.

## 7. Getting results back

- **Commit the run folders** you want to keep on the code branch (for example `eval/probe_hard/runs`), run the key
  scan (section 3), then commit. `runs/` (with the cache) is not committed.
- **The evidence branch.** `amoeba/adapt/evidence.py` can ship finished runs and event rows to the `evidence` branch
  (worktree `../amoeba-evidence`, at most one commit per 10 minutes plus a final one). Check the chain with
  `python -m scripts.verify_evidence --branch evidence`.
- **The as-built page.** `python tools/arch_update.py` rebuilds `docs/arch/` only when an input changed. It runs
  pytest and one toy run with the offline model. Box text is re-checked by the `arch-text` profile only when
  `GEMINI_API_KEY` is in the shell's environment; `ARCH_TEXT_LLM=off` keeps it offline (changed boxes are marked
  stale). The post-commit hook runs it in the background; its output is in `runs/arch_update.log`.

## 8. Checklist

- [ ] VM: 8 vCPU, 16 GB, 60 GB; Ubuntu 24.04; `landlock` in `/sys/kernel/security/lsm`; Python ≥3.11.
- [ ] Docker enabled at boot; gateway certs made; `amoeba-sandbox:local` built; gateway `up -d` (probes only).
- [ ] Repo cloned; venv; `pip install -e ".[test,local]"` (+ `openshell`); `./clone_sources.sh`; `pytest -q` passes.
- [ ] `git config core.hooksPath tools/hooks`; deploy key in `~/.ssh`; SSH `origin`.
- [ ] `data/pool/` and `runs/cache/` copied from the old checkout.
- [ ] `~/work/keys.env` outside the repo, `chmod 600`, plain `KEY=VALUE`, no `AMOEBA_*` or git/cloud names.
- [ ] Direct egress, or proxy set in the unit with `NO_PROXY=127.0.0.1,localhost`. Proxy changed → restart.
- [ ] Nothing else uses the key.
- [ ] Batch script; systemd oneshot unit; `start`.
- [ ] `tail -f` the log; stop at once on a repeated `error=api:`.
- [ ] Key scan, commit the run folders you keep, push.
- [ ] Stage E: fixed commit checked out; `stage_e.sh` with `--replan off`, no `--llm-cache`; report written.
