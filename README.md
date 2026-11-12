# AutoShift skills

Agent skills for working on [AutoShift](https://github.com/auto-shift/autoshiftv2), in the open
[Agent Skills](https://agentskills.io) format: each skill is a directory with a `SKILL.md` and
`references/`, readable by any agent that supports the format.

| Skill | Use it to |
|---|---|
| [`autoshift-review`](skills/autoshift-review/SKILL.md) | Review a change for the defects that pass every gate: silent Compliant, musthave merge semantics, hub versus local templates, what the 2.17 runtime allows |
| [`autoshift-author`](skills/autoshift-author/SKILL.md) | Add functionality: an operator, a configuration policy, labels and config, readiness gates |
| [`autoshift-deploy`](skills/autoshift-deploy/SKILL.md) | Walk someone through installing AutoShift on their own hub, tailored to their environment |

All three target Red Hat Advanced Cluster Management 2.17. The template function set, context
variables and lookup restrictions come from the 2.17 source (governance-policy-propagator and
config-policy-controller `release-2.17`, and the go-template-utils `v7.2.0` they build with), kept in
[`shared/acm-templates.md`](shared/acm-templates.md) and copied into the skills that need it.
Where an AutoShift checkout's own `AGENTS.md` or `docs/` disagree with a skill, the checkout wins.

## Install

Link or copy a skill directory into your agent's skills location.

```bash
# Claude Code, every project
for s in skills/*/; do ln -s "$PWD/$s" ~/.claude/skills/"$(basename "$s")"; done
# Claude Code, one AutoShift checkout
ln -s "$PWD/skills/autoshift-review" /path/to/autoshiftv2/.claude/skills/autoshift-review
```

Agents that read `.agents/skills/`, and other Agent Skills implementations: link the same
directories there. Then ask in plain language ("review this branch", "add the Loki operator",
"help me install AutoShift"), or invoke a skill by name where the agent supports it.

## Layout

```
skills/<name>/
  SKILL.md                 procedure; loaded when the skill triggers
  references/              detail, loaded on demand
  evals/<case>/            behavior tests: prompt.md, case.yaml, graders/, files/
shared/
  acm-baseline.yaml        the ACM release the skills describe, and its go-template-utils version
  acm-templates.md         the template runtime of that release, copied into skills
  acm-functions.tsv        every function name, generated from go-template-utils
  acm-runtime-excerpts.txt the controller source blocks acm-templates.md is written from
tests/
  validate.py              static checks
  test_validate.py         mutation tests proving each check fails when it should
  parsecheck/              eval fixtures parse under the hub and local passes
  acm_drift.py             compares another ACM release with the baseline
  funcset/                 generator for acm-functions.tsv
  triggers/<skill>.json    should-trigger and near-miss queries per skill
  run_triggers.py          trigger eval runner
```

## Testing

| Command | Cost | What it proves |
|---|---|---|
| `make test` | free, offline | Frontmatter follows the spec; links and anchors resolve; shared copies match; the ACM baseline matches AutoShift's `versions.yaml`, the go-template-utils pin and every ACM version the skills name; every function called in a template snippet exists in that release and none is denied or Helm-only; every AutoShift path cited exists (`AUTOSHIFT_REPO`, default `../autoshiftv2`); no em dashes, contractions or banned terms; eval folders are well formed; each of those checks fails on a planted defect; fixtures parse |
| `make acm-drift` | free, needs network | Compares ACM at `REF` (default `main`, the next release) with the baseline: go-template-utils version, function list and controller source excerpts. See [Keeping up with ACM](#keeping-up-with-acm) |
| `make triggers` | billed | Each skill fires for its queries and not for near misses, with all three installed and competing. Three runs per query, majority wins |
| `make evals SKILL=<name>` | billed | Behavior: review cases plant known defects (and one clean policy that must not draw false positives); author cases build against a fresh clone; deploy cases check the walkthrough without a cluster. Runs with and without the skill through `claude plugin eval` |

Trigger sets use the format of the skill-creator description optimizer, which can tune a
description against them.

Both billed targets run with an empty `KUBECONFIG`, so no eval run can reach a live cluster, and keep
reports local. Eval runs have no network access, so the AutoShift validation suite cannot run inside
them: author cases report that gate as skipped. Author cases run against a clone of
`AUTOSHIFT_REPO`, whose `AGENTS.md` and existing policies already guide a run without the skill. The
cases that separate the two depend on rules the repository does not state, such as the hub lookup
restriction in `author-hub-cluster-list`; `author-dns-forwarding` passes either way and guards against
regressions.

`make evals SKILL=<name> CASE=<case> RUNS=3` runs one case three times per arm. `--case` takes a single
name or `*` glob, without `[...]` classes. The saved trace keeps only its start and end, so check
file contents with a `type: regex` grader whose `target` is `source: file` and a `path` relative to the
run directory, as `author-hub-cluster-list/graders/08-*` does.

## Keeping up with ACM

The skills describe one Red Hat Advanced Cluster Management release, recorded in
`shared/acm-baseline.yaml`. AutoShift's `versions.yaml` (`inputs.acm`) decides which release that is:
`make test` fails as soon as the two differ, and when a skill names an ACM version newer than the
baseline.

To move to a new release:

1. `make acm-drift REF=release-<x.y>` (or `main` before the branch exists, to preview). It reports the
   go-template-utils version the controllers build with, the function list diff, and a diff of each
   controller source block, headed by the `acm-templates.md` section it backs.
2. Revise those sections of `shared/acm-templates.md`, and any reference or checklist item the
   change affects. Verify new behavior in controller source or on a cluster before writing it.
3. `make acm-drift REF=release-<x.y> UPDATE=1` rewrites the baseline, function list, excerpts and
   go-template-utils pin, and lists every line that still names the old release.
4. Update those lines, then `make sync test`, and rerun `make evals` for the skills that changed.

Run `make acm-drift` against `main` from time to time: the next release's changes show up there
before its branch is cut.

## Contributing

Add a finding only after verifying it on a cluster or in controller source. State the rule and the
mechanism in the present tense; keep incident history out. Edit `shared/` and run `make sync`, never
the copies. Run `make test` before every change.

## License

Apache License 2.0.
