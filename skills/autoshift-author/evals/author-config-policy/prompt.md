---
tags: [autoshift-author]
max_turns: 60
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

In ./autoshiftv2, add a policy so AutoShift configures chrony on worker nodes. Admins set the NTP servers per cluster set in config, and it only applies where a label turns it on. Don't commit anything.
