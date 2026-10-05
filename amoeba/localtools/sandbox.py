"""D96 — agents' local tools run out of the harness process, in a fresh NVIDIA OpenShell sandbox per run.

The local-tool server (`claude mcp serve`) and every command it runs execute inside an OpenShell sandbox (docker compute
driver; gateway config and image in amoeba/config/sandbox/). The harness talks to the server through `bridge`, a small
relay process that pipes the MCP stdio over OpenShell's interactive exec stream; the server itself never runs on the
harness host.

Policy (deny by default; amoeba/config/localtools.yaml `sandbox`), fixed when the sandbox is created and held by the
gateway, never by the agent:
  - network: none. The workload container runs with network=none and the policy names no egress endpoint;
  - filesystem (Landlock, hard requirement): only the sandbox's own home (/sandbox, holding the workspace
    /sandbox/workspace), /tmp and /dev/null are writable; system directories and /opt/skills are read-only; nothing else
    is visible. The harness code, eval/, events.jsonl, the ledger, recipes, .git and env files are never mounted;
  - process: runs as the unprivileged `sandbox` user, no capabilities, no-new-privileges, seccomp;
  - no secrets: the environment is LANG and nothing else (no API keys, git or cloud credentials, SSH agent);
  - skills (/opt/skills) and Claude Code's managed settings (all hooks off) are baked into the image, root-owned and
    read-only; gate.py also refuses writes to .claude/, .mcp.json, CLAUDE.md and skills/ paths;
  - limits: CPU and memory per sandbox, the gateway's process cap, a timeout per call and per run; one sandbox per run,
    deleted at the end of the run.
Files the team makes are copied from /sandbox/workspace to runs/<id>/workspace after every call (the harness reads
only that copy). Every allow and deny decision (gate.py and the sandbox's own log) is recorded in the run's trace;
the loop harness copies them into events.jsonl when the run finishes (evidence.tool_decisions).
"""
from __future__ import annotations

import base64
import io
import os
import queue
import sys
import tarfile
import threading
import time
from pathlib import Path

SANDBOX_WORKSPACE = "/sandbox/workspace"


# box: localtools
def sandbox_config(config: dict) -> dict:
    """The `sandbox` section of localtools.yaml with its defaults."""
    s = dict(config.get("sandbox") or {})
    s.setdefault("isolation", "process")
    s.setdefault("endpoint", "127.0.0.1:17680")
    s.setdefault("image", "amoeba-sandbox:local")
    s.setdefault("read_only", ["/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/opt/skills", "/proc",
                               "/dev/urandom"])
    s.setdefault("read_write", ["/sandbox", "/tmp", "/dev/null"])
    s.setdefault("cpu", "1")
    s.setdefault("memory", "1Gi")
    s.setdefault("run_timeout_s", 3600)
    return s


# box: localtools
class OpenShellBox:
    """One OpenShell sandbox for one run: created with the fixed policy, used for the harness's own file copies, and
    deleted at the end. `record(event, data)` receives every decision for the run's trace."""

    def __init__(self, cfg: dict, run_name: str, record=None):
        from openshell.sandbox import SandboxClient
        self.cfg = cfg
        import hashlib
        self.name = "am-" + hashlib.sha1(run_name.encode()).hexdigest()[:14]   # OpenShell names: at most 19 chars
        self.record = record or (lambda event, data: None)
        self.client = SandboxClient(cfg["endpoint"], timeout=120)
        self.created = 0.0

    def spec(self):
        from google.protobuf import struct_pb2
        from openshell._proto import openshell_pb2, sandbox_pb2
        policy = sandbox_pb2.SandboxPolicy(
            version=1,
            filesystem=sandbox_pb2.FilesystemPolicy(include_workdir=False, read_only=list(self.cfg["read_only"]),
                                                    read_write=list(self.cfg["read_write"])),
            landlock=sandbox_pb2.LandlockPolicy(compatibility="hard_requirement"),
            process=sandbox_pb2.ProcessPolicy(run_as_user="sandbox", run_as_group="sandbox"))
        res = struct_pb2.Struct()
        res.update({"limits": {"cpu": str(self.cfg["cpu"]), "memory": str(self.cfg["memory"])}})
        return openshell_pb2.SandboxSpec(
            template=openshell_pb2.SandboxTemplate(image=self.cfg["image"], resources=res),
            policy=policy, environment={"LANG": "C.UTF-8"})

    def create(self) -> None:
        try:
            self.client.create(workspace="default", name=self.name, spec=self.spec())
        except Exception as e:                        # a stale sandbox of a crashed earlier attempt: never reused
            if "already exists" not in str(e):
                raise
            self.client.delete(self.name, workspace="default")
            self.client.wait_deleted(self.name, workspace="default")
            self.record("sandbox_replaced_stale", {"amoeba.sandbox": self.name})
            self.client.create(workspace="default", name=self.name, spec=self.spec())
        self.client.wait_ready(self.name, workspace="default")
        self.created = time.time()
        self.exec(["mkdir", "-p", SANDBOX_WORKSPACE])
        self.record("sandbox_created", {"amoeba.sandbox": self.name, "amoeba.image": self.cfg["image"],
                                        "amoeba.read_write": list(self.cfg["read_write"]),
                                        "amoeba.read_only": list(self.cfg["read_only"]), "amoeba.network": "none",
                                        "amoeba.cpu": self.cfg["cpu"], "amoeba.memory": self.cfg["memory"]})

    def exec(self, command: list[str], stdin: bytes | None = None, timeout_s: int = 60):
        return self.client.exec(self.name, command, workspace="default", stdin=stdin, timeout_seconds=timeout_s)

    def expired(self) -> bool:
        return bool(self.created) and time.time() - self.created > float(self.cfg["run_timeout_s"])

    def pull(self, dest: Path) -> list[str]:
        """Copy /sandbox/workspace to `dest` (regular files and folders only; nothing outside dest)."""
        r = self.exec(["bash", "-c", f"cd {SANDBOX_WORKSPACE} && tar -cf - --exclude=./skills --exclude=./sources . "
                                     f"| base64 -w0"],                          # D107: inputs are not copied back
                      timeout_s=60)
        if r.exit_code != 0:
            return []
        raw = base64.b64decode(r.stdout.strip() or b"")
        out = []
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            members = [m for m in tf.getmembers() if m.isfile() or m.isdir()]
            tf.extractall(dest, members=members, filter="data")
            out = [m.name for m in members if m.isfile()]
        return out

    def logs(self) -> list[dict]:
        """The sandbox's own log lines that record a decision (denials and policy events)."""
        from openshell._proto import openshell_pb2
        from openshell.sandbox import _workspace_scope
        try:
            resp = self.client._stub.GetSandboxLogs(openshell_pb2.GetSandboxLogsRequest(
                workspace_scope=_workspace_scope("default"), sandbox=self.name, lines=2000), timeout=30)
        except Exception as e:                        # logs are evidence, never a reason to fail the run
            return [{"level": "ERROR", "message": f"logs unavailable: {type(e).__name__}"}]
        keep = []
        for line in resp.logs:
            text = f"{line.message} {dict(line.fields)}".lower()
            if any(w in text for w in ("deny", "denied", "block", "policy", "landlock", "violation", "refus")):
                keep.append({"level": line.level, "source": line.source, "target": line.target,
                             "message": line.message[:300], "fields": dict(line.fields)})
        return keep

    def delete(self) -> None:
        try:
            self.client.delete(self.name, workspace="default")
            self.record("sandbox_deleted", {"amoeba.sandbox": self.name})
        except Exception as e:
            self.record("sandbox_delete_failed", {"amoeba.sandbox": self.name, "amoeba.error": str(e)[:200]})


# ---- the stdio relay: python -m amoeba.localtools.sandbox bridge <sandbox> [--workdir W] [--endpoint E] -- cmd... ----
# box: localtools
def bridge(sandbox: str, command: list[str], workdir: str = SANDBOX_WORKSPACE, endpoint: str = "127.0.0.1:17680") -> int:
    """Relay this process's stdin/stdout to `command` run inside the sandbox (OpenShell interactive exec)."""
    import grpc
    from openshell._proto import openshell_pb2, openshell_pb2_grpc
    from openshell.sandbox import _workspace_scope
    stub = openshell_pb2_grpc.OpenShellStub(grpc.insecure_channel(endpoint))
    q: queue.Queue = queue.Queue()

    def read_stdin():
        while True:
            data = os.read(0, 65536)
            if not data:
                q.put(None)
                return
            q.put(data)
    threading.Thread(target=read_stdin, daemon=True).start()

    def requests():
        yield openshell_pb2.ExecSandboxInput(start=openshell_pb2.ExecSandboxRequest(
            workspace_scope=_workspace_scope("default"), sandbox=sandbox, command=command, workdir=workdir,
            environment={"LANG": "C.UTF-8", "HOME": "/sandbox/home", "DISABLE_AUTOUPDATER": "1",
                         "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}, no_login_shell=True))
        while True:
            data = q.get()
            if data is None:
                return
            yield openshell_pb2.ExecSandboxInput(stdin=data)
    code = 1
    for event in stub.ExecSandboxInteractive(requests()):
        kind = event.WhichOneof("payload")
        if kind == "stdout":
            os.write(1, bytes(event.stdout.data))
        elif kind == "stderr":
            os.write(2, bytes(event.stderr.data))
        elif kind == "exit":
            code = int(event.exit.exit_code)
    return code


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] != "bridge" or "--" not in a:
        sys.exit("usage: python -m amoeba.localtools.sandbox bridge <sandbox> [--workdir W] [--endpoint E] -- cmd ...")
    head, cmd = a[1:a.index("--")], a[a.index("--") + 1:]
    opts = {head[i]: head[i + 1] for i in range(1, len(head) - 1, 2)}
    sys.exit(bridge(head[0], cmd, opts.get("--workdir", SANDBOX_WORKSPACE), opts.get("--endpoint", "127.0.0.1:17680")))
