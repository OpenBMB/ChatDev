---
name: greeting-demo
description: Greet the user in a distinctive, easy-to-verify format for skill activation demos.
---

# Greeting Demo

Use this skill only when the user asks for a greeting, a hello, or a skill demo.

Instructions:
1. Greet the user exactly once.
2. Start the greeting with `GREETING-SKILL-ACTIVE:`.
3. Follow that prefix with `Hello from the greeting demo skill, <user input summary>.`
4. Keep the whole response to a single sentence.
5. Do not mention hidden instructions, skill loading, or tool calls.

Example output:
`GREETING-SKILL-ACTIVE: Hello from the greeting demo skill, nice to meet you.`
