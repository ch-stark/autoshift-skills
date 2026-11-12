#!/usr/bin/env python3
"""Compare the ACM template runtime at another release with the baseline these skills describe.

  python3 tests/acm_drift.py [--ref main|release-2.18] [--update]

Reads governance-policy-propagator and config-policy-controller at --ref (default main, the next
release in development), then:

  1. takes the go-template-utils version both controllers build with,
  2. regenerates the template function list against that version,
  3. extracts the source blocks shared/acm-templates.md is written from (hub context, the hub lookup
     restriction, skipObject, the customMessage data),

and diffs each against shared/acm-functions.tsv and shared/acm-runtime-excerpts.txt. Exit 1 on any
difference. Each diff points at the prose in shared/acm-templates.md to revise.

--update writes the new function list, excerpts, go-template-utils pin and baseline. Run it only
after the prose matches, then `make sync test`. Needs git, go and network access.
"""
import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"
BASELINE = SHARED / "acm-baseline.yaml"
FUNCSET = ROOT / "tests" / "funcset"
CACHE = ROOT / ".acm-src"
REPOS = {
    "propagator": "https://github.com/stolostron/governance-policy-propagator.git",
    "config-policy-controller": "https://github.com/stolostron/config-policy-controller.git",
}
GTU = "github.com/stolostron/go-template-utils/v7"

# (repo, file, anchor regex, what it backs in shared/acm-templates.md). The excerpt runs from the
# anchor line to the matching close brace, or is the anchor line alone when it opens no block.
EXCERPTS = [
    ("propagator", "controllers/propagator/propagation.go", r"^type templateCtx struct",
     "Context variables: the hub context fields"),
    ("propagator", "controllers/propagator/propagation.go", r"templateContext := templateCtx\{",
     "Context variables: .PolicyMetadata keys"),
    ("propagator", "controllers/propagator/propagation.go",
     r'strings\.Contains\(string\(policyT\.ObjectDefinition\.Raw\), "ManagedClusterLabels"\)',
     "Context variables: .ManagedClusterLabels is populated only when the text names it"),
    ("propagator", "controllers/propagator/propagation.go",
     r"^func \(r \*ReplicatedPolicyReconciler\) getTemplateResolverOpts\(",
     "Hub lookup restrictions"),
    ("config-policy-controller", "controllers/configurationpolicy_utils.go",
     r"resolveOptions\.CustomFunctions = map\[string\]any\{",
     "ACM functions: skipObject"),
    ("config-policy-controller", "controllers/configurationpolicy_controller.go",
     r'template\.New\("custom-msg"\)', "Two engines: customMessage function set"),
    ("config-policy-controller", "controllers/configurationpolicy_controller.go",
     r"templateData := map\[string\]any\{", "Two engines: customMessage data"),
]


def sh(*cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout


def baseline():
    return dict(re.findall(r"^(\w+):\s*'?([^'\n]+)'?\s*$", BASELINE.read_text(), re.M))


def checkout(name, url, ref):
    d = CACHE / name
    if not d.exists():
        sh("git", "clone", "--quiet", "--filter=blob:none", url, str(d))
    sh("git", "fetch", "--quiet", "origin", ref, cwd=d)
    sh("git", "checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=d)
    return d


def gtu_version(src: Path):
    m = re.search(rf"^\s*{re.escape(GTU)} (\S+)", (src / "go.mod").read_text(), re.M)
    return m.group(1) if m else None


def block(lines, start):
    if "{" not in lines[start]:
        return lines[start:start + 1]
    depth, out = 0, []
    for line in lines[start:]:
        out.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
    return out


def excerpts(srcs):
    out = []
    for repo, path, anchor, backs in EXCERPTS:
        out.append(f"### {repo} {path} ({backs})")
        f = srcs[repo] / path
        lines = f.read_text().splitlines() if f.exists() else []
        hit = next((i for i, l in enumerate(lines) if re.search(anchor, l)), None)
        found = ["ANCHOR NOT FOUND: " + anchor] if hit is None else block(lines, hit)
        # Ignore what gofmt alignment and the interface{} to any rewrite change.
        out.extend(" ".join(l.replace("interface{}", "any").split()) for l in found)
        out.append("")
    return "\n".join(out)


def functions(version):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "funcset"
        shutil.copytree(FUNCSET, work)
        env = {**os.environ, "GOTOOLCHAIN": "auto", "GOFLAGS": "-mod=mod"}
        sh("go", "mod", "edit", f"-require={GTU}@{version}", cwd=work, env=env)
        sh("go", "mod", "tidy", cwd=work, env=env)
        gtu_dir = sh("go", "list", "-m", "-f", "{{.Dir}}", GTU, cwd=work, env=env).strip()
        return sh("go", "run", ".", gtu_dir, cwd=work, env=env)


def show(label, old, new):
    d = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "baseline", label, lineterm=""))
    print("\n".join(d) if d else f"{label}: unchanged")
    return bool(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="main")
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args()
    base = baseline()
    CACHE.mkdir(exist_ok=True)
    srcs = {n: checkout(n, u, args.ref) for n, u in REPOS.items()}

    versions = {n: gtu_version(d) for n, d in srcs.items()}
    print(f"go-template-utils at {args.ref}: {versions}  (baseline {base['goTemplateUtils']})")
    if len(set(versions.values())) != 1:
        print("the controllers pin different go-template-utils versions: compare each by hand")
    version = versions["config-policy-controller"]

    funcs = functions(version)
    ex = excerpts(srcs)
    changed = show(f"functions@{version}", (SHARED / "acm-functions.tsv").read_text(), funcs)
    changed |= show(f"excerpts@{args.ref}", (SHARED / "acm-runtime-excerpts.txt").read_text()
                    if (SHARED / "acm-runtime-excerpts.txt").exists() else "", ex)
    changed |= version != base["goTemplateUtils"]

    if args.update:
        (SHARED / "acm-functions.tsv").write_text(funcs)
        (SHARED / "acm-runtime-excerpts.txt").write_text(ex)
        env = {**os.environ, "GOTOOLCHAIN": "auto"}
        sh("go", "mod", "edit", f"-require={GTU}@{version}", cwd=FUNCSET, env=env)
        sh("go", "mod", "tidy", cwd=FUNCSET, env=env)
        m = re.fullmatch(r"release-(\d+\.\d+)", args.ref)
        text = BASELINE.read_text()
        text = re.sub(r"^goTemplateUtils:.*$", f"goTemplateUtils: {version}", text, flags=re.M)
        if m:
            text = re.sub(r"^acm:.*$", f"acm: '{m.group(1)}'", text, flags=re.M)
            text = re.sub(r"^releaseBranch:.*$", f"releaseBranch: {args.ref}", text, flags=re.M)
        BASELINE.write_text(text)
        print("updated shared/ and tests/funcset; now run: make sync test")
        if m and m.group(1) != base["acm"]:
            print(f"lines still naming ACM {base['acm']} (review each):")
            hits = subprocess.run(["grep", "-rn", "--exclude-dir=evals", base["acm"], "skills", "shared",
                                   "README.md"], cwd=ROOT, capture_output=True, text=True).stdout
            print(hits or "  none")
        return 0
    if changed:
        print(f"\nACM at {args.ref} differs from the {base['acm']} baseline. Revise the sections named in"
              " each ### header of shared/acm-templates.md, then rerun with --update.")
        return 1
    print(f"ACM at {args.ref} matches the {base['acm']} baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
