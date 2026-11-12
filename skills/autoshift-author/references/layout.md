# Policy directory layout

```
policies/<tier>/<component>/
  kustomization.yaml            marker: discovered as a PolicyGenerator policy
  policy-generator-config.yaml  the policy graph: names, dependencies, placement, remediation
  placement.yaml                Placement predicate, written in full
  placement-<thing>.yaml        extra placements, one per gate
  README.md                     required
  manifests/                    enforced content; each file becomes a ConfigurationPolicy
    namespace.yaml
    operator.yaml               OperatorPolicy, or operator-install/kustomization.yaml
  test/                         inform-only checks, each its own policies[] entry
```

- `manifests/` is usually referenced as a directory, so a new file there is picked up with no edit to
  `policy-generator-config.yaml`.
- `${POLICY_NAMESPACE}`, `${REMEDIATION}`, `${EVAL_COMPLIANT}`, `${EVAL_NONCOMPLIANT}` and
  `${CLUSTER_SET_SUFFIX}` are substituted before the build. They belong in
  `policy-generator-config.yaml` and placement files, never in `manifests/`.
- Every ConfigurationPolicy keeps `evaluationInterval` with `compliant` and `noncompliant` as
  literals (PolicyGenerator injects `${EVAL_*}`).
- Four Helm holdouts keep the older chart shape (`cluster-config-maps`, `cluster-labels`,
  `openshift-gitops`, `policy-foundation`). Do not add new ones.

## Names

| Thing | Name |
|---|---|
| Operator install policy | `policy-<component>-operator-install` |
| Its placement | `placement-policy-<component>-operator-install` |
| Other policy | `policy-<component>-<thing>` |
| Its placement file | `placement-<thing>.yaml` |
| Its Placement resource | `placement-<component>-<thing>` |
| Enable label | `autoshift.io/<component>` |
| Operator labels | `<component>-subscription-name`, `-channel`, `-source`, `-source-namespace`, `-version` |
| Config key | `config.<component>`, same spelling as the directory |

`<namespace>.<policy-name>` must stay within 63 characters; the suite checks it. A rename carries the
placement file and Placement resource with it.

## Operator install component

Operator policies call the shared chart in `components/operator-install/`, which passes values
through verbatim. ACM-specific logic (hub templates, rendered-config reads, version resolution)
goes in the caller's `valuesInline`, never in the shared chart. Copy the config-versions block from
an existing caller such as `policies/stable/quay`. A multi-line block of `{{hub- ... hub}}` lines in
`valuesInline` is written `>-`, not `|-`.

## Placement

```yaml
predicates:
  - requiredClusterSelector:
      labelSelector:
        matchExpressions:
          - key: autoshift.io/<component>
            operator: In
            values:
              - 'true'
```

A multi-state label gets one placement per policy set, each `In` over the states it covers.
