# ACM runtime semantics

Behavior of Red Hat Advanced Cluster Management 2.17 policies that rendering cannot show. Every item
here was verified on a live hub or in controller source. None of it is caught by the validation
suite.

## Contents

- [complianceType semantics](#compliancetype-semantics)
- [Empty and failing policies](#empty-and-failing-policies)
- [Patching a CR another controller owns](#patching-a-cr-another-controller-owns)
- [Dependencies, teardown and OperatorPolicy](#dependencies-teardown-and-operatorpolicy)
- [Messages](#messages)
- [Stale replicas](#stale-replicas)

## complianceType semantics

| Need | Use | Trap |
|---|---|---|
| Add or merge fields | `musthave` | Never removes anything |
| Removals must take effect, policy owns the whole object | `mustonlyhave` | Must emit every field the controller autofills, or it fights the controller |
| Removals on an object another controller owns | `mustonlyhave` + read-modify-write | See below |
| Delete one list entry | nothing works | `mustnothave` deletes the whole object |
| Assert an object is absent | `mustnothave` | Matches identity, not field values |

- **`musthave` never removes a field.** When values drop a key and the template stops emitting it,
  the live field stays and the policy reports Compliant. Deleting a key stops AutoShift managing the
  field; it does not unset it. Docs must not imply otherwise.
- **`musthave` appends to lists of objects.** Changing one field of an entry adds a second entry;
  the controller may honor either. Use `mustonlyhave` when desired state overrides an existing entry.
- **`mustonlyhave` on a partial object compares the whole object.** Fields left out count as a
  mismatch, so it cannot "just check one field" of a rich CR.
- **One object, one template.** Two `object-templates` entries naming the same kind, name and
  namespace collapse: the first wins and the second is dead. A creating `musthave` beside a pruning
  `mustonlyhave` never prunes. Tell: a single `relatedObjects` entry.
- **An all-conditional list key renders `null`.**

  ```yaml
  volumeMounts:
    {{hub- if $a hub}}
    - name: one
    {{hub- end hub}}
  ```

  With `$a` false this is `volumeMounts: null`, and `musthave` writes the null, clearing the live
  list. Wrap the key itself in the same condition. A grep cannot tell this from a key already inside
  the conditional; read the surrounding block.
- **`musthave` + enforce creates absent objects.** A guard such as `or (empty $mc) ...` meant as "not
  there yet, skip" instead materializes a bare object. Require existence when creation is not the
  intent.
- **A list cannot be asserted to exclude a value.** No complianceType expresses it.

## Empty and failing policies

- **A ConfigurationPolicy that renders no object templates reports Compliant.** Success and a
  silently broken template look identical. The suite fails on a policy empty in every profile, but a
  policy empty only under real cluster data still passes.
- **Fail loudly on missing required input.** `lookup ... | default dict` turns a missing ConfigMap
  into silence. `fromConfigMap` errors and names the object. A missing key is still silent with
  `fromConfigMap` (it returns `""`), so check required keys explicitly and call `fail`.
- **Fail on missing input, not on empty output.** An inform or report policy can legitimately be
  empty, and an assertion-only policy (no `objectDefinition`, only `fail` calls) succeeds by being
  empty.
- **Prefer placement gating.** A policy with its own placement on label X that also wraps its body in
  `if X` applies nothing wherever the `if` is false. Delete the template conditional. An absent
  policy is unambiguous; a present empty one is not.
- **`fail` exists from ACM 2.14.** The message is `template-error; failed to resolve the template`,
  then the whole template, then the text, so for a template over about 4 KB the text is truncated
  away. For a local-template `fail`, strip the dump with:

  ```yaml
  customMessage:
    noncompliant: '{{ regexReplaceAll "(?s).*error calling fail: " .DefaultMessage "" | trim }}'
  ```

  This does nothing for a hub-template `fail`.
- **Resolution is all or nothing per ConfigurationPolicy.** One error, including an unknown
  function, aborts the whole policy; nothing in it is applied. A policy that creates a Secret and
  reads it with `fromSecret` in the same `object-templates-raw` deadlocks on first pass. Read it
  with `lookup ... | default dict` and guard on the value.
- **Never assert a fake object to force NonCompliant** (for example a metadata-only Deployment that
  cannot be created). The violation names something unrelated to the problem. Assert the real object
  the missing input breaks and explain in `customMessage`.
- **Never use `mustnothave` as a probe.** The root `Policy.remediationAction` overrides children, so
  one console Enforce turns it into a delete of whatever it names.

## Patching a CR another controller owns

```
{{- $live := (lookup "<group>/<ver>" "<Kind>" "<ns>" "<name>") | default dict }}
{{- if not (dig "spec" "" $live) }}
{{- fail "<policy>: <Kind> <name> not found. Refusing to write a partial object." }}
{{- end }}
{{- $spec := $live.spec }}
{{- $_ := set $spec "<field you own>" $desired }}
{{- $obj := set $live "spec" $spec }}
{{- $_ := unset $obj "status" }}
{{- $_ := unset $obj.metadata "managedFields" }}
- complianceType: mustonlyhave
  objectDefinition: {{ $obj | toRawJson }}
```

- The `fail` guard is load-bearing: without it an empty lookup writes a near-empty object.
- **Ownership cannot be inferred from config.** "Keep entries not in my config" also keeps entries
  this policy wrote earlier and has since dropped. Keep the other owner's entries by an explicit
  allowlist (a name prefix), prune the rest, and say so in one comment.
- The guard needs a `tools/testdata/` stub of the live object or the suite fails.
- In-repo references: `policies/stable/cluster-labels/templates/policy-cluster-labels.yaml`,
  `policies/stable/global-observability/manifests/prometheus-prometheus.yaml`.

## Dependencies, teardown and OperatorPolicy

- **A `dependencies` entry resolves against the same cluster's replica.** If the dependency is placed
  on a different set of clusters, the dependent is Pending forever with no error. It can hide when
  one cluster (such as `local-cluster`) is in both sets. Check both placements match.
- **Enforce + `mustnothave` reports Compliant when the delete call returns,** even while the object
  is stuck Terminating. It cannot be its own barrier. Delete with enforce, verify with a separate
  inform `mustnothave`, and depend on the inform one.
- **OperatorPolicy removal ignores operands.** It deletes Subscription, CSV and OperatorGroup and
  reports Compliant while operand CRs are left with no controller. Remove operands in an earlier
  phase. Keep `customResourceDefinitions: Keep`: a `mustnothave` against a kind whose CRD is gone
  reports NonCompliant forever.
- **OperatorPolicy does not flag a missing or unhealthy catalog.** Catalog health needs its own
  inform check on `status.connectionState.lastObservedState: READY`.
- **OwnNamespace-only operators** (for example NFD, NMState, ODF, LVM Storage, Local Storage,
  OpenShift Virtualization, MTV, Ansible Automation Platform, GitLab, ACM) need `targetNamespaces`
  or the CSV fails `UnsupportedOperatorGroup`. AllNamespaces operators must not set it. Confirm with
  `oc get packagemanifest <pkg> -o jsonpath='{.status.channels[0].currentCSVDesc.installModes}'`.
- **Teardown is explicit.** Removal happens only through the `uninstall` label value. A mode change
  must not remove the previous mode's objects automatically.

## Messages

- Compliance messages are cut at 4096 characters (4082 usable), a blind byte slice. Diffs are cut at
  50 lines. Put the fix first in `customMessage`.
- `customMessage` applies only under a parent Policy, and has no `lookup`.
- A message names the exact label or key, the value, and the command that unblocks it. "See the
  README" is not a fix.

## Stale replicas

When a Policy keeps its name but its content changes substantially, the replicated
ConfigurationPolicy in the cluster namespace can keep the old spec and report Compliant. Compare hub
and replica rather than trusting the compliance column; delete the replica
(`oc delete policy <policy-ns>.<name> -n <cluster>`) to force re-creation.
