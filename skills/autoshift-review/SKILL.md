---
name: autoshift-review
description: Use when reviewing AutoShift diffs or policy files for ACM defects. Excludes authoring, deployment and live cluster diagnosis.
license: Apache-2.0
compatibility: Built for the AutoShift repository. Uses git; helm, go and make if present to verify findings.
metadata:
  author: Ben Carr
  version: "0.1.1"
  tags: autoshift
---

# AutoShift review

## Purpose

Review changes in an AutoShift checkout for Red Hat Advanced Cluster Management (ACM) 2.17
policy defects that generic code review misses.

Most AutoShift defects pass every gate. The policy renders, the validation suite is green, ACM
reports Compliant, and nothing is applied. Review for that class of defect first. Style comes last,
if at all.

## Prerequisites

- An AutoShift checkout and Git, plus the diff, branch, commit, PR or policy file to review.
- Helm, Go and Make for the verification steps that use them. If a tool is unavailable, report the
  affected gate as skipped and keep unsupported findings under Worth discussing.
- No live cluster access is needed for this review. Use repository files, renders and controller
  source as evidence.

## Instructions

1. **Find the change.** Use the target the user gave (a PR number, branch, commit or path). With
   none, review `git diff $(git merge-base HEAD main)` plus uncommitted changes. Read each changed
   file in full, not only the hunks: most bugs here sit in how a template line interacts with the
   block around it.
2. **Load only the references the change needs.**

   | Changed path | Read |
   |---|---|
   | any template expression (`{{`), in any file | [acm-templates](references/acm-templates.md): the ACM 2.17 function set, context variables and lookup restrictions |
   | `policies/**/manifests/`, `test/`, `templates/`, any `object-templates-raw` | [hub-templates](references/hub-templates.md) and [acm-runtime](references/acm-runtime.md) |
   | `complianceType`, `remediationAction`, `dependencies`, `OperatorPolicy`, teardown | [acm-runtime](references/acm-runtime.md) |
   | `tools/`, `tools/testdata/`, `autoshift/values/**/_example*.yaml` | [validation-harness](references/validation-harness.md) |
   | new policy, placement, label, config key, values file, `components/` | [repo-conventions](references/repo-conventions.md) |
   | `README.md`, `docs/`, policy READMEs, comments, `customMessage` text | the prose section of [repo-conventions](references/repo-conventions.md#prose-comments-and-messages) |

   If the checkout has `AGENTS.md`, `docs/policy-behavior.md` and `docs/developer-guide.md`, they
   are authoritative where they disagree with this skill.
3. **Run the gates when the toolchain is present.** `make test` after changes to `policies/`,
   `autoshift/values/` or `tools/`. Report a gate you could not run as skipped, never as passed. A
   green suite proves rendering and resolution only; it says nothing about enforcement.
4. **Walk the checklist** below against every changed policy.
5. **Verify before reporting.** Each finding needs evidence: a `helm template` render, a
   `make test` failure, a minimal Go `text/template` probe, or a cited line of controller source.
   An A/B comparison counts only when both sides had identical input. When a behavior change could
   be deliberate, ask rather than assert.
6. **Report** in the format at the end of this file.

## Checklist

Each line names the trap; the reference holds the mechanism and the fix.

**Silent no-ops (highest value)**

- [ ] A policy that can render no objects reports Compliant. Required input read with
  `lookup ... | default dict` is masked; it must fail loudly (`fromConfigMap`, explicit key checks,
  `fail`). [acm-runtime](references/acm-runtime.md#empty-and-failing-policies)
- [ ] A dedicated placement plus an in-template `if` on the same label: where the `if` is false the
  policy applies nothing and reports Compliant. Gate with placement only.
- [ ] Removing a key from values with `musthave`: the live field stays. Changing one field of a list
  entry with `musthave`: a second entry is appended. [acm-runtime](references/acm-runtime.md#compliancetype-semantics)
- [ ] Two object templates naming the same object in one ConfigurationPolicy: only the first applies.
- [ ] A list key whose items are all conditional renders `key: null`, which `musthave` writes,
  clearing the live list.
- [ ] `musthave` + enforce gated on a `lookup` that may be empty creates the object.
- [ ] `dependencies` on a policy whose placement can miss a cluster this one selects (another label,
  cluster set or target): the dependency resolves against the same cluster's copy, so it stays
  Pending forever there.
- [ ] A Policy renamed in place, or its content swapped with the same name: the replica can keep the
  old spec.

**Template resolution**

- [ ] Hub template used for something local to the target cluster, or `.ManagedClusterLabels` read
  in a local (`{{ }}`) template, where it is nil. [hub-templates](references/hub-templates.md#which-template-to-use)
- [ ] Hub `fromSecret` piped to `base64dec`, or composed into a string. It returns an encrypted token.
- [ ] `{{-` shallower than surrounding content in a block scalar; multi-line output without
  `autoindent`; empty lines without indent padding; comment syntax inside a hub template or a folded
  scalar. [hub-templates](references/hub-templates.md#whitespace-and-block-scalars)
- [ ] Unquoted `toInt`/`toBool`/`toLiteral` template value.
- [ ] `.PolicyMetadata`, `.ManagedClusterName` or `.ManagedClusterLabels` read inside `range`.
- [ ] Hub expression inlined in a backtick raw string, or a deep hub lookup inlined in a field rather
  than hoisted to its own `{{hub- ... hub}}` line.
- [ ] Lookups indexed by position (`items[0]`) rather than filtered by name or label.
- [ ] A function or variable the 2.17 engine does not provide there: `env`/`expandenv`; Helm-only
  `required`, `tpl`, `include`; `skipObject` or `.Object` in `object-templates-raw`; any ACM function
  in `customMessage`. Check names against [acm-templates](references/acm-templates.md).
- [ ] A hub `lookup` outside the policy namespace, or of any cluster-scoped object other than the
  target's own ManagedCluster, on a policy without `hubTemplateOptions.serviceAccountName`. Passes
  `make test`, fails on the hub.
- [ ] `| default` on a value where `0` or `false` is legitimate (Sprig treats both as empty).

**Enforcement shape**

- [ ] Existence or readiness check bundled into an enforcing policy instead of its own inform policy
  under `test/`. A metadata-only `musthave` under enforce creates empty placeholders.
- [ ] `mustnothave` used to assert a field value or list element (it deletes the whole object), or as
  a probe that an enforce override would turn into a delete.
- [ ] Enforcing `mustnothave` used as a completion barrier, or an OperatorPolicy removal expected to
  clean up operands.
- [ ] `mustonlyhave` on a CR another controller owns without read-modify-write and a `fail` guard on
  the live read.
- [ ] A fake object asserted only to force NonCompliant. Use `customMessage` on the real object.
- [ ] `evaluationInterval` block missing, missing a key, or set to a hub template.
- [ ] A mode change that tears down the previous mode's objects automatically.

**Repo contract**

- [ ] New `autoshift.io/<key>` not declared in an `_example*.yaml`, or a label read that differs from
  the declared spelling. [repo-conventions](references/repo-conventions.md#labels-and-config)
- [ ] A new `| default "literal"` in a local template with no matching `_example*.yaml` value, or a
  new branch gated on a key no example sets (it never renders in CI). [validation-harness](references/validation-harness.md)
- [ ] Credentials or credential-shaped fields in values; high-entropy fakes in `tools/testdata/`.
- [ ] Policy, placement file and Placement names that do not correspond; a policy registered by hand.
- [ ] ACM-specific logic added to `components/operator-install/`; OwnNamespace operators without
  `targetNamespaces`.
- [ ] Edits to `tools/internal/resolver/e2e_test.go` to make a policy pass.
- [ ] A hard-coded policy count in docs.

## Do not flag

- ACM 2.15 portability: the baseline is ACM 2.17. Any function listed in
  [acm-templates](references/acm-templates.md) is available, including `trimPrefix`,
  `compact`, `toString`, `uniq` and `fail`.
- `evaluationInterval: watch`. It is the default, and `watch` tracks every `lookup`, `fromConfigMap`
  and `fromSecret` the template reads.
- Explanatory comments inside `object-templates-raw`, unless they narrate history (see prose rules).
- Debug or scratch charts, at production severity.
- Style preferences, in the same list as defects.

## Examples

- Review a branch: "Review my AutoShift branch before I open a PR; it changes policy manifests and
  adds labels to the example values." Compare the branch with main, include uncommitted changes,
  and load the template, runtime and repository references needed by the diff.
- Review one policy: "Does this AutoShift ConfigurationPolicy use hub fromSecret correctly?"
  Check the hub and local return values in the template references, then verify the rendered value
  before reporting a defect.
- Review a clean change: "Sanity-check this AutoShift console banner change." Apply the checklist
  and say there are no confirmed findings when the evidence supports none.

## Limitations

This skill targets ACM 2.17 and the AutoShift repository conventions. It reviews changes; live
cluster diagnosis and deployment need their own evidence and workflow. A green validation suite
proves rendering and resolution, not enforcement or the absence of silent no-ops. Missing tools,
repository context or controller source can leave a suspected defect unverified.

## Troubleshooting

- No review target supplied: use the default diff in step 1 of Instructions.
- A validation command is unavailable or fails before checking policies: report the gate as skipped
  or failed with the cause, and continue the file review with the evidence available.
- A render fails near a hub delimiter: read the Reading failures section of
  [validation-harness](references/validation-harness.md) to distinguish the hub error from the
  downstream local-parser error.

## Report format

```
## Confirmed
1. path/to/file.yaml:LINE: <one-sentence defect>
   Failure: <concrete input or cluster state> -> <wrong result, including what ACM reports>
   Evidence: <command run and its output, or the source line>
   Fix: <the specific change>

## Worth discussing
<suspicious, plausibly intentional, or unverified; say which>

## Gates
make test: passed | failed (<summary>) | skipped (<why>)
```

Rank by blast radius: a silent false Compliant across the fleet outranks a loud render failure. Say
plainly when there are no confirmed findings.
