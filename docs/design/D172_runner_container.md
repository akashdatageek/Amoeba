# D172 — Box 4's scoped round must not fall back silently

Status: **built** (branch claude/zen-fermi-mnaurm, Oct 22). This fixes a review finding on D154/D163 (main @ 9f1fb29).

## Why
`probe.py::fallback_reason` turns a scoped round into the single rung whenever local tools run in the OpenShell
sandbox. There a probe's workspace files cannot be undone. The single rung has no INV/DOM comparison, no compose
(D165) and no control (D168), and it gives few verdicts to learn from. The run went on with only a `scoped_fallback`
event, so a learning run in the sandbox learned almost nothing, and nobody was told.

## What
1. **`probe.py::proposer_mode(adapt, proposer, local_tools, local_tools_mode)`** works out, from the flags, the mode
   Box 4 will actually get. It uses the same rule as `fallback_reason`:
   - `scoped`;
   - `single`, either asked for or a fallback, with the reason;
   - `none`, when adapt is off.
2. **Preflight** (D156) has a new row, `proposer mode`, with new flags `--proposer`, `--adapt` and `--local-tools`
   that mirror run_task's.
   - **`ok`** when the mode is scoped.
   - **`warn`** for a fallback. The row names it, and its fix points to the runner container.
   - **Why warn and not missing:** the hard stop is in run_task, and a fallback does not block a run that does not
     learn.
3. **run_task refuses learning from a fallback.**
   - **When.** A `--topology plan` run is refused if `--lessons-write` resolves to on (it is on by default with
     adapt on) and the scoped round would fall back.
   - **How to get past it.** The message names three ways: run inside the runner container, pass
     `--lessons-write off`, or pass `--allow-single-learning` to learn from single rounds anyway.
   - **What is not refused.** `--proposer single` is asked for, so it is not refused.
4. **`scripts/vm/`: a throwaway runner container.**
   - **`Dockerfile`**, built from the repository root. It holds the repository, `pip install -e ".[test,local]"`,
     the sandbox libraries (libs.txt: numpy, pandas, scipy, matplotlib, pillow, openpyxl, python-docx, python-pptx,
     pypdf, pytest), LibreOffice Calc and Writer, Node and Claude Code (whose `claude mcp serve` is the local-tool
     server). It sets `AMOEBA_SANDBOX=1` and runs as user 1000. No key is in the image.
   - **`run.sh <out-dir> "<command>"`** runs one command with `docker run --rm`. It mounts **one** host folder, the
     output folder, at `/out`. It passes the keys **by name** from the shell's environment
     (`-e CLAUDE_API_KEY -e GEMINI_API_KEY -e TAVILY_API_KEY -e OPENROUTER_API_KEY`), never as values. It refuses a
     command that turns local tools on without `--local-tools-mode inprocess`.
   - **Inside it,** the container is the sandbox. In-process local tools are undone file by file, so the scoped round
     runs in full.

## Found on the first preflight inside the container (Oct 22)
- **The profile's keys.** The preflight checked only `GEMINI_API_KEY` and `TAVILY_API_KEY`. It now also checks the
  key of the profile's team model and of its verifier. For claude-sonnet+gemma-verify that adds `CLAUDE_API_KEY`.
- **Behind a TLS-inspecting proxy** (as in a cloud session), the container had no route to the model APIs. `run.sh`
  has two opt-in settings for this:
  - `AMOEBA_RUNNER_CA=<ca file>` passes the proxy variables by name and mounts that one CA file read-only as the
    trust bundle;
  - `AMOEBA_RUNNER_NETWORK=host` is needed only when the proxy listens on the host's loopback.

  On a VM with direct network access, leave both unset.

## Tests (tests/test_runner_vm_d172.py, red on 9f1fb29)
- **`proposer_mode`.** Sandbox gives single with the reason. In-process or local tools off gives scoped. Asking for
  single gives single, and adapt off gives none.
- **Preflight.** The row warns "single: falls back …" in sandbox mode and points to scripts/vm. It is ok and
  "scoped …" in in-process mode.
- **The refusal.** run_task refuses the default learning run in sandbox mode, and the message names
  `--allow-single-learning`. It is accepted with that flag, with `--lessons-write off`, or in-process with
  `AMOEBA_SANDBOX=1`.
- **The runner files.** The Dockerfile has LibreOffice, scipy, pytest, `AMOEBA_SANDBOX=1` and `pip install -e`.
  run.sh has exactly one mount, ending at `/out`, passes the keys by name, writes no key value, and runs in-process
  with `--rm`.

On 9f1fb29, the same flags were accepted with `lessons_write = on` (red evidence in the PR).

## Found in Part 2, Step 1 (Oct 22, second session)
- **git behind the proxy.** `pool refresh` clones `anthropics/skills` with git, which does not read `SSL_CERT_FILE`,
  so the clone failed and the pool had no skills (preflight: `skill xlsx … missing`). With `AMOEBA_RUNNER_CA`,
  `run.sh` now also sets `GIT_SSL_CAINFO`, `CURL_CA_BUNDLE` and `NODE_EXTRA_CA_CERTS` to the same file.
- **The pool cache lives in the output folder.** The image holds no `data/pool`; build it once with
  `run.sh <out> "python -m amoeba pool refresh --dir /out/pool"` and pass `--pool-dir /out/pool` to preflight and
  run_task. `--only skill` rewrites the index with skills only, so refresh both kinds together.
- **Image build behind the proxy:** `docker build --network host --secret id=ca,src=<ca.crt>
  --build-arg BASE_REGISTRY=mirror.gcr.io/library` (Docker Hub answered 429 to anonymous pulls).
