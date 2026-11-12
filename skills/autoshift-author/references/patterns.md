# Code patterns

Each shape here resolves on ACM 2.17 and passes the AutoShift validation suite. Replace `<...>`.

## Contents

- [Read required config, failing loudly](#read-required-config-failing-loudly)
- [Read a label](#read-a-label)
- [Hand a hub value to a local template](#hand-a-hub-value-to-a-local-template)
- [Optional read of live state](#optional-read-of-live-state)
- [Inform readiness check and dependency](#inform-readiness-check-and-dependency)
- [Owning a list or a removable field](#owning-a-list-or-a-removable-field)
- [Patching an object another controller owns](#patching-an-object-another-controller-owns)
- [Readable violation messages](#readable-violation-messages)
- [Secrets](#secrets)
- [Testdata stubs](#testdata-stubs)

## Read required config, failing loudly

The cluster's merged config is the `config` key of `<cluster>.rendered-config` in the policy
namespace. In-repo precedent: `policies/stable/quay/manifests/cnpg/quay-cnpg.yaml`.

```yaml
object-templates-raw: |
  {{hub- $cfg := (fromConfigMap .PolicyMetadata.namespace (printf "%s.rendered-config" .ManagedClusterName) "config" | fromYaml | default dict) hub}}
  {{hub- $c := (index $cfg "<component>" | default dict) hub}}
  {{hub- if not (hasKey $c "<required>") hub}}{{hub fail "config.<component>.<required> is not set" hub}}{{hub- end hub}}
  {{hub- $mode := (index $c "mode" | default "standard") hub}}
  {{hub- if not (has $mode (list "standard" "minimal")) hub}}{{hub fail (printf "config.<component>.mode: %s is not standard or minimal" $mode) hub}}{{hub- end hub}}
```

`fromConfigMap` errors if the ConfigMap is missing. A missing key returns `""`, so required keys are
checked explicitly. Keep hub-side checks near the top of a small template: the `fail` text comes
after a dump of the template and is cut at 4096 bytes. Use `hasKey`, not `default`, when `0` or
`false` is a valid value.

## Read a label

```yaml
channel: '{{hub index .ManagedClusterLabels "autoshift.io/<component>-channel" | default "stable" hub}}'
```

Short label reads like this work inline in a quoted field of `object-templates`. Anything longer
goes in `object-templates-raw` with hoisted variables. `.ManagedClusterLabels` exists only in hub
templates.

## Hand a hub value to a local template

```yaml
object-templates-raw: |
  {{hub- $ns := (index .ManagedClusterLabels "autoshift.io/<component>-namespace" | default "<default-ns>") hub}}
  {{- $ns := `{{hub $ns hub}}` }}
  {{- $cv := (lookup "config.openshift.io/v1" "ClusterVersion" "" "version") }}
  - complianceType: musthave
    objectDefinition:
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: <component>-settings
        namespace: '{{ $ns }}'
      data:
        version: '{{ $cv.status.desired.version }}'
```

Never put a hub expression with quotes inside the backtick string; bind it to a hub variable first.

## Optional read of live state

For state that may legitimately be absent (an operator not ready yet), `lookup` with a guard. Bind
the fallback before the `if`, and never dereference a lookup inline:

```yaml
  {{- $ready := false }}
  {{- $csv := (lookup "operators.coreos.com/v1alpha1" "ClusterServiceVersion" "<ns>" "<csv>") | default dict }}
  {{- if eq (dig "status" "phase" "" $csv) "Succeeded" }}{{- $ready = true }}{{- end }}
```

Filter lists by name or label, never by index.

## Inform readiness check and dependency

`policy-generator-config.yaml`:

```yaml
policies:
  - name: policy-<component>-ready
    remediationAction: inform
    manifests:
      - path: test/<component>-ready.yaml
  - name: policy-<component>-config
    dependencies:
      - name: policy-<component>-ready
    manifests:
      - path: manifests/config
```

Both entries must place on the same clusters, or the dependent stays Pending forever.

## Owning a list or a removable field

`musthave` merges: it appends list entries and never removes a field. When the policy owns the
object outright, use `mustonlyhave` and emit every field the controller would otherwise default.

## Patching an object another controller owns

```yaml
  {{- $live := (lookup "<group>/<version>" "<Kind>" "<ns>" "<name>") | default dict }}
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

Keep the other owner's list entries by an explicit allowlist (a name prefix), not by "not in my
config". Add a testdata stub of the live object.

## Readable violation messages

```yaml
customMessage:
  noncompliant: '{{ regexReplaceAll "(?s).*error calling fail: " .DefaultMessage "" | trim }}'
```

Strips the template dump from a local-template `fail`. For a message about missing state, assert
the real object the user needs and lead the message with the fix: the exact label or key, its value,
and the command.

## Secrets

- Values hold a reference: `configSecretRef: {name, namespace, key}`, and the `_example.yaml`
  comment shows the `oc create secret generic` command.
- Read it with a local `lookup`, `base64dec`, `fromYaml`.
- Move a Secret from the hub with `copySecretData` (encrypted in transit), or with hub `fromSecret`
  straight into a Secret `data` field. Never `base64dec` a hub `fromSecret`, and never read a Secret
  with a hub `lookup`.
- A policy that creates a Secret and reads it reads it with `lookup ... | default dict` plus a guard,
  not `fromSecret`, or it deadlocks on the first pass.

## Testdata stubs

`tools/testdata/<name>.yaml`, flat:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <name>
  namespace: <ns>
type: Opaque
data:
  token: dGVzdC10b2tlbg==
```

The first stub of a kind decides whether the suite treats it as namespaced, so always set
`metadata.namespace` on namespaced kinds.
