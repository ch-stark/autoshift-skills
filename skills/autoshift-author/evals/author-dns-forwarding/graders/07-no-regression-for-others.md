---
type: llm
focus: trace
weight: 1
---

Clusters that do not opt in to forwarding (no gating label or no forwarding config) keep the current tolerations behavior: the change does not make the existing policy, which is placed on every cluster, report NonCompliant or fail on clusters without the new config
