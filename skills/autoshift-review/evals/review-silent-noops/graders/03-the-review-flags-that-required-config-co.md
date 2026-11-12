---
type: llm
focus: trace
weight: 1
---

The review flags that required config (config.ntp-sync.servers) is read through lookup with default dict, so a missing ConfigMap or key renders nothing instead of failing
