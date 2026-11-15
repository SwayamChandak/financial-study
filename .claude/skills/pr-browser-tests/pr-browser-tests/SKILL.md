---
name: pr-browser-tests
description: Produces a complete browser-level test case list (no test code, no test execution) for the code changes on the current branch, whether the change is frontend, backend, or both. Reads the git diff against the base branch plus uncommitted changes, deduces the ideal behavior and output from the code, shows that deduction, asks up to 10 clarifying questions one at a time (each with a recommended answer), then writes a PLAN.md listing every test case needed to cover the change fully: ideal path, edge cases (including RBAC and direct-URL access), performance (measure-only) and volume. Use this whenever the user asks for browser tests, e2e test cases, a test plan, "what should I test for my changes / this PR / this branch", or wants test coverage mapped for a feature or issue, even if they don't say "skill".
---

# PR Browser Tests (test case planning)

Read the changes on the current branch, work out what the feature or fix is supposed to do, and write down the test cases that cover it fully. This applies to frontend changes, backend changes, and changes that span both.

**This skill only plans. It never writes test code and never runs tests.** A separate skill implements and runs the test cases from the plan this skill produces. Do not create spec files, do not install packages, do not start the app, and do not run any test command.

Follow the steps in order. Do not skip the deduction or the interview, and do not invent requirements: if something about expected behavior is not clear from the code, commits, or the developer's answers, ask or flag it.

## Step 1: Collect the changes

Gather all of the following:

1. **Base branch.** Detect it (`main`, `master`, `develop`, or the upstream/default branch). If it is not obvious, ask the user.
2. **Committed changes:** diff of the current branch against the merge base with the base branch (`git diff <base>...HEAD`).
3. **Uncommitted changes:** staged, unstaged, and untracked files (`git diff HEAD`, `git status`).
4. **Context:** commit messages since the base (`git log <base>..HEAD`) and the current branch name.

## Step 2: Read the code and deduce the ideal behavior

Read the changed files in full, not just the hunks, and follow imports and call chains. Classify the change as frontend, backend, or both, then work out what it does and what the ideal output is.

- **Frontend changes:** which routes, pages and components are affected, what the user sees and can do, what states exist (loading, empty, error, success).
- **Backend changes:** which endpoints, queries, serializers, validators, permission checks, background jobs or business rules changed; what request goes in and what response or data should come out; and where that output surfaces in the UI. Trace each backend change to the screens, links, and API routes that expose it.
- **Both:** check that the two sides agree (field names, shapes, error handling, permissions).

For each affected behavior, deduce the ideal output: inputs, expected result, boundaries, error cases, who is allowed to do it. Mark anything the code does not settle as an open question for Step 3.

Then rate your confidence in your understanding of the PR's intent, using the diff, commit messages and branch name. If it is about 50% or lower, stop and ask the user to paste the PR description or ticket text before continuing. Do not guess.

**Show the user a short summary of the deduced behavior** before asking any question: 4-8 bullets covering the change type, affected flows and endpoints, the ideal output you deduced, and the open points you will ask about. Then go straight into the interview.

## Step 3: Interview the developer (maximum 10 questions)

Style: grill-me. Probe for the details the code cannot answer, so the test cases state the right expected results.

Rules:
- Read the code first. Never ask something the code, commits or an earlier answer already settles.
- Ask **one question at a time** and wait for the answer before asking the next.
- Every question includes **your recommended answer**, based on what you read, so the user can reply "yes" or correct it. Format: the question, then `Recommended: <your answer>` and a one-line reason.
- Let the deduction drive the questions. Ask where the ideal output depends on a product decision. Examples of the kind of question to ask:
  - A chart accepts custom date ranges and the range can be very wide: what is the maximum number of x-axis points to show, and how should the data be bucketed (1 per day, 1 per week, 1 per month)?
  - A list or export has no obvious limit: what are the page size, the maximum rows, the sort order, the default filter?
  - A calculation or date field: rounding rules, time zone, behavior at boundaries.
  - A new or changed permission: which roles must be allowed, which denied, and what should a denied user see (redirect, 403 page, hidden data, error message)?
  - Existing data: what should happen to records created before this change?
  - Failure behavior: retries, partial failures, what message is shown.
  - What is explicitly out of scope.
- Stop as soon as you have enough. Fewer than 10 is fine. Never exceed 10.
- **Always ask** (these count toward the 10):
  1. How to log in, including which roles or users are needed (include a user without access when roles or permissions are involved). If the repo has no obvious base URL, API base URL or start command, ask for those here too.
  2. What test data to use and how to get it (seed script, fixtures, existing records, API setup). Include what volume of data is realistic for volume tests.

Never put passwords, tokens or secrets in the plan. Refer to credentials by environment variable name only.

## Step 4: Write the test case list

Write test cases that **cover the change fully**. There is no fixed number: list as many as the change needs, no fewer and no padding. Every test case must trace back to the diff, the deduced behavior, or an interview answer. Merge duplicates, and do not add generic cases that ignore the change.

Do not write test code. Each test case is a description precise enough that another skill can implement it without re-reading the whole diff. Use the format in `references/plan-template.md`: ID, title, category, layer (UI, API or both), role and preconditions, test data, steps, expected result, and what it covers.

Test cases are browser-level, but may combine UI steps with **direct API calls**, for both setup and assertions. Use the UI for what the user sees and does, and API calls to verify data, status codes and response shapes, to create or clean up data, and to test access without going through the UI. Backend-only changes are covered this way: UI paths that exercise the change where they exist, plus API assertions.

Cover these categories (see `references/test-categories.md` for prompts):

- **Ideal working path:** the main flow of the change works as intended, in the UI and in the API response or data behind it.
- **Edge cases:** boundaries, empty and invalid input, error states, permissions, repeat or double actions, back/refresh, and regressions in neighboring behavior. Always include **access-control cases** when the change touches pages, endpoints or data that depend on roles or permissions. For example: a page that no button leads a restricted user to must still be blocked when the user types its URL directly, and the endpoint behind it must also deny that user. State the expected result for both what the user sees (redirect, 403 or not-found page, no restricted data on screen) and what the API returns (status and no restricted data in the body), using the behavior from the code or the user's answer.
- **Performance:** **measure and report timings only. Never define pass/fail thresholds.** Specify which timings to capture (for example page navigation, action-to-visible-result, API response time) and that they are reported, not asserted.
- **Volume:** the change under large data sets or many repeated actions, using the test data approach the user gave. Timings are measure-only. The expected result covers correctness only (e.g. all items rendered or returned, no error shown).

Then build a **coverage matrix** that maps every changed behavior, endpoint, route, role and open decision to the test case IDs that cover it. If anything has no test case, either add one or list it under "Not covered" with the reason. If something cannot be verified in a browser or by API call, or depends on an unanswered question, say so under "Not covered". Do not invent an expected result.

## Step 5: Save the plan

Save one file: `e2e/pr-<branch-name>/PLAN.md`.

- Make the branch name filesystem-safe (replace `/` and other special characters with `-`).
- If the repo's e2e folder lives somewhere else (for example `tests/e2e` or `cypress/e2e`), use that parent instead of `e2e/` and mention it.
- Use `references/plan-template.md` for the structure.

Do not modify application source code or create any other file.

## Final message

Keep it brief: the path of `PLAN.md`, the number of test cases per category, any "Not covered" items, and a note that the plan is ready for the implementing skill. Do not offer to run the tests.
