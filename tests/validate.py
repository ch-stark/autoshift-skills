#!/usr/bin/env python3
"""Static checks for the skills in this repository. Standard library only.

  python3 tests/validate.py [--autoshift PATH]

Checks:
  spec       SKILL.md frontmatter follows the Agent Skills specification
  links      every relative Markdown link and #anchor resolves
  shared     copies of shared/ references inside skills are identical to the source
  baseline   shared/acm-baseline.yaml agrees with the go-template-utils pin, the excerpts, the
             reference title, every ACM version the skills name and, with --autoshift, the ACM
             version in AutoShift's versions.yaml
  functions  every function called in a template snippet exists in ACM 2.17
             (shared/acm-functions.tsv) and none is denied or Helm-only
  paths      every AutoShift path the skills cite exists (needs --autoshift or AUTOSHIFT_REPO)
  style      no em dashes, contractions or banned terms in prose outside code
  evals      eval case folders and trigger sets are well formed
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
SHARED = ROOT / "shared"

SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Go text/template builtins and keywords: valid in a template, not in the ACM function list.
GO_BUILTINS = {
    "if", "else", "end", "range", "with", "define", "template", "block", "break", "continue",
    "and", "or", "not", "eq", "ne", "lt", "le", "gt", "ge", "len", "index", "slice", "print",
    "printf", "println", "html", "js", "urlquery", "call", "nil", "true", "false",
}
# Never valid at runtime: denied by go-template-utils, or Helm-only.
FORBIDDEN = {"env", "expandenv", "required", "tpl", "include", "lookupOrDefault"}
# Prose rules from the Red Hat style the AutoShift repository enforces.
BANNED = [r"\bhardcoded\b", r"\bvs\.?\b", r"\bIPI\b", r"\ba number of\b"]
CONTRACTION = re.compile(r"\b[A-Za-z]+n't\b|\b(it|that|there|what|who)'s\b|\b\w+'(re|ve|ll)\b", re.I)
ASSUMED_PATH_PREFIXES = (
    "policies/", "autoshift/", "tools/", "docs/", "scripts/", "components/",
    "openshift-gitops/", "advanced-cluster-management/", ".github/",
)

errors: list[str] = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def frontmatter(text: str):
    if not text.startswith("---\n"):
        return None, text
    end = text.index("\n---\n", 4)
    fm, body = text[4:end], text[end + 5:]
    data, key = {}, None
    for line in fm.splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            if key:
                data[key] = (data[key] + "\n" + line.strip()).strip()
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        data[key] = val.strip().strip('"').strip("'")
    return data, body


def check_spec():
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        md = skill / "SKILL.md"
        where = rel(md)
        if not md.exists():
            err(rel(skill), "missing SKILL.md")
            continue
        data, body = frontmatter(md.read_text())
        if data is None:
            err(where, "no YAML frontmatter")
            continue
        for k in data:
            if k not in SPEC_KEYS:
                err(where, f"frontmatter key '{k}' is not in the Agent Skills spec")
        name = data.get("name", "")
        if not NAME_RE.match(name) or len(name) > 64:
            err(where, f"name '{name}' must be lowercase letters, digits and single hyphens, at most 64")
        if name != skill.name:
            err(where, f"name '{name}' does not match directory '{skill.name}'")
        desc = data.get("description", "")
        if not 1 <= len(desc) <= 1024:
            err(where, f"description length {len(desc)} not within 1..1024")
        if len(data.get("compatibility", "")) > 500:
            err(where, "compatibility over 500 characters")
        if body.count("\n") > 500:
            err(where, f"body is {body.count(chr(10))} lines; keep SKILL.md under 500")


def slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[`*_]", "", s)
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(md: Path) -> set:
    out = set()
    in_code = False
    for line in md.read_text().splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("#"):
            out.add(slug(line.lstrip("#")))
    return out


def markdown_files():
    return sorted(p for p in ROOT.rglob("*.md")
                  if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
                  and "-workspace" not in str(p) and "evals" not in p.parts)


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links():
    link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    for md in markdown_files():
        for target in link.findall(strip_code(md.read_text())):
            if re.match(r"^[a-z]+://", target) or target.startswith("mailto:"):
                continue
            path, _, anchor = target.partition("#")
            dest = (md.parent / path).resolve() if path else md
            if not dest.exists():
                err(rel(md), f"broken link {target}")
                continue
            if anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                err(rel(md), f"missing anchor #{anchor} in {path or md.name}")


def check_shared():
    for src in SHARED.glob("*.md"):
        for copy in SKILLS.glob(f"*/references/{src.name}"):
            if copy.read_bytes() != src.read_bytes():
                err(rel(copy), f"differs from shared/{src.name}; run tests/sync-shared.sh")


def template_snippets(text: str):
    """Yield the body of each complete template expression on one line, hub ones first."""
    for esc, real in (('{{ "{{hub-" }}', "{{hub-"), ('{{ "{{hub" }}', "{{hub"), ('{{ "hub}}" }}', "hub}}"),
                      ('{{ "{{-" }}', "{{-"), ('{{ "{{" }}', "{{"), ('{{ "}}" }}', "}}")):
        text = text.replace(esc, real)
    for line in text.splitlines():
        for m in re.finditer(r"\{\{hub-?\s([^`{}]*?)\s-?hub\}\}", line):
            yield m.group(1)
        line = re.sub(r"\{\{hub-?\s[^`{}]*?\s-?hub\}\}", "HUB", line)
        for m in re.finditer(r"\{\{-?\s([^`{}]+?)\s-?\}\}", line):
            yield m.group(1)


def called_functions(expr: str):
    expr = re.sub(r"/\*.*?\*/", "", expr, flags=re.S)
    expr = re.sub(r'"(\\.|[^"\\])*"|`[^`]*`|\'[^\']*\'', " ", expr)
    for tok in re.findall(r"(?<![\w.$])([A-Za-z_][A-Za-z0-9_]*)\b", expr):
        yield tok


def check_functions():
    tsv = SHARED / "acm-functions.tsv"
    known = {line.split("\t")[0] for line in tsv.read_text().splitlines() if line}
    if not known:
        err(rel(tsv), "empty function list")
        return
    for md in markdown_files():
        if md.parent == ROOT:
            continue
        text = md.read_text()
        for expr in template_snippets(text):
            if "<" in expr and ">" in expr and "<" not in expr.split()[0]:
                expr = re.sub(r"<[^>]*>", "x", expr)
            for fn in called_functions(expr):
                if fn in FORBIDDEN:
                    err(rel(md), f"template calls '{fn}', which ACM 2.17 does not provide")
                elif fn not in known and fn not in GO_BUILTINS and fn not in {"x", "hub", "HUB"}:
                    err(rel(md), f"template calls unknown function '{fn}' in: {expr.strip()[:70]}")
    tables = SHARED / "acm-templates.md"
    section = tables.read_text().split("## ACM functions")[1].split("\n## ")[0]
    for row in re.findall(r"^\| `([^`]+)`", section, re.M):
        for name in re.findall(r"`?([A-Za-z][A-Za-z0-9]*)", row)[:1]:
            if name not in known:
                err(rel(tables), f"function table names '{name}', not in the 2.17 list")


ACM_VERSION = re.compile(r"\b2\.(\d+)\b")


def acm_baseline():
    text = (SHARED / "acm-baseline.yaml").read_text()
    return dict(re.findall(r"^(\w+):\s*'?([^'\n]+)'?\s*$", text, re.M))


def check_baseline(repo):
    base = acm_baseline()
    for key in ("acm", "releaseBranch", "goTemplateUtils"):
        if key not in base:
            err("shared/acm-baseline.yaml", f"missing {key}")
            return
    acm, minor = base["acm"], int(base["acm"].split(".")[1])
    gomod = (ROOT / "tests" / "funcset" / "go.mod").read_text()
    if f"go-template-utils/v7 {base['goTemplateUtils']}" not in gomod:
        err("tests/funcset/go.mod", f"does not require go-template-utils {base['goTemplateUtils']}")
    excerpts = SHARED / "acm-runtime-excerpts.txt"
    if not excerpts.exists() or "ANCHOR NOT FOUND" in excerpts.read_text():
        err(rel(excerpts), "missing or has an unresolved anchor: run make acm-drift")
    title = (SHARED / "acm-templates.md").read_text().splitlines()[0]
    if acm not in title:
        err("shared/acm-templates.md", f"title does not name ACM {acm}")
    for md in markdown_files():
        text = md.read_text()
        for m in ACM_VERSION.finditer(text):
            if int(m.group(1)) > minor:
                line = text.count("\n", 0, m.start()) + 1
                err(f"{rel(md)}:{line}", f"names ACM 2.{m.group(1)}, newer than the {acm} baseline")
        data, _ = frontmatter(text) if md.name == "SKILL.md" else (None, None)
        desc = (data or {}).get("description", "")
        if ACM_VERSION.search(desc) and acm not in desc:
            err(rel(md), f"description names an ACM version other than the {acm} baseline")
    if repo:
        versions = (repo / "versions.yaml").read_text()
        m = re.search(r"^inputs:\n(?:[ \t]+.*\n)*?[ \t]+acm:\s*'?([\d.]+)'?", versions, re.M)
        if not m:
            err(f"{repo}/versions.yaml", "has no inputs.acm")
        elif m.group(1) != acm:
            err("shared/acm-baseline.yaml",
                f"ACM {acm}, but AutoShift targets {m.group(1)} (versions.yaml inputs.acm): run make acm-drift")


def check_paths(repo: Path):
    token = re.compile(r"`([^`\s]+)`")
    for md in markdown_files():
        for t in token.findall(md.read_text()):
            t = t.rstrip(".,:;")
            if not t.startswith(ASSUMED_PATH_PREFIXES) or re.search(r"[<>*{}$]", t):
                continue
            if ":" in t:
                t = t.split(":")[0]
            if not (repo / t).exists():
                err(rel(md), f"cites {t}, which does not exist in {repo}")


def check_style():
    for md in markdown_files():
        prose = strip_code(md.read_text())
        for i, line in enumerate(prose.splitlines(), 1):
            if "\u2014" in line or re.search(r"\s--\s", line):
                err(rel(md), f"em dash in prose: {line.strip()[:70]}")
            if CONTRACTION.search(line):
                err(rel(md), f"contraction: {line.strip()[:70]}")
            for b in BANNED:
                if re.search(b, line):
                    err(rel(md), f"banned term {b}: {line.strip()[:70]}")


def check_evals():
    for case in sorted(SKILLS.glob("*/evals/*")):
        if not case.is_dir() or case.name in {"results", "mocks", "node_modules"}:
            continue
        where = rel(case)
        prompt = case / "prompt.md"
        if not prompt.exists():
            err(where, "missing prompt.md")
        else:
            data, body = frontmatter(prompt.read_text())
            allowed = {"tags", "max_turns", "timeout_seconds", "allowed_tools"}
            if data is None or set(data) - allowed:
                err(where, f"prompt.md settings keys must be within {sorted(allowed)}")
            if not body.strip():
                err(where, "prompt.md has no prompt")
        cy = case / "case.yaml"
        text = cy.read_text() if cy.exists() else ""
        if 'schema_version: "1.1"' not in text:
            err(where, 'case.yaml needs schema_version: "1.1" (quoted)')
        if f"name: {case.name}\n" not in text:
            err(where, "case.yaml name must equal the folder name")
        graders = sorted((case / "graders").glob("*.md"))
        if not graders:
            err(where, "no graders")
        for g in graders:
            d, b = frontmatter(g.read_text())
            if not d or d.get("type") not in {"llm", "regex", "file_exists", "tool_used", "tool_order", "baseline"}:
                err(rel(g), "grader needs a frontmatter block with a known type")
        if "scaffold_script" in text and not (case / "place-files.sh").exists():
            err(where, "case.yaml names place-files.sh but it is missing")
    for tf in sorted((ROOT / "tests" / "triggers").glob("*.json")):
        items = json.loads(tf.read_text())
        if not (SKILLS / tf.stem).is_dir():
            err(rel(tf), f"no skill named {tf.stem}")
        pos = sum(1 for i in items if i.get("should_trigger") is True)
        neg = sum(1 for i in items if i.get("should_trigger") is False)
        if pos < 5 or neg < 5 or pos + neg != len(items):
            err(rel(tf), f"need at least 5 positive and 5 negative queries, each with should_trigger; got {pos}/{neg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autoshift", default=os.environ.get("AUTOSHIFT_REPO"))
    args = ap.parse_args()
    repo = Path(args.autoshift) if args.autoshift else None
    checks = [("spec", check_spec), ("links", check_links), ("shared", check_shared),
              ("baseline", lambda: check_baseline(repo)), ("functions", check_functions), ("style", check_style), ("evals", check_evals)]
    if args.autoshift:
        checks.append(("paths", lambda: check_paths(Path(args.autoshift))))
    for name, fn in checks:
        before = len(errors)
        fn()
        print(f"{'ok  ' if len(errors) == before else 'FAIL'} {name}")
    if not args.autoshift:
        print("skip paths (pass --autoshift or set AUTOSHIFT_REPO)")
    for e in errors:
        print("  " + e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
