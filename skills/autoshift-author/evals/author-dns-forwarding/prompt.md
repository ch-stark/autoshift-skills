---
tags: [autoshift-author]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

In ./autoshiftv2, extend the openshift-dns policy so admins can set DNS forwarding zones (zone names and upstream servers) per cluster set in config. When an admin removes a zone from config, the cluster must stop forwarding it. Don't commit anything.
