# Running Amoeba on a VM

This page says how to run the benchmark on a persistent Linux VM: the practice/gate loop (`scripts.run_loop`),
experiments (`scripts.run_experiment`), single tasks (`scripts.run_task`) and the probe tasks.

Why a VM. In one day the cloud session restarted its container five times or more. Each restart killed the
detached runs. The HTTPS proxy port also changed once. Runs started before the change kept the old address and
ended with `api: APIConnectionError`. A VM with a service manager and direct network access avoids both.

## 1. The machine

- **Size.** 8 vCPU, 16 GB RAM, 60 GB SSD. The loop runs 4 runs at once (`--parallel 4`). Each run is one Python
  process. With local tools on, each run also gets its own sandbox (1 CPU and 1 GiB each,
  `amoeba/config/localtools.yaml` `sandbox`). The cloud session had 4 CPUs and 15 GB; that is the minimum.
- **OS.** Ubuntu 24.04 LTS (any Linux with Landlock works). The sandbox needs Landlock as a hard requirement.
  Check: `cat /sys/kernel/security/lsm` must list `landlock`.
- **Python** 3.11 or newer (`requires-python = ">=3.11"` in `pyproject.toml`).
- **Docker** with Compose and BuildKit, only if you run with `--local-tools on` (the probes do; the loop does not):
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
- Do not set `AMOEBA_API_KEY`, `AMOEBA_BASE_URL` or `AMOEBA_MODEL` in it. They override the profile.
  `run_loop` and `run_experiment` drop them; for `run_task` unset them yourself.
- Do not put `GIT_*`, `GH_*`, `GITHUB_*`, cloud or SSH-agent variables in it. `--env-file` refuses such a file (D95).
- `run_loop` and `run_experiment` read it with `--env-file` and never print it. They pass the keys to their own
  `run_task` children with every cloud and git variable removed. `run_task` has no `--env-file`; load the file
  into its environment (`set -a; . ~/work/keys.env; set +a`), as the probe script below does.
- **Agents never see the keys.** Every command an agent runs executes in the OpenShell sandbox with `LANG` as its
  only variable, no network, and no view of the repo, `eval/` or env files (`amoeba/localtools/sandbox.py`).
- **Evidence branch credentials stay in the harness.** Shipping (`git push origin` to `evidence`) runs in the
  `run_loop` / `run_experiment` process only. Give the `amoeba` user a GitHub deploy key with write access in
  `~/.ssh` (a key file in `~/.ssh/config`, not an SSH agent: services have none) and an SSH `origin` URL.
- **Key scan before every commit.** Stage, then run (exit 1 and the file names on a hit):

```bash
git diff --cached --name-only -z | python -c 'import sys; from pathlib import Path; from amoeba.adapt.evidence import key_scan, secret_values; from scripts.run_experiment import load_env; s = secret_values(load_env(sys.argv[1:])); h = [x for f in sys.stdin.read().split("\0") if f and Path(f).is_file() for x in key_scan(Path(f), s)]; print("\n".join(h) or "clean"); sys.exit(1 if h else 0)' ~/work/keys.env
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
  The web tools do not re-read it; restart the service after a proxy change anyway
  (`sudo systemctl restart amoeba-chain`; the work resumes, section 5). A run that still ends in an infrastructure
  error gets `status: infra_error` in result.json, is run again up to `infra.retries` (2) times
  (`amoeba/config/adapt.yaml`) and is never scored. On a VM with a fixed proxy or none, leave `AMOEBA_PROXY_FILE` unset.

## 5. Running long jobs

Run every long job as a **systemd service**. tmux also works, but nothing restarts it after a crash or reboot.

**Nobody answers questions in a service (D116).** `run_task` asks you about a name or term with close readings
before it plans. Under systemd there is no terminal, so such a run stops with status `needs_clarification` and
writes `clarification.json`. The experiment, loop and audit scripts already pass `--ask-assumed off`. For a
benchmark or a single task run as a service, either answer ahead of time with `--clarify 'TERM=READING'` or pass
`--ask-assumed off` (the answer then states its assumption).

**The chain script**, `~/work/m2_chain.sh` (`chmod 700`). This is the command line the cloud session ran, with paths
for the VM:

```bash
#!/bin/bash
# M-P2: calibration on the gate set -> pre-registered check -> loop. Rerun-safe: each step skips finished work.
W=$HOME/work
[ -f "$W/m2.done" ] && { echo "m2 already done"; exit 0; }
cd "$HOME/Amoeba" && . .venv/bin/activate
M="--env-file $W/keys.env --llm openai --profile gemma-api --timezone America/Chicago --llm-cache runs/cache --llm-cache-mode record --min-seconds-between-calls 1 --max-rate-retries 8"
echo "== calibration $(date -u +%FT%TZ)"
python -m scripts.run_experiment --stream m2 --family calc --calibrate-only --parallel 4 $M || { echo "calibration rc=$?"; exit 1; }
echo "== check $(date -u +%FT%TZ)"
python -m scripts.run_experiment --stream m2 --family calc --edit eval/loop/m2/hypotheses/check-assumptions.yaml --check --parallel 4 $M || { echo "check rc=$?"; exit 1; }
echo "== loop $(date -u +%FT%TZ)"
python -m scripts.run_loop --stream m2 --parallel 4 --parallel-until 8 $M || { echo "loop rc=$?"; exit 1; }
touch "$W/m2.done"; echo "== done $(date -u +%FT%TZ)"
```

The `m2.done` marker stops a reboot from starting a finished chain again. `--min-seconds-between-calls` only acts
with `--routing fixed` or `role`. The loop's runs use `--topology plan`, which is routed by default; there a shared
per-model bucket spaces the calls (15 requests per minute for Gemma, `amoeba/config/models.yaml`).

**The unit**, `/etc/systemd/system/amoeba-chain.service`:

```ini
[Unit]
Description=Amoeba M-P2 chain
After=network-online.target docker.service
Wants=network-online.target
StartLimitIntervalSec=6h
StartLimitBurst=5

[Service]
User=amoeba
WorkingDirectory=/home/amoeba/Amoeba
ExecStart=/home/amoeba/work/m2_chain.sh
Restart=on-failure
RestartSec=300
Environment=PYTHONUNBUFFERED=1
# only with a proxy:
# Environment=HTTPS_PROXY=http://proxy:3128 HTTP_PROXY=http://proxy:3128 NO_PROXY=127.0.0.1,localhost
StandardOutput=append:/home/amoeba/work/logs/m2_chain.log
StandardError=append:/home/amoeba/work/logs/m2_chain.log

[Install]
WantedBy=multi-user.target
```

No `EnvironmentFile=` is needed: the script passes `--env-file`. Run `mkdir -p ~/work/logs`, then `sudo systemctl
daemon-reload && sudo systemctl enable --now amoeba-chain`. Stopping the service stops every child. `StartLimitBurst`
keeps a chain that always fails (a config error) from looping all day.

**Resume after a crash or reboot: run the same command again** (the service does this for you). What is reused:

- **Every run folder with a finished `result.json`** is not run again (D73). A run with `status: infra_error` (an
  `api:` connection, timeout, proxy, 429 or 5xx error, a `cache_miss`, no result) does not count as finished and is
  run again (D111).
- **A run killed half-way** starts again with the same `--llm-cache` folder and cache namespace. Every model call it
  had finished replays from the cache for free. Local tool commands run again, since they change files.
- **Calibration** is skipped when `ledger.jsonl` holds its row. **The check** and any **hypothesis** with a decision
  row in the ledger are not run again. The Architect's proposals replay from their own cache namespace.
- **The loop** reads `eval/loop/<stream>/loop_state.json` (practice orders already handled, unshipped evidence) and
  `practice.jsonl` (practice runs done). It goes on from the first order not handled.
- Without `runs/cache` resume still works, but in-flight runs pay their calls again.

**Rules.**

- **One writer per stream.** Never run the same stream from two checkouts (cloud and VM, or two VMs). The state
  files and the evidence chain would fork. To move a stream: stop it, commit and push `eval/loop/<stream>/`, pull on
  the VM, copy `runs/cache/`, then start.
- **One chain per key at a time.** The key's limits (15 requests per minute, 1,500 per day for Gemma) are shared by
  everything that uses it. The shared bucket covers the processes of one user on one machine only
  (`~/.cache/amoeba/rate`, or `AMOEBA_RATE_DIR`). It knows nothing of other machines, and the daily limit is not
  enforced. Stop the cloud session's runs before you start on the VM.
- **Probes go one at a time,** and not next to a chain on the same key. In the cloud session the probes shared the
  key with four loop runs and got 429s (4 to 10 retries per probe).

**A probe** (one task, local tools in the sandbox, web tools). The probe flags as the cloud session ran them:

```bash
cd ~/Amoeba && . .venv/bin/activate
set -a; . ~/work/keys.env; set +a; unset AMOEBA_MODEL AMOEBA_BASE_URL AMOEBA_API_KEY
grep '"probe-h1-freight"' tasks/probe_hard.jsonl > ~/work/probe_task.jsonl
python -m scripts.run_task --tasks ~/work/probe_task.jsonl --topology plan --llm openai --routing routed --niche general \
  --local-tools on --local-tools-mode sandbox --web-tools --replan on --timezone America/Chicago \
  --draft-prompts d24 --runs-dir eval/probe_hard/runs --max-rate-retries 8 >> ~/work/logs/probe.log 2>&1
```

Run it as a oneshot service or in tmux. `run_task` does not ship to the evidence branch. The cloud session shipped
probe runs with a small harness script (not in the repo yet) that calls `EvidenceLog`, `make_shipper` and
`run_finished` from `amoeba/adapt/evidence.py`, then `flush(force=True)`. Add it as a script before you rely on it.
A killed sandbox run can leave a container behind: check `docker ps --filter label=openshell`.

## 6. Monitoring

Use `tail -f ~/work/logs/m2_chain.log`, `systemctl status amoeba-chain` and `grep -n 'error=api:' ~/work/logs/m2_chain.log`.

What the lines mean:

- `== calibration …`, `== check …`, `== loop …`, `== done …`: the chain's own step marks. `rc=` means a step failed.
- `[A] <task> k<n> score=… tokens=… error=… <s>s` and `[B] …`: one experiment or calibration run of arm A or B
  finished. `[P] …`: one practice run finished. `(retry n of 2 after an infra error)` means an earlier try ended in an
  infrastructure error and it was run again; `status=infra_error` means this try did too (D111).
- `[practice] #<order> <task> v<recipe> score=… failed=[…] error=…`: the loop recorded a practice run.
- `[alarm] #<order> <kind>: <before> -> <after>`: the Monitor saw a drop. `[diagnosis]` names the cause and the
  allowed edits. `[architect] <id>: <edit> … predicted +0.10` is a proposal. `[gate] <id>: accept|reject …` is the
  decision. `[unresolved]` means three proposals failed; the alarm waits in `human_queue.jsonl`.
- `[ship] all shipped` or `[ship] N item(s) unshipped: …`: the evidence push at the end of `run_experiment`.

**On `error=api:`.** Such a run is an infrastructure error (D111). It is run again, at most twice. If it still
fails, its pair is left out of the experiment (`experiment.json` `excluded`), and a practice line ends
`status=infra_error (not scored)`; the Monitor and the Gate never count it. Several of these in a row mean the
network, proxy, key or quota is broken: stop the service (`sudo systemctl stop amoeba-chain`), fix the cause, start
it again. Never edit `events.jsonl`, the ledger or run folders to hide them. `error=api: … 429` lines mean the key is
shared or over quota (see the rules above).

**Disk.** `du -sh runs/cache eval/loop/* eval/probe_hard/runs; docker system df; df -h ~`. After one day in the
cloud, `runs/cache` held about 135 MB and `eval/loop/m2` about 91 MB. The sandbox and gateway images take a few GB.

## 7. Getting results back

- **Commit the stream's folder** on the code branch: `git add eval/loop/m2 eval/probe_hard`, run the key scan
  (section 3), then commit. `eval/loop/*/jobs/` and `runs/` (with the cache) are not committed.
- **The evidence branch.** `run_loop` ships each finished run (after the key scan) and the new event rows to the
  `evidence` branch at most every 10 minutes, and once more at the end (`amoeba/config/adapt.yaml` `evidence`). It
  uses a worktree of that branch at `../amoeba-evidence`, made if missing. What is not shipped yet is in
  `loop_state.json` (`unshipped`, `ship_blocked`). Check the chain:
  `python -m scripts.verify_evidence --stream m2` and `python -m scripts.verify_evidence --branch evidence`.
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
- [ ] The stream stopped everywhere else. Nothing else uses the key.
- [ ] Chain script with a done marker; systemd unit with `Restart=on-failure`; `enable --now`.
- [ ] `tail -f` the log; stop at once on a repeated `error=api:`.
- [ ] Key scan, commit `eval/loop/<stream>/`, verify the evidence branch, push.
