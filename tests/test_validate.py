#!/usr/bin/env python3
"""Mutation tests for validate.py: each plants one defect in a copy of the repository and asserts
the validator reports it. A check that never fails proves nothing.

  python3 -m unittest tests/test_validate.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTOSHIFT = os.environ.get("AUTOSHIFT_REPO", str(ROOT.parent / "autoshiftv2"))


def run(repo: Path, *extra):
    p = subprocess.run([sys.executable, str(repo / "tests" / "validate.py"), *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


class Mutations(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        shutil.copytree(ROOT, self.repo, ignore=shutil.ignore_patterns(".git", ".acm-src", "*-workspace"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def append(self, rel, text):
        p = self.repo / rel
        p.write_text(p.read_text() + text)

    def replace(self, rel, old, new):
        p = self.repo / rel
        s = p.read_text()
        assert old in s, f"mutation anchor not found in {rel}: {old!r}"
        p.write_text(s.replace(old, new, 1))

    def assertCaught(self, check, needle, *extra):
        code, out = run(self.repo, *extra)
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAIL {check}", out)
        self.assertIn(needle, out)

    def test_clean_tree_passes(self):
        code, out = run(self.repo)
        self.assertEqual(code, 0, out)

    def test_baseline_newer_version_named(self):
        self.append("skills/autoshift-review/references/acm-runtime.md", "\nOn ACM 2.99 this changes.\n")
        self.assertCaught("baseline", "names ACM 2.99")

    def test_baseline_disagrees_with_autoshift(self):
        self.replace("shared/acm-baseline.yaml", "acm: '2.17'", "acm: '2.16'")
        self.assertCaught("baseline", "AutoShift targets 2.17", "--autoshift", AUTOSHIFT)

    def test_baseline_pin_mismatch(self):
        self.replace("shared/acm-baseline.yaml", "goTemplateUtils: v7.2.0", "goTemplateUtils: v7.9.9")
        self.assertCaught("baseline", "does not require go-template-utils v7.9.9")

    def test_denied_function(self):
        self.append("skills/autoshift-author/references/patterns.md", '\n```\n{{ env "HOME" }}\n```\n')
        self.assertCaught("functions", "'env'")

    def test_helm_only_function_in_hub_template(self):
        self.append("skills/autoshift-author/references/patterns.md",
                    '\n```\n{{hub required "x" .ManagedClusterName hub}}\n```\n')
        self.assertCaught("functions", "'required'")

    def test_unknown_function(self):
        self.append("skills/autoshift-review/references/hub-templates.md", "\n`{{ fooBar .x }}`\n")
        self.assertCaught("functions", "unknown function 'fooBar'")

    def test_helm_escaped_hub_template_is_checked(self):
        self.append("skills/autoshift-review/references/hub-templates.md",
                    '\n```\n\'{{ "{{hub" }} nosuchfn .ManagedClusterName {{ "hub}}" }}\'\n```\n')
        self.assertCaught("functions", "unknown function 'nosuchfn'")

    def test_function_table_names_unknown_function(self):
        self.replace("shared/acm-templates.md", "| `atoi` |", "| `atoiz` |")
        self.assertCaught("functions", "'atoiz'")

    def test_shared_copy_drift(self):
        self.append("skills/autoshift-author/references/acm-templates.md", "\nlocal edit\n")
        self.assertCaught("shared", "differs from shared/acm-templates.md")

    def test_broken_anchor(self):
        self.append("skills/autoshift-review/SKILL.md", "\n[x](references/acm-runtime.md#no-such-heading)\n")
        self.assertCaught("links", "missing anchor #no-such-heading")

    def test_broken_link(self):
        self.append("skills/autoshift-deploy/SKILL.md", "\n[x](references/missing.md)\n")
        self.assertCaught("links", "broken link references/missing.md")

    def test_name_mismatch(self):
        self.replace("skills/autoshift-deploy/SKILL.md", "name: autoshift-deploy", "name: autoshift-deployer")
        self.assertCaught("spec", "does not match directory")

    def test_unknown_frontmatter_key(self):
        self.replace("skills/autoshift-deploy/SKILL.md", "license:", "argument-hint: x\nlicense:")
        self.assertCaught("spec", "argument-hint")

    def test_em_dash(self):
        self.append("skills/autoshift-author/SKILL.md", "\nThis is wrong — very wrong.\n")
        self.assertCaught("style", "em dash")

    def test_contraction(self):
        self.append("skills/autoshift-author/SKILL.md", "\nIt doesn't work.\n")
        self.assertCaught("style", "contraction")

    def test_bad_trigger_set(self):
        (self.repo / "tests/triggers/autoshift-review.json").write_text('[{"query": "x", "should_trigger": true}]')
        self.assertCaught("evals", "at least 5 positive and 5 negative")

    def test_eval_case_without_graders(self):
        case = next((self.repo / "skills").glob("*/evals/*/graders"))
        shutil.rmtree(case)
        self.assertCaught("evals", "no graders")

    @unittest.skipUnless(Path(AUTOSHIFT, "AGENTS.md").exists(), "AutoShift checkout not found")
    def test_cited_path_missing(self):
        self.append("skills/autoshift-author/references/layout.md", "\nSee `policies/stable/no-such-policy/README.md`.\n")
        self.assertCaught("paths", "policies/stable/no-such-policy/README.md", "--autoshift", AUTOSHIFT)


if __name__ == "__main__":
    unittest.main()
