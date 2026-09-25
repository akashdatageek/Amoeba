"""The `amoeba` command (also `python -m amoeba`).

    amoeba pool refresh                  # build data/pool/ from the sources in amoeba/config/pool.yaml (no model call)
    amoeba pool refresh --only skill     # one kind only
    amoeba pool refresh --dir other/     # another cache folder
    amoeba pool status                   # what the cache holds
"""
from __future__ import annotations

import argparse
import sys

from amoeba.pool.index import load_index, load_pool_config, refresh


# box: pool_index
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="amoeba", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="group", required=True)
    pool = sub.add_parser("pool", help="the tool/skill pool of Box 3's toolbox step (D56)")
    cmd = pool.add_subparsers(dest="cmd", required=True)
    r = cmd.add_parser("refresh", help="fetch the pool index into the cache")
    r.add_argument("--dir", default=None, help="cache folder (default: cache_dir in pool.yaml)")
    r.add_argument("--only", choices=["tool", "skill"], default=None)
    s = cmd.add_parser("status", help="summarise the cache")
    s.add_argument("--dir", default=None)
    args = p.parse_args(argv)
    cfg = load_pool_config()
    folder = args.dir or cfg["cache_dir"]
    if args.cmd == "refresh":
        index = refresh(cfg, folder, only=args.only)
        kinds = {k: sum(e["kind"] == k for e in index["entries"]) for k in ("tool", "skill")}
        print(f"pool refresh: {kinds['tool']} tools, {kinds['skill']} skills in {folder}/index.json"
              + (f"; {len(index['errors'])} source(s) failed" if index["errors"] else ""))
        return 1 if index["errors"] and not index["entries"] else 0
    index = load_index(folder)
    if index is None:
        print(f"no pool cache in {folder}; run `python -m amoeba pool refresh`")
        return 1
    es = index["entries"]
    tools = [e for e in es if e["kind"] == "tool"]
    skills = [e for e in es if e["kind"] == "skill"]
    print(f"refreshed {index['refreshed_at']}: {len(tools)} tools ({sum(e['remote_url'].startswith('https://') for e in tools)}"
          f" with an HTTPS remote, {sum(bool(e['auth_required']) for e in tools)} needing a key), {len(skills)} skills "
          f"({sum(not e['has_scripts'] for e in skills)} instruction-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
