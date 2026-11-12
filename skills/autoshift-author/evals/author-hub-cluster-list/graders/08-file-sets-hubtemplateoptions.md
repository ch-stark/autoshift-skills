---
type: regex
target:
  source: file
  path: autoshiftv2/policies/stable/cluster-peers/policy-generator-config.yaml
pattern: "serviceAccountName: autoshift-policy-service-account"
match: contains
weight: 1
---

policy-generator-config.yaml sets hubTemplateOptions.serviceAccountName to autoshift-policy-service-account
