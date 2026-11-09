#!/usr/bin/env python3
"""
Package the skills in this repo for every platform that supports Agent Skills.

    python3 scripts/package.py [--dev] [skill-name ...]     (no names = all skills)

For each skill it writes two byte-identical archives with the skill folder at the root:
    dist/<name>.skill   Claude (claude.ai, Claude Desktop)
    dist/<name>.zip     ChatGPT and other Agent Skills platforms

--dev builds a separately installable test copy instead: dist/<name>-dev.skill/.zip, with
name <name>-dev and a description that starts "DEV/TESTING version of <name>". The rename
happens only in the package, never in the committed SKILL.md.

Before packaging, each skill must pass the shared checks:
  - frontmatter has only `name` and `description`; name lowercase-hyphenated (max 64)
  - description max 1024 characters and ends with "Skill version: YYYY-MM-DD-N"
  - a "Version:" line in the body, if present, matches that version
  - portability: no Claude-only tool names, no cwd-relative "python scripts/" calls, and no
    /mnt/ paths outside SKILL.md's "## Output, validation and delivery" section
  - agents/openai.yaml (ChatGPT icon, name, colour), if present: short_description 25-64
    characters, brand colour #RRGGBB, icon file present and an SVG
Standard library only.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VERSION_AT_END = re.compile(r"Skill version: (\d{4}-\d{2}-\d{2}-\d+)$")
BODY_VERSION = re.compile(r"^Version:\s*(\S+)\s*$", re.MULTILINE)
PLATFORM_SECTION = "## Output, validation and delivery"
FORBIDDEN = [
    (re.compile(r"present_files"), "Claude-only tool name 'present_files'"),
    (re.compile(r"python3? scripts/"), "cwd-relative 'python scripts/' call (use <skill-root>/scripts/)"),
    (re.compile(r"/mnt/"), "hardcoded /mnt/ path (allowed only in SKILL.md's platform section)"),
]
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".sh"}
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc"}


def fail(skill: str, problems: list[str]) -> None:
    raise SystemExit(f"error: {skill}:\n  - " + "\n  - ".join(problems))


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with '---' frontmatter")
    end = text.index("\n---", 4)
    return text[4:end], text[end + 4:]


def read_frontmatter(fm: str) -> dict[str, str]:
    """name/description as single-line (quoted or plain) or folded (>-, >, |) values."""
    out: dict[str, str] = {}
    lines = fm.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in (">-", ">", "|", "|-"):
            block = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            value = " ".join(b for b in block if b)
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].replace('\\"', '"') if value[0] == '"' else value[1:-1].replace("''", "'")
        out[key] = value
    return out


def check(skill_dir: Path) -> str:
    """Runs the shared checks; returns the skill version."""
    name = skill_dir.name
    problems: list[str] = []
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    try:
        fm_text, body = split_frontmatter(text)
    except ValueError as e:
        fail(name, [str(e)])
    fm = read_frontmatter(fm_text)
    extra = set(fm) - {"name", "description"}
    if extra:
        problems.append(f"frontmatter keys other platforms don't share: {sorted(extra)}")
    if fm.get("name") != name:
        problems.append(f"name '{fm.get('name')}' must equal the folder name '{name}'")
    if not NAME_RE.match(name) or len(name) > 64:
        problems.append("name must be lowercase with hyphens, max 64 characters")
    desc = fm.get("description", "")
    if not desc or len(desc) > 1024:
        problems.append(f"description must be 1-1024 characters (is {len(desc)})")
    m = VERSION_AT_END.search(desc)
    version = m.group(1) if m else ""
    if not m:
        problems.append("description must end with 'Skill version: YYYY-MM-DD-N'")
    bv = BODY_VERSION.search(body)
    if bv and bv.group(1) != version:
        problems.append(f"'Version: {bv.group(1)}' in the body differs from the description's {version}")

    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or excluded(path.relative_to(skill_dir)):
            continue
        rel = path.relative_to(skill_dir).as_posix()
        content = path.read_text(encoding="utf-8")
        if rel == "SKILL.md":
            i = content.find(PLATFORM_SECTION)
            if i >= 0:
                j = content.find("\n## ", i + len(PLATFORM_SECTION))
                content = content[:i] + "\n" * content[i:j if j >= 0 else None].count("\n") + (content[j:] if j >= 0 else "")
        if rel == "scripts/validate.py":
            # the validator may print its own usage line
            content = re.sub(r"Usage: python validate\.py", "", content)
        for n, line in enumerate(content.splitlines(), 1):
            for rx, why in FORBIDDEN:
                if rx.search(line):
                    problems.append(f"{rel}:{n}: {why}")

    openai = skill_dir / "agents" / "openai.yaml"
    if openai.exists():
        y = openai.read_text(encoding="utf-8")
        get = lambda k: (re.search(rf'^\s*{k}:\s*"?([^"\n]*)"?\s*$', y, re.MULTILINE) or [None, None])[1]  # noqa: E731
        sd = get("short_description") or ""
        if not 25 <= len(sd) <= 64:
            problems.append("agents/openai.yaml: short_description must be 25-64 characters")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", get("brand_color") or ""):
            problems.append("agents/openai.yaml: brand_color must be #RRGGBB")
        for k in ("icon_small", "icon_large"):
            icon = get(k)
            p = skill_dir / icon if icon else None
            if not p or not p.is_file():
                problems.append(f"agents/openai.yaml: {k} file not found in the skill")
            elif not p.read_text(encoding="utf-8").lstrip().startswith("<svg"):
                problems.append(f"agents/openai.yaml: {k} is not an SVG")
    if problems:
        fail(name, problems)
    return version


def excluded(rel: Path) -> bool:
    return (any(p in EXCLUDE_DIRS for p in rel.parts) or rel.name in EXCLUDE_FILES
            or rel.suffix in EXCLUDE_SUFFIXES)


def make_dev_copy(skill_dir: Path, stage: Path) -> Path:
    name = skill_dir.name
    dev = stage / f"{name}-dev"
    shutil.copytree(skill_dir, dev, ignore=shutil.ignore_patterns(*EXCLUDE_DIRS, *EXCLUDE_FILES, "*.pyc"))
    text = (dev / "SKILL.md").read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(text)
    desc = read_frontmatter(fm_text)["description"]
    prefix = (f"DEV/TESTING version of {name}. Use ONLY when the user explicitly asks for the dev or "
              f"test version ('dev', 'use the dev skill'); for normal work use {name}. Same capabilities: ")
    new_desc = prefix + desc[0].lower() + desc[1:]
    if len(new_desc) > 1024:
        # keep the version at the end; shorten the copied description
        tail = desc[VERSION_AT_END.search(desc).start():]
        room = 1024 - len(prefix) - len(tail) - 2
        new_desc = prefix + (desc[0].lower() + desc[1:])[:room].rsplit(" ", 1)[0] + "… " + tail
    q = '"' + new_desc.replace("\\", "\\\\").replace('"', '\\"') + '"'
    fm = f'name: "{name}-dev"\ndescription: {q}\n'
    body = body.replace(f'"({name}, version', f'"({name}-dev, version')
    (dev / "SKILL.md").write_text(f"---\n{fm}---{body}", encoding="utf-8")
    openai = dev / "agents" / "openai.yaml"
    if openai.exists():
        y = openai.read_text(encoding="utf-8")
        y = re.sub(r'^(\s*display_name:\s*)"?([^"\n]*)"?', lambda m: f'{m.group(1)}"{m.group(2)} (DEV)"', y,
                   count=1, flags=re.MULTILINE)
        openai.write_text(y, encoding="utf-8")
    return dev


def build(skill_dir: Path, archive_name: str) -> tuple[Path, Path]:
    DIST.mkdir(exist_ok=True)
    skill_file, zip_file = DIST / f"{archive_name}.skill", DIST / f"{archive_name}.zip"
    for f in (skill_file, zip_file):
        f.unlink(missing_ok=True)
    with zipfile.ZipFile(skill_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            rel = path.relative_to(skill_dir)
            if path.is_file() and not excluded(rel):
                zf.write(path, Path(archive_name) / rel)
    shutil.copyfile(skill_file, zip_file)
    return skill_file, zip_file


def main() -> int:
    args = sys.argv[1:]
    dev = "--dev" in args
    names = [a for a in args if a != "--dev"]
    skills = sorted(p.parent for p in ROOT.rglob("SKILL.md")
                    if DIST not in p.parents and ".git" not in p.parts)
    if names:
        unknown = set(names) - {s.name for s in skills}
        if unknown:
            raise SystemExit(f"error: no skill named {', '.join(sorted(unknown))}")
        skills = [s for s in skills if s.name in names]
    for skill_dir in skills:
        version = check(skill_dir)
        if dev:
            with tempfile.TemporaryDirectory() as tmp:
                dev_dir = make_dev_copy(skill_dir, Path(tmp))
                check(dev_dir)
                files = build(dev_dir, dev_dir.name)
        else:
            files = build(skill_dir, skill_dir.name)
        print(f"{files[0].relative_to(ROOT)} + {files[1].name}  {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
