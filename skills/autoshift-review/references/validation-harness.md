# What the validation suite catches and misses

`make test` (Go, under `tools/`) renders every policy chart, resolves hub and local templates against
synthetic values and `tools/testdata/` stubs, checks the label contract, flags empty
ConfigurationPolicies, checks policy name lengths and `versions.yaml`, runs a mutation sweep, and
renders the top-level `autoshift/` chart against each values profile. CI adds `govulncheck`; the
pre-commit hook adds gitleaks and `helm lint`.

## It validates rendering, not enforcement

Green does not prove any of these. Review them by reading:

- every item in [acm-runtime](acm-runtime.md)
- hub `fromSecret | base64dec` (the fake returns base64, so it passes)
- `.ManagedClusterLabels` in a local template (the resolver supplies labels to both passes)
- `dependencies` across placements (every policy resolves regardless of dependencies)
- hub-of-hubs `managedHub` topology
- the real Config Management Plugin substitution of `${POLICY_NAMESPACE}`, `${REMEDIATION}`,
  `${EVAL_COMPLIANT}`, `${EVAL_NONCOMPLIANT}` and `${CLUSTER_SET_SUFFIX}`. The suite substitutes on its
  own. A new token must be added to the plugin in both
  `openshift-gitops/templates/policy-generator-cmp.yaml` and
  `policies/stable/openshift-gitops/templates/policy-gitops-cmp-plugin.yaml`, to
  `scripts/render-policygen-charts.sh`, `scripts/pg-render.sh`, `autoshift-app-set.yaml` and the
  harness, or it leaks as a literal into the cluster
- OLM install modes, CRD field names (check with `oc explain`), and the final applied object

## It renders only what the examples declare

- **A branch gated on a key no `_example*.yaml` sets never renders,** so it is never checked. A
  commented-out example key counts as unset. New branches that read a Secret, ConfigMap or trust
  bundle need the key declared, not commented out.
- **Loops over ManagedClusters usually iterate nothing,** because testdata stubs few clusters.
  Bugs in the loop body are invisible.
- Profiles: the primary hub plus one per `autoshift/values/clusters/_example-cluster-install-*.yaml`.

## `| default "literal"` is stripped before the local pass

A blind text scan between the hub and local passes deletes every non-empty quoted default
(`| default "x"`, `| default 'x'`) anywhere in the hub-resolved document.

- Survives: `| default dict`, `| default list`, `| default ""`, `| default $var`, `| default 1`.
- Hub-template defaults already resolved, so they are unaffected, unless the hub pass errored.
- Consequence: a key relying on a quoted default must be set in the matching `_example*.yaml`, or
  it resolves to `<no value>` and fails. That is intended: examples are the schema.
- Safe idiom: bind the lookup to a variable, set the fallback as its own variable before an `if`,
  never dereference a lookup inline.

## Testdata stubs

- **`tools/testdata/` is the API registry.** Flat `.yaml` files, no subdirectories. A `lookup` of a
  kind with no stub is a hard failure, not an empty result. A known kind with a missing name returns
  empty, which is why some stubs use a deliberately non-matching name.
- Namespaced-ness is inferred from the first stub of that kind: a namespaced stub without
  `metadata.namespace` makes every namespaced lookup miss.
- Secret stubs read through `.data` or `fromSecret` need base64 `data:`, not `stringData:`. Nothing
  converts it.
- Fake credential values must be short and low-entropy (`test-token`, `dGVzdC10b2tlbg==`). The
  gitleaks rule `kubeconfig-tokens` matches `(token|kubeconfig|bearer)\s*[:=]\s*[a-zA-Z0-9\-_.]{20,}`
  and testdata is not allowlisted; `make test` does not run gitleaks.
- A policy reading an object another policy creates needs that object stubbed.

## Reading failures

- `template: tmpl:NN: bad character U+002D '-'` at a `{{hub-` line means the hub pass failed and the
  local pass saw raw hub delimiters. The real error is elsewhere in the log:
  `grep -oE 'error: [^,]{0,220}' <log> | sort -u`.
- `function "hub" not defined` means a hub expression reached the local parser unresolved.
- `go test` does not rebuild its cache on YAML changes. Use `-count=1` when testing a manifest edit.

## Rules for changes to the harness

- `tools/internal/resolver/e2e_test.go` is never edited to make a policy pass. Fix the policy or add
  a stub.
- An exemption or skip added to a check must be proven by deleting the thing it keys on and watching
  the check fail. A placement-aware skip and a regex that matched the word "fail" in a comment both
  once silenced checks wholesale.
- There is no empty-policy allowlist. Fix the policy.
- A mutation case that avoids a code path to pass hides a hole in that path.

## Top-level chart

`autoshift/templates/_validate-*.tpl` runs only in `TestAutoShiftChart_ValuesProfiles`. A hand
render inspects output; it is not coverage. Use a release name of 11 characters or fewer
(`helm template autoshift ./autoshift ...`): the default `release-name` trips the naming validator.
The validator deep-checks only known config keys; a new `config.<component>` block passes through
unchecked.
