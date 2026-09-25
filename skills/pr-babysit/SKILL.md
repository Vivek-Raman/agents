---
name: pr-babysit
description: Babysit a GitHub pull request after creation by continuously polling review comments, CI checks/workflow runs, and mergeability state until the PR is merged/closed or user help is required. Address and resolve all review comments (freely replying to human and bot comments on GitHub), diagnose CI failures, retry likely flaky failures up to 3 times, auto-fix/push branch-related issues, and keep watching open PRs so fresh review feedback is surfaced promptly. Use when the user asks to monitor a PR, watch CI, handle review comments, or keep an eye on failures and feedback on an open PR.
---

# PR Babysitter

## Objectives
Babysit a PR persistently to achieve these core goals:

1. **Address and resolve all review comments**: Every review comment and review thread (from both human reviewers and AI review bots) must be addressed and resolved. This includes patching code for actionable requests, freely replying to comments on GitHub with explanations, answers, or rationale, and marking the review threads as resolved on GitHub.
2. **Keep CI green**: Diagnose CI failures, auto-fix branch-related issues, and retry likely flaky failures (up to 3 times per SHA).
3. **Ensure merge readiness**: Keep watching until the PR is clean, mergeable, and ready to merge (or merged/closed).

Babysit persistently until one of these terminal outcomes occurs:

- The PR is merged or closed.
- A situation requires user help (for example persistent CI infrastructure outages, repeated flaky failures after retry budget is exhausted, permission problems, or genuine product/architectural ambiguity that cannot be resolved safely).
- Progress milestone: the PR is currently green + mergeable + all comments addressed and resolved. Treat this as a progress state, not a watcher stop, so late-arriving review comments are still surfaced promptly while the PR remains open.

Do not stop merely because a single snapshot returns `idle` while checks are still pending or comments are unresolved.

## Inputs
Accept any of the following:

- No PR argument: infer the PR from the current branch (`--pr auto`)
- PR number
- PR URL

## Core Workflow

1. When the user asks to "monitor"/"watch"/"babysit" a PR, start with the watcher's continuous mode (`--watch`) unless you are intentionally doing a one-shot diagnostic snapshot.
2. Run the watcher script to snapshot PR/review/CI state (or consume each streamed snapshot from `--watch`).
3. Inspect the `actions` list in the JSON response.
4. If `process_review_comment` is present or any unresolved review threads exist, inspect all surfaced published review items and threads. All review comments must be addressed and resolved:
   - For actionable code feedback: patch code locally, commit, push, reply to the comment/thread explaining the changes made (referencing the commit), and resolve the review thread on GitHub.
   - For questions, clarifications, suggestions not requiring code changes, or non-actionable comments: freely reply directly to the comment/thread on GitHub with a clear, polite, and constructive response, and resolve the thread once addressed.
5. If `diagnose_ci_failure` is present, inspect failed run logs and classify the failure.
6. If the failure is likely caused by the current branch, patch code locally, commit, and push. Do not patch random flaky tests, CI infrastructure, dependency outages, runner issues, or other failures that are unrelated to the branch.
7. If the failure is likely flaky/unrelated and `retry_failed_checks` is present, rerun failed jobs with `--retry-failed-now`.
8. If both actionable review feedback and `retry_failed_checks` are present, prioritize review feedback first; a new commit will retrigger CI, so avoid rerunning flaky checks on the old SHA unless you intentionally defer the review change.
9. On every loop, look for newly surfaced review feedback before acting on CI failures or mergeability state, then verify mergeability / merge-conflict status (for example via `gh pr view`) alongside CI.
10. After any push, reply, thread resolution, or rerun action, immediately return to step 1 and continue polling on the updated SHA/state.
11. If you had been using `--watch` before pausing to patch/commit/push, relaunch `--watch` yourself in the same turn immediately after the push (do not wait for the user to re-invoke the skill).
12. Repeat polling until `stop_pr_closed` appears or a user-help-required blocker is reached. A green + all comments resolved + mergeable PR is a progress milestone, not a reason to stop the watcher while the PR is still open.
13. Maintain terminal/session ownership: while babysitting is active, keep consuming watcher output in the same turn; do not leave a detached `--watch` process running and then end the turn as if monitoring were complete.

## Commands

Run the watcher script from the skill's `scripts/` directory (e.g. `scripts/gh_pr_watch.py` or `<path-to-skill>/scripts/gh_pr_watch.py` such as `~/.agents/skills/babysit-pr/scripts/gh_pr_watch.py` or `.agents/skills/babysit-pr/scripts/gh_pr_watch.py`):

> **Environment Note**: When working inside `~/Documents/Work` (or any subdirectory), the environment variable `GH_CONFIG_DIR=~/.config/gh-work` is required for all `gh` CLI invocations. The watcher script automatically checks and sets this environment variable.

### One-shot snapshot

```bash
python3 scripts/gh_pr_watch.py --pr auto --once
```

### Continuous watch (JSONL)

```bash
python3 scripts/gh_pr_watch.py --pr auto --watch
```

### Fresh review state snapshot (ignore prior session state)

```bash
python3 scripts/gh_pr_watch.py --pr auto --once --fresh
```

### Trigger flaky retry cycle (only when watcher indicates)

```bash
python3 scripts/gh_pr_watch.py --pr auto --retry-failed-now
```

### Explicit PR target

```bash
python3 scripts/gh_pr_watch.py --pr <number-or-url> --once
```

## Review Comment Handling & Resolution

**Addressing and resolving all review comments is a primary goal of the babysit-pr skill.**

The watcher surfaces review items from:
- PR issue comments
- Inline review comments (via REST and GraphQL `reviewThreads`)
- Review submissions (COMMENT / APPROVED / CHANGES_REQUESTED)

Only act on published feedback. Ignore review submissions in GitHub's `PENDING` state and inline comments attached to those pending reviews.

The watcher surfaces feedback from all human reviewers as well as AI reviewer bots (e.g., `copilot-pull-request-reviewer[bot]`, `chatgpt-codex-connector[bot]`, `claude[bot]`, `gemini-code-assist[bot]`, `coderabbitai[bot]`, `sourcery-ai[bot]`, `qodo-merge[bot]`, etc.).

### Addressing and Replying to Comments

You have full authority to freely reply to comments and review threads on GitHub:

1. **Actionable code suggestions/requests**:
   - Patch code locally.
   - Commit with `fix: address PR review feedback (#<n>)` (or `agent: address PR review feedback (#<n>)`).
   - Push to the PR head branch.
   - Reply to the comment/thread explaining what changes were made and referencing the commit SHA or summary.
   - Resolve the review thread on GitHub.

2. **Questions, clarifications, or non-actionable suggestions**:
   - Reply directly to the comment/thread on GitHub with a clear, polite, and constructive explanation answering the question or detailing why the current approach is preferred.
   - Resolve the review thread on GitHub once addressed.

3. **Attribution**:
   - Prefix automated replies with `[agent]: ` (or `[from agent]: `) so it is transparent that the response was generated by the agent.

4. **Self-authored feedback deduplication**:
   - If the watcher later surfaces your own reply, treat it as already handled and do not reply again.

5. **Already resolved threads**:
   - If a review thread is already marked `isResolved: true` in GitHub, treat it as resolved unless new follow-up comments appear in that thread.

### GitHub CLI / API Commands for Replying & Resolving

- **Reply to an inline review comment thread**:
  ```bash
  gh api repos/<owner>/<repo>/pulls/<pr_number>/comments/<comment_id>/replies -X POST -f body="[agent]: <explanation-and-commit-reference>"
  ```

- **Reply to a general PR issue comment**:
  ```bash
  gh api repos/<owner>/<repo>/issues/<pr_number>/comments -X POST -f body="[agent]: <response>"
  # or
  gh pr comment <pr_number> --body "[agent]: <response>"
  ```

- **Resolve a review thread via GraphQL**:
  ```bash
  gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread {
        id
        isResolved
      }
    }
  }' -F threadId="<thread_id>"
  ```

### State Staleness & Unaddressed Feedback Auto-Recovery
- State files from previous sessions (> 3 minutes inactive) automatically have their "seen" list reset so that unaddressed review feedback (e.g., bot comments or reviewer feedback left unhandled in a prior session) is never silently swallowed.
- The watcher queries GitHub's GraphQL `reviewThreads` API: threads marked `isResolved: true` on GitHub are treated as resolved, while active unresolved threads prevent premature `ready_to_merge` recommendations and keep `process_review_comment` active.
- To explicitly force a clean review state, pass `--fresh` / `--clean-state`.

## CI Failure Classification
Use `gh` commands to inspect failed runs before deciding to rerun (remembering `GH_CONFIG_DIR=~/.config/gh-work` if executing manually under `~/Documents/Work`).

- `gh run view <run-id> --json jobs,name,workflowName,conclusion,status,url,headSha`
- `gh api repos/<owner>/<repo>/actions/runs/<run-id>/jobs -X GET -f per_page=100`
- `gh api repos/<owner>/<repo>/actions/jobs/<job-id>/logs > /tmp/gh-job-<job-id>-logs.zip`
- `gh run view <run-id> --log-failed` as a fallback after the overall workflow run is complete

`gh run view --log-failed` is workflow-run scoped and may not expose failed-job logs until the overall run finishes. For faster diagnosis, poll the run's jobs first and, as soon as a specific job has failed, fetch that job's logs directly from the Actions job logs endpoint. The watcher includes a `failed_jobs` list with each failed job's `job_id` and `logs_endpoint` when GitHub exposes one.

Prefer treating failures as branch-related when failed-job logs point to changed code (compile/test/lint/typecheck/snapshots/static analysis in touched areas).

Prefer treating failures as flaky/unrelated when logs show transient infra/external issues (timeouts, runner provisioning failures, registry/network outages, GitHub Actions infra errors).

Do not attempt to fix flaky/unrelated failures by changing tests, build scripts, CI configuration, dependency pins, or infrastructure-adjacent code unless the logs clearly connect the failure to the PR branch. For flaky/unrelated failures, rerun only when the watcher recommends `retry_failed_checks`; otherwise wait or stop for user help.

If classification is ambiguous, perform one manual diagnosis attempt before choosing rerun.

Read `references/heuristics.md` for a concise checklist.

## GitHub State Mutation Policy

You can read any PR state you need for monitoring. Writes must comply with this policy:

- **Pushes**: You can push to the PR head branch to update the code under review to address review feedback or fix CI failures.
- **Replies & Comments**: You are authorized to freely reply to review comments and review threads on GitHub (from human reviewers and AI bots). Prefix automated replies with `[agent]: ` (or `[from agent]: `) for clarity.
- **Resolving Threads**: You are authorized and expected to resolve review threads on GitHub once the feedback has been addressed (either via code changes or explanatory replies).
- **CI Reruns**: You can trigger failed check reruns for flaky/unrelated failures according to the retry budget.

Unless explicitly instructed by the user, do not:
- Close or reopen PRs.
- Mark PRs as drafts or ready for review.
- Force push destructive history rewrites or push to branches other than the PR head branch.

## Git Safety Rules

- Work only on the PR head branch.
- Avoid destructive git commands.
- Do not switch branches unless necessary to recover context.
- Before editing, check for unrelated uncommitted changes. If present, stop and ask the user.
- After each successful fix, commit and `git push`, reply to the comment/thread, resolve the thread, then resume the watcher.
- If you interrupted a live `--watch` session to make the fix, restart `--watch` immediately after the push in the same turn.
- Do not run multiple concurrent `--watch` processes for the same PR/state file; keep one watcher session active and reuse it until it stops or you intentionally restart it.
- A push is not a terminal outcome; continue the monitoring loop unless a strict stop condition is met.

Commit message defaults:
- `fix: CI failure on PR #<n>` (or `agent: fix CI failure on PR #<n>`)
- `fix: address PR review feedback (#<n>)` (or `agent: address PR review feedback (#<n>)`)

## Monitoring Loop Pattern
Use this loop in a live agent session:

1. Run `--once` (or start `--watch`).
2. Read `actions`.
3. First check whether the PR is now merged or otherwise closed; if so, report that terminal state and stop polling immediately.
4. Check CI summary, new review items, unresolved review threads, and mergeability/conflict status.
5. If there are unaddressed review items or unresolved review threads:
   - For actionable comments: patch code locally, commit, push, post a reply explaining the changes, and resolve the thread.
   - For questions or non-actionable items: post a reply on GitHub answering the question or explaining why no code change is needed, and resolve the thread.
   - If a later snapshot surfaces your own reply, treat it as informational and continue without responding again.
6. Diagnose CI failures and classify branch-related vs flaky/unrelated. If the overall run is still pending but `failed_jobs` already includes a failed job, fetch that job's logs and diagnose immediately instead of waiting for the whole workflow run to finish. Patch only when the failure is branch-related.
7. Process actionable review comments before flaky reruns when both are present; if a review fix requires a commit, push it and skip rerunning failed checks on the old SHA.
8. Retry failed checks only when `retry_failed_checks` is present and you are not about to replace the current SHA with a review/CI fix commit. Do not make code changes for unrelated flakes or infrastructure failures just to get CI green.
9. If you pushed a commit, posted replies, resolved review threads, or triggered a rerun, report the action briefly and continue polling (do not stop).
10. After a review-fix push, proactively restart continuous monitoring (`--watch`) in the same turn unless a strict stop condition has already been reached.
11. If everything is passing, mergeable, not blocked on required review approval, and all comments and review threads are resolved, report that the PR is currently ready to merge but keep the watcher running so new review comments are surfaced quickly while the PR remains open.
12. If blocked on a user-help-required issue (infra outage, exhausted flaky retries, genuine product/architectural blocker, permissions), report the blocker and stop.
13. Otherwise sleep according to the polling cadence below and repeat.

When the user explicitly asks to monitor/watch/babysit a PR, prefer `--watch` so polling continues autonomously in one command. Use repeated `--once` snapshots only for debugging, local testing, or when the user explicitly asks for a one-shot check.
Do not stop to ask the user whether to continue polling; continue autonomously until a strict stop condition is met or the user explicitly interrupts.
Do not hand control back to the user after a review-fix push just because a new SHA was created; restarting the watcher and re-entering the poll loop is part of the same babysitting task.
If a `--watch` process is still running and no strict stop condition has been reached, the babysitting task is still in progress; keep streaming/consuming watcher output instead of ending the turn.

## Polling Cadence
Keep review polling aggressive and continue monitoring even after CI turns green:

- While CI is not green (pending/running/queued or failing): poll every 1 minute.
- After CI turns green: keep polling at the base cadence while the PR remains open so newly posted review comments are surfaced promptly instead of waiting on a long green-state backoff.
- Reset the cadence immediately whenever anything changes (new commit/SHA, check status changes, new review comments, mergeability changes, review decision changes).
- If CI stops being green again (new commit, rerun, or regression): stay on the base polling cadence.
- If any poll shows the PR is merged or otherwise closed: stop polling immediately and report the terminal state.

## Stop Conditions (Strict)
Stop only when one of the following is true:

- PR merged or closed (stop as soon as a poll/snapshot confirms this).
- User intervention is required and the agent cannot safely proceed alone.

Keep polling when:

- `actions` contains only `idle` but checks are still pending or comments remain unresolved.
- CI is still running/queued.
- Review state is quiet but CI is not terminal.
- CI is green but mergeability is unknown/pending.
- CI is green and mergeable, but the PR is still open and you are waiting for possible new review comments or merge-conflict changes.
- The PR is green but blocked on review approval (`REVIEW_REQUIRED` / similar); continue polling at the base cadence and surface any new review comments without asking for confirmation to keep watching.

## Output Expectations
Provide concise progress updates while monitoring and a final summary that includes:

- During long unchanged monitoring periods, avoid emitting a full update on every poll; summarize only status changes plus occasional heartbeat updates.
- Treat push confirmations, intermediate CI snapshots, ready-to-merge snapshots, and review-action updates as progress updates only; do not emit the final summary or end the babysitting session unless a strict stop condition is met.
- A user request to "monitor" is not satisfied by a couple of sample polls; remain in the loop until a strict stop condition or an explicit user interruption.
- A review-fix commit + push is not a completion event; immediately resume live monitoring (`--watch`) in the same turn and continue reporting progress updates.
- When CI first transitions to all green for the current SHA, emit a one-time celebratory progress update (do not repeat it on every green poll). Preferred style: `🚀 CI is all green! 33/33 passed. Still on watch for review approval.`
- Do not send the final summary while a watcher terminal is still running unless the watcher has emitted/confirmed a strict stop condition; otherwise continue with progress updates.

- Final PR SHA
- CI status summary
- Mergeability / conflict status
- Addressed & resolved review comments / threads
- Fixes pushed
- Flaky retry cycles used
- Remaining unresolved failures or blockers (if any)

## References

- Heuristics and decision tree: `references/heuristics.md`
- GitHub CLI/API details used by the watcher: `references/github-api-notes.md`
