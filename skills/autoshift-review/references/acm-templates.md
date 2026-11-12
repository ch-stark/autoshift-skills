# ACM 2.17 policy template runtime

What Red Hat Advanced Cluster Management 2.17 actually runs when it resolves a policy template.
Sourced from code, not documentation: governance-policy-propagator and config-policy-controller at
`release-2.17`, and the go-template-utils `v7.2.0` both build with. The skill repository's `shared/`
directory holds the baseline (`acm-baseline.yaml`), the function list (`acm-functions.tsv`) and the
source excerpts this page is written from (`acm-runtime-excerpts.txt`); its tests check every
function named here against the list.

## Contents

- [Two engines](#two-engines)
- [Context variables](#context-variables)
- [ACM functions](#acm-functions)
- [Sprig functions](#sprig-functions)
- [Hub lookup restrictions](#hub-lookup-restrictions)
- [Where the validation suite differs](#where-the-validation-suite-differs)

## Two engines

| | Hub template `{{hub ... hub}}` | Local template `{{ ... }}` |
|---|---|---|
| Resolved by | governance-policy-propagator, on the hub that placed the policy | config-policy-controller, on the cluster the policy lands on |
| When | at propagation, per managed cluster | at every evaluation |
| Reads | the placing hub's API, restricted (see below) | the local cluster's API, through the controller's own service account |
| Re-evaluates on change | watches every object it read | watches every object it read when `evaluationInterval` is `watch` |
| Error result | replicated policy reports `template-error`; nothing in it applies | that ConfigurationPolicy reports NonCompliant; nothing in it applies |

One unresolvable expression, including a call to an undefined function, fails the whole policy
template, not just that line.

## Context variables

| Engine | Variable | Contents |
|---|---|---|
| hub | `.ManagedClusterName` | target cluster name |
| hub | `.ManagedClusterLabels` | target ManagedCluster labels. Populated only when the template text contains `ManagedClusterLabels` |
| hub | `.PolicyMetadata` | the root Policy's `name`, `namespace`, `labels`, `annotations` |
| local, `object-templates` only | `.ObjectName`, `.ObjectNamespace`, `.Object` | set for entries expanded by `namespaceSelector` or `objectSelector`; `.Object` is the live object. `object-templates-raw` resolves with no context at all |
| local | none of the hub variables | `.ManagedClusterLabels` is nil: `index .ManagedClusterLabels "x"` fails with `index of untyped nil` |
| `customMessage` | `.DefaultMessage` | the message the controller would have written |
| `customMessage` | `.Policy` | the ConfigurationPolicy as a map; with `evaluationInterval: watch`, `status.relatedObjects[].object` holds the full live object |

`customMessage` templates get Sprig only: no `lookup` or other ACM function. They apply only when
the ConfigurationPolicy has a parent Policy.

## ACM functions

| Function | Engine | Behavior worth knowing |
|---|---|---|
| `lookup apiVersion kind ns name [labelSelector...]` | both | Missing object: empty map, no error. Kind not served by the API: error. `name` `""` lists. Always keep the API group in `apiVersion` |
| `fromConfigMap ns name key` | both | Missing ConfigMap: error naming it. Missing key: `""`, silently |
| `fromSecret ns name key` | both | Missing Secret: error. Missing key: `""`, silently. Local returns base64. Hub returns an encrypted `$ocm_encrypted:` token, valid only as a whole Secret `data` value |
| `copySecretData ns name` | both | Whole `data` map; on the hub it is encrypted. The way to move a Secret hub to cluster |
| `copyConfigMapData ns name` | both | Whole `data` map |
| `protect value` | hub | Encrypts a value. Only with encryption enabled on the hub; elsewhere errors |
| `fromClusterClaim name` | local | Missing claim: error |
| `lookupClusterClaim name` | local | Missing claim: empty |
| `getNodesWithExactRoles roles...`, `hasNodesWithExactRoles roles...` | local | Node selection by role set |
| `skipObject [bool]` | local, `object-templates` only | Skips the current object. Not defined in `object-templates-raw` (use `if` there) |
| `toInt`, `toBool`, `toLiteral` | both | Typed output. Quote the whole template; unquoted, the type processor eats the next newline |
| `atoi` | both | String to int |
| `autoindent` | both | Indents multi-line output to the column the template sits at. Required for `toYaml` and any multi-line value inside a block scalar |
| `indent n` | both | ACM override of the Sprig function |
| `base64enc`, `base64dec`, `b64enc`, `b64dec` | both | ACM implementations |
| `fromYaml`, `toYaml`, `fromYAML`, `toYAML` | both | ACM implementations |
| `fromJSON`, `toJSON`, `toRawJSON`, `mustFromJSON`, `mustToJSON`, `mustToRawJSON` | both | Aliases of the Sprig JSON functions |

## Sprig functions

Every Sprig v3 function except `env` and `expandenv`, which are replaced by a function that returns
`function '<name>' is considered a security risk`. That includes everything ACM 2.15 and earlier
lacked: `trimPrefix`, `trimSuffix`, `compact`, `toString`, `uniq`. Commonly useful:

- `fail msg`: aborts resolution with `msg`. The reported message is the template dump followed by
  the text, cut at 4096 bytes. For a local `fail`, recover the text in `customMessage` with
  `{{ regexReplaceAll "(?s).*error calling fail: " .DefaultMessage "" | trim }}`.
- `dig k1 k2 ... default map`: nil-safe nested read.
- `default`: treats `0`, `false`, `""`, empty maps and lists as empty and replaces them. Use
  `hasKey` when zero or false is a legitimate value.
- `required`, `tpl` and `include` are Helm functions, not Sprig: they do not exist at runtime.

## Hub lookup restrictions

Without `hubTemplateOptions.serviceAccountName` on the Policy, a hub template may only read:

- objects in the root policy's own namespace (an empty namespace argument defaults to it), and
- the target's own `ManagedCluster`.

Anything else fails with `the namespace argument is restricted to <policy-namespace>` or
`lookup of cluster-scoped resource '<kind>/<name>' is not allowed`. Listing ManagedClusters, or
reading a Secret or ConfigMap in another namespace, needs a service account with RBAC for it. In
AutoShift that is `hubTemplateOptions.serviceAccountName: autoshift-policy-service-account` in the
policy's `policy-generator-config.yaml` entry.

## Where the validation suite differs

AutoShift's `make test` resolves templates with go-template-utils as pinned in `tools/go.mod`, with
none of the runtime options set. So it:

- does not apply the hub lookup restriction: a cross-namespace hub `lookup` without
  `hubTemplateOptions` passes the suite and fails on the hub;
- has no `skipObject` and no `protect`: either fails resolution in the suite;
- gives local templates `.ManagedClusterLabels`, which the runtime does not;
- returns base64 from a hub `fromSecret`, where the runtime returns an encrypted token;
- deletes non-empty quoted `| default "x"` strings before the local pass (a deliberate check that
  examples declare every value).

Check those by reading, not by the suite.
