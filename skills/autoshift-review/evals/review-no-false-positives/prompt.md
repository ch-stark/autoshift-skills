---
tags: [autoshift-review]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Quick review of policies/stable/console-banner please, I think it is fine but want a check. The autoshift.io/console-banner label and config.console-banner (text and linkUrl, both set) are already declared in _example.yaml and make test passes.

Input files: policies/stable/console-banner/policy-generator-config.yaml, policies/stable/console-banner/placement.yaml, policies/stable/console-banner/manifests/banner.yaml
