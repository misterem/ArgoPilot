---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

The spec got an addition for the plots list: GET /v1/plots now takes an optional crop_id query param and only returns plots growing that crop. It should work together with the existing farm_id filter. Can you add it in registry-service?
