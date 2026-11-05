---
name: fix-tests
description: Systematically fix all failing tests after business logic changes or refactoring
argument-hint: what tests or modules to focus on
---

# Fix Tests

## User Arguments

User can provide to focus on specific tests or modules:

```
$ARGUMENTS
```

If nothing is provided, focus on all tests.

## Context

After business logic changes, refactoring, or dependency updates, tests may fail because they no longer match the current behavior or implementation. This command orchestrates automated fixing of all failing tests using specialized agents.

## Goal

Fix all failing tests to match current business logic and implementation.

## Important Constraints

- **Focus on fixing tests** - avoid changing business logic unless absolutely necessary
- **Preserve test intent** - ensure tests still validate the expected behavior
- "Analyse complexity of changes" - 
  - if there 2 or more changed files, or one file with complex logic, then **Do not write tests yourself** - only orchestrate agents!
  - if there is only one changed file, and it's a simple change, then you can write tests yourself.

## Workflow Steps

### Preparation

1. **Read sadd skill if available**
   - If available, read the sadd skill to understand best practices for managing agents

2. **Discover test infrastructure**
   - Read @README.md and package.json (or equivalent project config)
   - Identify commands to run tests and coverage reports
   - Understand project structure and testing conventions

3. **Run all tests**
   - Execute full test suite to establish baseline

4. **Identify all failing test files**
   - Parse test output to get list of failing test files
   - Group by file for parallel agent execution

### Analysis

5. **Verify single test execution**
   - Choose any test file
   - Launch haiku agent with instructions to find proper command to run this only test file
     - Ask him to iterate until you can reliably run individual tests
   - After he complete try running a specific test file if it exists
   - This ensures agents can run tests in isolation

### Test Fixing

6. **Launch `developer` agents (parallel)**
   - Launch one agent per failing test file
   - Provide each agent with clear instructions:
     * **Context**: Why this test needs fixing (business logic changed)
     * **Target**: Which specific file to fix
     * **Guidance**: Read TDD skill (if available) for best practices how to write tests.
     * **Resources**: Read README and relevant documentation
     * **Command**: How to run this specific test file
     * **Goal**: Iterate until test passes
     * **Constraint**: Fix test, not business logic (unless clearly broken)

7. **Verify all fixes**
   - After all agents complete, run full test suite again
   - Verify all tests pass

8. **Iterate if needed**
   - If any tests still fail: Return to step 5
   - Launch new agents only for remaining failures
   - Continue until 100% pass rate

## Success Criteria

- All tests pass ✅
- Test coverage maintained
- Test intent preserved
- Business logic unchanged (unless bugs found)

## Agent Instructions Template

When launching agents, use this template:

```
The business logic has changed and test file {FILE_PATH} is now failing.

Your task:
1. Read the test file and understand what it's testing
2. Read TDD skill (if available) for best practices on writing tests.
3. Read @README.md for project context
4. Run the test: {TEST_COMMAND}
5. Analyze the failure - is it:
   - Test expectations outdated? → Fix test assertions
   - Test setup broken? → Fix test setup/mocks
   - Business logic bug? → Fix logic (rare case)
6. Fix the test and verify it passes
7. Iterate until test passes
```
