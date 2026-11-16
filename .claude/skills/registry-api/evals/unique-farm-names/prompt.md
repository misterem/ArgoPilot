---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

New requirement from the P1 spec: farm names have to be unique. Creating a farm, or renaming one with PATCH, to a name another farm already has must be rejected. Please implement it in registry-service.
