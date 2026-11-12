---
type: llm
focus: trace
weight: 1
---

The review flags that | default true on suspend turns an explicit suspend: false into true, because Sprig default treats false as empty, so the pruner never runs
