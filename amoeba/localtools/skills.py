"""D59 — local skills: Claude Code's skill folders and the anthropics/skills clone kept by `pool refresh`.

A skill is attached by copying its whole folder into the run's workspace (skills/<name>/) and putting the SKILL.md
frontmatter plus the first `max_skill_chars` characters of its body on the helper's role card. Scripts inside the
folder are allowed here (unlike the D56 pool without local tools): they can only run through local:Bash, in the
workspace, behind the gate.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from amoeba.pool.index import split_skill


# box: localtools
def skill_roots(config: dict, pool_dir: Path) -> list[tuple[str, Path]]:
    """(label, folder) for every place skills are listed from, in order: Claude Code's, then the kept clones."""
    roots = [(r["label"], Path(r["path"]).expanduser()) for r in config.get("skill_roots") or []]
    clones = Path(pool_dir) / (config.get("repo_skills") or "repos")
    if clones.is_dir():
        roots += [(d.name, d) for d in sorted(clones.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    return roots


# box: localtools
def list_skills(config: dict, pool_dir: Path) -> list[dict]:
    """One entry per <root>/**/<name>/SKILL.md: {id, name, title, description, kind skill, source local, root, path,
    has_scripts}. Hidden folders are skipped. A skill found under two roots is listed twice (ids differ by root)."""
    out = []
    for label, root in skill_roots(config, pool_dir):
        if not root.is_dir():
            continue
        for md in sorted(root.rglob("SKILL.md")):
            base = md.parent
            if any(part.startswith(".") for part in base.relative_to(root).parts):
                continue
            try:
                front, _ = split_skill(md.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            files = [f for f in base.rglob("*") if f.is_file()]
            out.append({"id": f"local:skill:{label}/{base.name}", "name": base.name, "title": str(front.get("name") or ""),
                        "description": " ".join(str(front.get("description") or "").split()), "kind": "skill",
                        "source": "local", "root": label, "root_path": str(root), "path": str(base),
                        "has_scripts": any(f.suffix in (".py", ".sh", ".js") or "scripts" in f.relative_to(base).parts[:-1]
                                           for f in files)})
    return out


# box: localtools
def skill_root_path(entry: dict) -> Path | None:
    """D103: the folder of the root a skill entry was listed from. `root` is the root's label (the clone's folder
    name, e.g. anthropics_skills), not a path: an entry made before D103 has no `root_path`, so the label is found
    among the skill path's parents."""
    if entry.get("root_path"):
        return Path(entry["root_path"])
    path = Path(entry.get("path") or "")
    return next((p for p in path.parents if p.name == entry.get("root")), None)


# box: localtools
def sandbox_skill_path(entry: dict, image_root: str = "/opt/skills", baked: str = "anthropics_skills") -> Path | None:
    """D103: where a skill sits in the sandbox image (the `baked` clone is copied to `image_root`), or None when the
    image does not hold it."""
    root = skill_root_path(entry)
    if entry.get("root") != baked or root is None:
        return None
    try:
        return Path(image_root) / Path(entry["path"]).resolve().relative_to(root.resolve())
    except ValueError:
        return None


# box: localtools
def card_text(entry: dict, max_chars: int) -> str | None:
    """The SKILL.md frontmatter and the first max_chars of its body, or None when it cannot be read."""
    try:
        text = (Path(entry["path"]) / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.match(r"^(---\s*\n.*?\n---\s*\n?)(.*)$", text, re.S)
    front, body = (m.group(1), m.group(2)) if m else ("", text)
    cut = body.strip()[:max_chars]
    more = f"\n[… first {max_chars} of {len(body.strip())} characters]" if len(body.strip()) > max_chars else ""
    return f"{front.strip()}\n{cut}{more}".strip()


# box: localtools
def copy_skill(entry: dict, workspace: Path) -> Path:
    """Copy the skill's folder to <workspace>/skills/<name>/ (symlinks are left out: nothing points outside)."""
    dest = workspace / "skills" / entry["name"]
    src = Path(entry["path"])

    def links(folder, names):
        return [n for n in names if (Path(folder) / n).is_symlink()]
    shutil.copytree(src, dest, ignore=links, dirs_exist_ok=True)
    return dest
