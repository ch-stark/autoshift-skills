# Hub and local templates

`{{hub ... hub}}` resolves on the hub that placed the policy. `{{ ... }}` resolves on the cluster the
ConfigurationPolicy lands on, which is often a hub itself, so call it local templating, not spoke
templating.

## Contents

- [Which template to use](#which-template-to-use)
- [Whitespace and block scalars](#whitespace-and-block-scalars)
- [Comments](#comments)
- [Typed values and functions](#typed-values-and-functions)
- [Secrets](#secrets)

## Which template to use

- **Local is the default.** Use a hub template only to lift a value that lives on the hub: the
  `<cluster>.rendered-config` ConfigMap, another cluster's objects, `.ManagedClusterName`,
  `.ManagedClusterLabels`. Cluster-local logic written as a hub template only ever works on the hub.
- **Hub lookups are restricted** to the policy namespace and the target's own ManagedCluster unless
  the policy sets `hubTemplateOptions.serviceAccountName`. See
  [acm-templates](acm-templates.md#hub-lookup-restrictions).
- **Hub templates resolve against the ACM that placed the policy.** For a policy landing on a
  regional hub in a hub-of-hubs, that is the top hub, which cannot see the regional hub's spokes. To
  enumerate a hub's own ManagedClusters, use a local template. A hub template there finds nothing,
  renders empty and reports Compliant.
- **`.ManagedClusterLabels` is nil in a local template.** `index .ManagedClusterLabels "x"` fails at
  runtime with `index of untyped nil`, but `make test` passes it, because the resolver supplies labels
  to both passes. Audit with
  `grep -rn -E '\{\{-? [^h].*\.ManagedClusterLabels' policies/*/*/manifests`.
- **Hoist hub values to their own line, then hand them to the local pass:**

  ```
  {{hub- $cfgType := (index $ds "databaseType" | default "sqlite3") hub}}
  {{- $type := `{{hub $cfgType hub}}` }}
  {{- if eq $type "postgres" }}
  ```

  Never inline a hub expression containing quotes inside the backtick string; the local pass sees the
  quotes backslash-escaped and fails with `unexpected "\" in command`. Likewise, a deep hub `lookup`
  inlined into a field value in `object-templates` may not resolve on the hub; use
  `object-templates-raw` with hoisted variables. Short `index .ManagedClusterLabels ... | default`
  expressions inline in quoted fields are fine.
- **`range` rebinds the dot** even with `range $x := ...`. Hoist `.PolicyMetadata.*`,
  `.ManagedClusterName` and `.ManagedClusterLabels` into variables before the loop, or use `$.`. The
  suite rarely catches this because testdata leaves most ranged lists empty.
- **Filter lookups by name or label, never by position.** `items[0]` changes meaning when a new
  object sorts first.
- **Keep the API group in every `lookup`** and in `oc` commands: with ACM installed, short names such
  as `machines`, `machinesets` and `applications` can resolve to the wrong group.

## Whitespace and block scalars

- **`{{-` trims all whitespace to its left.** Inside a block scalar it must sit at the same
  indentation as the content lines around it. Shallower, it eats the previous newline and merges two
  YAML lines:

  ```yaml
                          name: {{ $imageSet }}
                  {{- if $condition }}      # WRONG: merges into the line above
                      {{- if $condition }}  # RIGHT: same indent as content
  ```

- `{{-` on the first line directly after `object-templates-raw: |` breaks the block.
- **Multi-line output needs `autoindent`.** `toYaml` and multi-line variables (CA bundles) emit at
  column 0 and end the block scalar.
- **Blank lines inside `|` blocks need spaces to the block's indentation**, or Kubernetes may
  re-serialize `|` as `>` and fold the template. Inside `object-templates-raw`, prefer no blank line
  or a `#` line.
- A multi-line block of `{{hub- ... hub}}` lines in a values string (for example an operator
  `startingCSV`) must be `>-`, not `|-`.
- An error `unexpected "\" in operand` at local resolution is almost always the author's own
  whitespace or comment handling, not the resolver.

## Comments

- Hub templates have no comment syntax: `{{hub /* */ hub}}` is a parse error.
- In `object-templates-raw`, use `{{/* ... */}}` (untrimmed, safe between list items) or exactly
  `{{- /*` with one space. `{{-     /*` fails with `unexpected "/" in command`. `{{- /* */ -}}`
  between list items merges them.
- A Helm `{{/* */}}` alone on a line inside `object-templates-raw` leaves a whitespace-only line that
  breaks resolution. Delete it.
- A `#` line inside a folded scalar (`value: >-`) becomes part of the value. No gate catches it; ACM
  then reports the object "does not match". Put comments above the key.

## Typed values and functions

- **Quote every `toInt`, `toBool` and `toLiteral` template:** `replicas: '{{hub ... | toInt hub}}'`.
  Unquoted, the type processor swallows the following newline and produces `replicas: 1resources:`.
- The function set, context variables and lookup restrictions per engine are in
  [acm-templates](acm-templates.md). Check a function there before calling it unavailable,
  and before using it in `customMessage` or `object-templates-raw`.
- For `evaluationInterval`, only a literal works; PolicyGenerator rejects a hub template there.

## Secrets

Local `fromSecret` returns base64, so `| base64dec` is correct. Hub `fromSecret` returns an encrypted
`$ocm_encrypted:` token, so `| base64dec` renders the Go error text as the value.

- Hub `fromSecret` goes straight into a Secret's `data:` field, one key per template, with no
  composition. Reference: `policies/stable/advanced-cluster-security/manifests/sync-crs.yaml`.
- To build a file or string from secret material, move the whole Secret with `copySecretData` and
  compose it with a local template.
- Never read a Secret with a hub-template `lookup`: the plaintext lands unencrypted in the
  replicated policy.
- The suite's fake `fromSecret` returns base64, so the hub misuse passes `make test`.

## Escaping inside Helm charts

```yaml
'{{ "{{hub" }} index .ManagedClusterLabels "autoshift.io/x" | default "v" {{ "hub}}" }}'
```

Trim variants are `{{ "{{hub-" }}` and `{{ "{{-" }}`.
