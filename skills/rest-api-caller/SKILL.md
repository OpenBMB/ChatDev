---
name: rest-api-caller
description: Call REST APIs from Python, parse JSON responses, and report the useful fields back to the user.
allowed-tools: run_python_script execute_code
---

# REST API Caller

Use this skill when the user wants data fetched from an HTTP API, especially a REST endpoint that returns JSON.

This skill is intended for:
- public GET endpoints
- authenticated APIs using tokens or API keys
- endpoints where the user specifies headers, query params, or environment variable names

Requirements:
- The agent should have access to `run_python_script` or `execute_code`.

Workflow:
1. Activate this skill when the task requires calling an API.
2. If you need examples, call `read_skill_file` for `references/examples.md`.
3. Write a short Python script that performs the request.
4. Prefer the `requests` library if available in the environment.
5. Prefer `run_python_script`; if it is unavailable, fall back to `execute_code`.
6. Parse the response and print only the fields needed for the final answer.
7. Summarize the API result clearly for the user.

Rules:
1. Do not invent API responses. Run the request first.
2. For JSON APIs, parse JSON and extract the relevant fields instead of dumping the whole payload unless the user asks for the raw body.
3. If the user provides an environment variable name for a token or API key, read it from `os.environ` inside the script.
4. If the endpoint requires auth and no credential source is provided, say what is missing.
5. If the request fails, report the HTTP status code or error message clearly.
6. Do not claim there is a generic execution-environment issue unless the tool call actually returned one.

Demo endpoint:
- `GET https://official-joke-api.appspot.com/random_joke`

Expected behavior for the demo endpoint:
- Fetch one random joke
- Return the setup and punchline in a readable format
