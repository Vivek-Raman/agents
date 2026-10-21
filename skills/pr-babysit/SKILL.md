---
name: pr-babysit
description: Monitor a GitHub pull request, address review feedback, handle CI failures, and keep watching until it closes or needs user input. Use when asked to monitor a PR, watch CI, or handle PR feedback.
---

# PR babysitter

Keep working on an open PR until it is merged or closed, or progress needs a user decision. Treat a green, mergeable PR as a status update, not a reason to stop watching.

## Choose GitHub access

Use the harness' GitHub tooling when it is available. Use its native PR monitoring or wake mechanism if it has one, and use its operations to read PR state, checks, comments, review threads, and mergeability, then reply, resolve threads, rerun checks, and push changes as needed.

If the harness exposes no usable GitHub tooling, use the `gh` CLI. Read [GitHub CLI fallback](references/github-cli-fallback.md) before making `gh` API calls. Do not create a local watcher script or a detached polling process.

Accept the current branch's PR, a PR number, or a PR URL. If no PR is given, infer it from the current branch.

## Work loop

1. Read the PR's open or closed state, current head SHA, mergeability, review decision, checks, published comments, and unresolved review threads. Ignore pending reviews and their unpublished comments.
2. Handle unaddressed review feedback before flaky CI reruns.
   - For actionable feedback, make the smallest correct change, commit and push it, reply with a short explanation, then resolve the thread.
   - For questions or declined suggestions, reply with the reasoning, then resolve the thread.
   - Treat comments from human reviewers and bots the same way. Prefix automated replies with `[agent]: `.
3. Diagnose failed checks from their job logs.
   - Fix and push failures clearly caused by the PR.
   - Rerun likely flaky or external failures at most three times per head SHA.
   - Do not change unrelated tests, CI settings, dependencies, or infrastructure to turn an external failure green.
4. After each push, reply, thread resolution, or rerun, refresh the PR state and continue monitoring.
5. Stop only when the PR is merged or closed, or when the task needs user help. Report a persistent external CI failure, exhausted retry budget, missing permission, unrelated local changes, or a product decision that cannot be inferred safely.

Use the harness' monitoring feature for ongoing work. If only `gh` is available, take fresh snapshots with it at a reasonable cadence and keep the active session attached. Do not leave a background watcher behind.

## Safety and scope

- Work only on the PR head branch. Check for unrelated local changes before editing and ask the user if you find any.
- You may push fixes to the PR branch, reply to review comments, resolve addressed threads, and rerun likely flaky checks within the retry limit.
- Do not close, reopen, mark ready or draft, force-push, or push to another branch unless the user asks.
- Use commit messages such as `fix: address PR review feedback (#<n>)` or `fix: CI failure on PR #<n>`.

Read [CI and review heuristics](references/heuristics.md) when classifying a failure or deciding whether to fix, rerun, or ask the user.

## Reporting

Send brief progress updates when the PR state changes. When work stops, report the head SHA, check status, mergeability, review items addressed, commits pushed, retry count, and any blocker.
