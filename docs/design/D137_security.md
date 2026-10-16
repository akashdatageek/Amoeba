# D137 — security: remote code execution from the pool, the harness's own fetches, local tools under a niche gate

Status: **built** (branch claude/audit-fixes). Audit Phase A, numbered D134 in the audit prompt; renumbered because
PR #42 had already used D134–D136.

## Why
- **Remote code execution from the pool.** A server that runs code for the caller could still be granted from the
  pool. SIDE_EFFECT (pool/stock.py) has no exec, run or code words, and the code_execution aliases score such
  servers higher. In the Sonnet probe (eval/manual/sonnet/REPORT.md), Box 4 picked
  `io.github.MichielDeRuiter/sandboxapi-mcp` ("Execute code in 8 languages … in gVisor sandboxes") for "Bash". It
  was stopped only because its connection failed.
- **The harness's own fetches.** `tools/web.py` http_get fetched any URL from the harness host, so a page or data
  link could make the harness read 169.254.169.254, localhost or a private network.
- **Local tools under a niche gate.** `config/niche.py` refused local:Write and local:Edit under
  `outside_actions: false`, because "write" and "edit" are side-effect words, even though local tools act only inside
  the run's workspace.

## What
1. **REMOTE_EXEC.** The words are: execute, execution, exec, run code, run python, eval, interpreter, sandbox, shell,
   terminal, notebook, jupyter, compile, container, vm. Names are split at `- _ . /`, and matches are whole words.
   - The check covers the server's name, title and description, and each tool the index lists.
   - It runs at vetting (`vet` → reason `remote_exec`) and again on the live tool listing after connecting.
   - It applies to grants, find_tool and Box 4 alike, since all of them go through `stock_toolbox`.
   - Each refusal logs `pool_refused_remote_exec` with the server, the stage (vet | connect) and the matched word.
   - `--allow-remote-exec` (`PoolSetup.allow_remote_exec`, default off) allows such servers. `remote_exec` is a
     fall-through reason (D127), so the next vetted candidate, usually local:Bash, gets the request.
2. **http_get.**
   - Only http and https.
   - The host is resolved with `socket.getaddrinfo`. Loopback, private, link-local, multicast, reserved,
     unspecified and non-global addresses are refused, for IPv4 and IPv6, and an IPv4-mapped IPv6 address is judged
     as its IPv4 address. `localhost` is refused by name.
   - Redirects are followed by hand, at most 3 hops, each checked again.
   - The error text is "refused: address not public".
3. **Niche gate.** `tool_allowed` skips the side-effect word test for `local:` and `made:` names. The profile's
   allow list still applies to them.

## As built (Oct 16)
- **Unresolvable hosts.** A host that does not resolve inside the harness is allowed only when a proxy is set for
  its scheme: the proxy then resolves it and reaches only the public internet. This container works that way. An IP
  literal or `localhost` is always judged locally. With no proxy, an unresolvable host is refused.
- **Rebinding.** DNS rebinding between the check and the connection is not closed; that would need pinning the
  resolved address in the connection. The redirect hops and literal addresses are closed.
- **Tavily fetches.** `fetch_url` through Tavily is fetched by Tavily, not by the harness, so it is not affected.
- **Tests that opted in.** Four existing tests used a remote code runner as their internet candidate to test
  ranking, fall-through and shared picks. Their fixture now opts in with `allow_remote_exec=True`. The paid-endpoint
  test now also shows that a non-paid code runner is refused as `remote_exec`.

## Tests
tests/test_security_d137.py covers:
- the word list;
- an "execute python" tool refused at vetting, and allowed with the flag;
- the real sandboxapi-mcp metadata refused;
- a connected server whose tool runs code refused (with its event);
- 127.0.0.1, 10.x, 192.168.x, 169.254.169.254, ::1, ::ffff:127.0.0.1, 0.0.0.0 and localhost refused;
- resolution to a private address refused and the scheme limited;
- a redirect to a private host refused, a public redirect followed, more than 3 hops refused;
- the calc profile allowing local:Write and local:Edit while still refusing outside actions.
