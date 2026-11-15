# Plan template for `e2e/pr-<branch>/PLAN.md`

This file is the only output of the skill. Another skill will implement and run the test cases, so each case must be precise and self-contained. Fill every section; write "None" where empty. Never include passwords, tokens or secrets; name environment variables only.

```markdown
# Test plan: <branch name>

## Understanding of the PR
<2-4 sentences: what changes, frontend / backend / both, affected screens, flows and endpoints. Note the source: commits, branch name, pasted PR description.>

## Deduced behavior
<4-8 bullets: the ideal output deduced from the code, including any corrections from the developer.>

## Setup
- Base branch: <name>
- Base URL / API URL / start command: <values, as given by the developer>
- Login: <how, which roles, including a user without access where relevant>. Credentials and tokens come from env vars: <VAR_NAMES>
- Test data: <approach from the interview, including realistic volume>

## Decisions from the interview
| # | Question | Answer |
|---|----------|--------|

## Test cases

### TC-01: <short title>
- Category: <Ideal path | Edge case | Access control | Performance | Volume>
- Layer: <UI | API | both>
- Role / preconditions: <who is logged in, state required>
- Test data: <what is needed>
- Steps:
  1. <action>
  2. <action>
- Expected result: <what the UI shows and/or what the API returns: status, shape, values>
- Measure (performance and volume only): <timings or counts to capture and report; no thresholds>
- Covers: <diff area, file or endpoint, or interview answer #>

<repeat for every test case, numbered TC-02, TC-03, and so on>

Performance and volume cases record timings only; no thresholds are defined.

## Coverage matrix
| Changed behavior / endpoint / route / role / decision | Test cases |
|-------------------------------------------------------|------------|

## Not covered / limits
<Anything not verifiable by browser or API, cases left out, unanswered questions, with the reason for each.>
```
