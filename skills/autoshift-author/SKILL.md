---
name: autoshift-author
description: Add new functionality to AutoShift, the OpenShift Day 2 framework built on Red Hat Advanced Cluster Management 2.17 policies and OpenShift GitOps. Covers installing a new operator through policy, configuring a component (a CR, ConfigMap, MachineConfig or any resource) on hubs or managed clusters, adding an autoshift.io label or config key, adding readiness gates and test policies, and extending an existing policy. Use whenever someone wants AutoShift to install, configure or manage something it does not yet, even if they only name the product ("can AutoShift set up the Loki operator?", "add a MachineConfig for chrony").
license: Apache-2.0
compatibility: Built for an AutoShift checkout. Needs git, bash and helm; go and make to run the validation suite; oc against a cluster to research operators and CRD schemas.
metadata:
  version: "0.1.0"
---

# Add functionality to AutoShift

The goal is a policy that does the right thing on a real ACM 2.17 hub, not one that merely passes
`make test`. The suite proves rendering and resolution; most AutoShift bugs live in enforcement
semantics it cannot see. So write to the runtime rules in the references, and say plainly what you
could not verify.

## 1. Decide the shape

| The request | Build |
|---|---|
| Install an operator | `scripts/generate-operator-policy.sh`, a new directory |
| Configure something an existing component owns | `scripts/generate-policy.sh <name> --dir policies/<tier>/<component>` |
| Configure something new, no operator | `scripts/generate-policy.sh <name> --dir policies/<tier>/<new>` |
| Wait for state before configuring | an inform policy under `test/`, and a `dependencies` entry on it |
| A user-facing choice | a label if it decides **which policies are placed** (any number of states); config if it is only **read during enforcement** |
| A credential | never in values: a `configSecretRef` to a Secret created out of band |

Tier follows the operator catalog: `stable` for `redhat-operators` and for configuration with no
operator, `certified` for `certified-operators`, `community` for `community-operators`. Never
hand-write a policy directory or register it anywhere; a directory with `kustomization.yaml` under
`policies/<tier>/` is discovered automatically.

If the request leaves a real design choice open (which clusters, which states, what the user
configures), ask before scaffolding. Otherwise follow the repository's existing pattern for the
nearest similar component, and name it as the precedent.

## 2. Research before writing

With cluster access:

```bash
oc get packagemanifest <pkg> -o jsonpath='{.status.catalogSource}{"\n"}{range .status.channels[*]}{.name}{" "}{.currentCSV}{"\n"}{end}'
oc get packagemanifest <pkg> -o jsonpath='{.status.channels[0].currentCSVDesc.installModes}'
oc explain <kind>.spec --recursive | head -80
```

- `installModes` with `AllNamespaces: false` means OwnNamespace: pass `--namespace-scoped`.
- Take every field name from `oc explain`, never from memory or from another version's docs.

Without cluster access, write the policy and list every unverified field name and install mode in
your summary.

## 3. Scaffold

Run the generator before writing any file, even when the policy looks simple enough to write by
hand. It produces the `kustomization.yaml` marker that discovery needs, a consistent
`policy-generator-config.yaml` entry, placement and README, and with `--add-to-autoshift` the
values labels. Hand-written directories drift from all of those. Then edit what it generated.

```bash
./scripts/generate-operator-policy.sh <component> <package> --channel <channel> \
  --namespace <ns> [--namespace-scoped] [--source <catalog>] [--short-name <abbr>] --add-to-autoshift
./scripts/generate-policy.sh <name> --dir policies/<tier>/<component> --target <hub|spoke|both|all> \
  [--dependency <component>-operator-install]
```

`--short-name` keeps `policy-<name>-operator-install` within the name limit. Read what was generated
before changing it; [layout](references/layout.md) explains each file.

## 4. Write the manifests

Read [patterns](references/patterns.md) for the code shapes and
[acm-templates](references/acm-templates.md) for what each engine provides. The rules that
matter most:

1. **Local templating by default.** Use `{{hub ... hub}}` only to lift values that live on the hub
   (rendered config, labels, another cluster's objects), each on its own line, then hand them to
   local templates.
2. **Fail loudly on missing required input.** A ConfigurationPolicy that renders nothing reports
   Compliant. Read required config with `fromConfigMap`, check required keys and call `fail`. Do not
   mask a required read with `| default dict`.
3. **Gate with placement, not with an `if` on the same label** inside the template.
4. **Pick the compliance type from what must happen on removal.** `musthave` never removes a field
   and appends to lists; when a value must be able to change or disappear, use `mustonlyhave`
   (read-modify-write if another controller owns the object).
5. **Inform checks live in `test/`** as their own policy entry. Never a metadata-only `musthave`
   under enforce: it creates empty placeholders.
6. **One object, one template**, and wrap an all-conditional list key in its condition.
7. **Removal is explicit.** Leave `pruneObjectBehavior` unset (or `None`) so unplacing a policy
   deletes nothing. Teardown goes through the label's `uninstall` value where the policy has one. Use
   `DeleteIfCreated` only when the user asks for it, and say what it deletes (a MachineConfig
   deletion reboots the pool).
8. **Hub lookups outside the policy namespace** need `hubTemplateOptions.serviceAccountName:
   autoshift-policy-service-account` on the policy entry.
9. **Whitespace**: `{{-` at the content's indentation, `autoindent` on multi-line output, quoted
   `toInt`/`toBool`/`toLiteral`.

## 5. Wire values and tests

- Declare every new `autoshift.io/<key>` and `config.<key>` in
  `autoshift/values/clustersets/_example.yaml` (or a `clusters/_example*.yaml` for per-cluster
  values), uncommented, so the suite renders the branch. Gate label and config key share one
  spelling: the directory name.
- A new `| default "literal"` in a local template needs the value set in an example file; the suite
  strips quoted defaults on purpose.
- Every `lookup`, `fromConfigMap` or `fromSecret` of an object the suite does not have needs a stub
  in `tools/testdata/` (flat files; Secrets as base64 `data:`; namespaced objects with
  `metadata.namespace`; short low-entropy fake values).
- Write the policy `README.md`: what it does, its labels and config, its dependencies, and its
  pitfalls stated in the present tense.

## 6. Run the gates

```bash
make test                       # always; add -count=1 to a direct go test after editing YAML only
make verify                     # when README.md, docs/ or a policy README changed
```

Report each gate as passed, failed (with the error) or skipped (with why). If the change touched
`autoshift/values/`, `make test` covers the top-level chart. Then review the change against the
`autoshift-review` skill if it is installed.

## 7. Summarize

List the files created and changed, the labels and config keys a user sets (with an example values
snippet in block YAML), the dependency order, what turning the label off leaves behind and the
command or `uninstall` value that removes it, the gate results, and what remains unverified until it
runs on a cluster. Draft a commit message; do not commit unless asked.
