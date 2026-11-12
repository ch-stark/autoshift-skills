# Repository conventions

## Contents

- [Policy layout and naming](#policy-layout-and-naming)
- [Labels and config](#labels-and-config)
- [Operator installs](#operator-installs)
- [Secrets](#secrets)
- [GitOps](#gitops)
- [Prose, comments and messages](#prose-comments-and-messages)

## Policy layout and naming

- Policies are discovered by marker file under `policies/{stable,certified,community}/<name>/`:
  `kustomization.yaml` means PolicyGenerator, `Chart.yaml` without one means Helm. Registering a
  policy by hand anywhere is a defect. `excludePolicies` opts out.
- New policies come from `scripts/generate-operator-policy.sh` or `scripts/generate-policy.sh`, and
  need a `README.md`.
- `manifests/` is enforced; `test/` holds inform-only checks, each its own `policies[]` entry with
  `remediationAction: inform`. A root `remediationAction` overrides its children, so an inform check
  bundled into an enforcing policy becomes enforced.
- `${POLICY_NAMESPACE}`, `${REMEDIATION}`, `${EVAL_COMPLIANT}`, `${EVAL_NONCOMPLIANT}` and
  `${CLUSTER_SET_SUFFIX}` belong in `policy-generator-config.yaml` and `placement.yaml` only, never in
  `manifests/`, where substitution would clobber template `$vars`.
- Every ConfigurationPolicy keeps an `evaluationInterval` block with both `compliant` and
  `noncompliant`, as literals.
- **Names correspond.** Operator install: policy `policy-<component>-operator-install`, placement
  `placement-policy-<component>-operator-install`. Others: policy `policy-<component>-<thing>`,
  placement file `placement-<thing>.yaml`, Placement `placement-<component>-<thing>`. A rename (often
  forced by the 63-character `<namespace>.<name>` limit) must carry the placement file and resource
  with it; grep for the old name.
- Policy counts are never written into documentation.

## Labels and config

- `autoshift.io/*` labels live in values files only. Nothing puts one directly on a ManagedCluster,
  and docs never tell a user to; the `cluster-labels` policy stamps them.
- Every consumed `autoshift.io/<key>` is declared in `autoshift/values/clustersets/_example.yaml` or a
  `clusters/_example*.yaml`. Check the read spelling against the declaration character by character:
  a misspelled read with a `| default` renders fine and ignores the user's value.
- **Placement is labels, data is config.** A value that selects which policies get placed is a label,
  even with more than two states (`acs-registration: crs|manual|initBundle`); give each state a
  placement with `operator: In`. A value read only at enforcement is config.
- A new policy's gate label and config key share one spelling: the directory name, kebab-case on both
  sides (`odf-dr` label, `config.odf-dr`), with mode sub-blocks keyed by the label's values.
- Three-state operator labels: `true | false | uninstall`. Removal happens only through `uninstall`.
- Values YAML: block notation for lists and maps, never flow (`[a, b]`, `{k: v}`). Commented example
  blocks uncomment to valid, correctly typed YAML; no trailing comments or alignment padding on value
  lines.
- A change under `autoshift/values/` needs the top-level chart rendered (`make test` covers it).

## Operator installs

- `components/operator-install/` is a pass-through interface: values go through verbatim, never
  `tpl`'d. ACM-specific logic (hub templates, rendered-config lookups, version resolution) belongs in
  each caller's `valuesInline`, not in the shared chart.
- The config key for versions is the version-label base (`autoshift.io/<key>-version`), not the
  chart's `name`.
- Standard labels: `<component>`, `-subscription-name`, `-channel`, `-source`, `-source-namespace`,
  `-version`.
- OwnNamespace-only operators pass `targetNamespaces`; AllNamespaces operators must not.

## Secrets

- No credentials in values files or any tracked file. Sensitive settings come from a Secret created
  out of band, referenced by `configSecretRef: {name, namespace, key}`, read with a local `lookup`,
  merged last. The example documents the `oc create secret` command and holds only non-sensitive
  keys.
- A free-form `config:` pass-through block will attract pasted credentials; pair it with a
  `configSecretRef`.

## GitOps

- Objects AutoShift creates are named `gitops-*`, not `argocd-*`. Keep `argocd-` only where a
  controller fixes the name (check with `oc explain` whether the field is settable). Rename every
  reference in the same change; a partial rename leaves both sides Compliant and disconnected.
- Infrastructure GitOps may hold cluster-admin. Team GitOps is least privilege: a team component
  needing cluster-scoped access gets a purpose-built ClusterRole, never an entry in
  `ARGOCD_CLUSTER_CONFIG_NAMESPACES` (that makes the instance cluster-scoped).
- Argo CD `resourceExclusions` keep `clusterview.open-cluster-management.io` kinds excluded; otherwise
  a prune can hit the read-only ManagedClusterSet view instead of the real object.

## Prose, comments and messages

Applies to `README.md`, `docs/`, policy READMEs, YAML and script comments, and `customMessage`. Vale
lints only Markdown; comments are held to the same rules by review.

- Red Hat style: full `Red Hat` product names, no em dashes (neither `—` nor ` -- `), no
  contractions, sentence-case headings, `through` not `via`, no `above`/`below` for position. Banned:
  `IPI`, `hardcoded`, `vs`, `a number of`, `typo`. Adding a term to the Vale accept list to silence a
  finding is a defect.
- Present tense, current behavior only. No "previously", "used to", "the old", version history, or
  incident narration ("this silently broke", "we tried"). That belongs in the commit message.
- Comments are one or two lines stating the rule or constraint. No reasoning walkthroughs, no
  defending a rejected alternative, no comments about what the code does not do.
- Never assert unverified behavior in a comment or doc; say plainly what is unverified.
- Docs must not imply that deleting a values key turns a setting off under `musthave`.
- `customMessage` front-loads the remedy: exact label or key, value, and command.
- Bulk find-and-replace over prose is a defect source: check a prose-wide diff for doubled words,
  broken parentheses, partial-word replacements and edits inside code blocks.
- `docs/diagrams/*.drawio.svg` must never pass through an SVG optimizer; it strips the embedded
  editable source.
