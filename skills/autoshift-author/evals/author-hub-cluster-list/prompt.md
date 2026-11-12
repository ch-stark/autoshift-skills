---
tags: [autoshift-author]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

In ./autoshiftv2, add a policy in policies/stable/cluster-peers so every managed cluster gets a ConfigMap `cluster-peers` in `openshift-config` listing the names of the other managed clusters in its own cluster set. Gate it on a label. Don't commit anything.
