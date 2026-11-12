---
tags: [autoshift-review]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Can you check policies/stable/registry-creds/manifests/creds.yaml? It is a new policy for our AutoShift fork and the validation suite is green, but I want a second pair of eyes before it hits the hub.

Input files: policies/stable/registry-creds/policy-generator-config.yaml, policies/stable/registry-creds/manifests/creds.yaml
