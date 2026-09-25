# CI / Review Heuristics

## CI classification checklist

Treat as **branch-related** when logs clearly indicate a regression caused by the PR branch:

- Compile/typecheck/lint failures in files or modules touched by the branch
- Deterministic unit/integration test failures in changed areas
- Snapshot output changes caused by UI/text changes in the branch
- Static analysis violations introduced by the latest push
- Build script/config changes in the PR causing a deterministic failure

Treat as **likely flaky or unrelated** when evidence points to transient or external issues:

- DNS/network/registry timeout errors while fetching dependencies
- Runner image provisioning or startup failures
- GitHub Actions infrastructure/service outages
- Cloud/service rate limits or transient API outages
- Non-deterministic failures in unrelated integration tests with known flake patterns

Do not patch likely flaky/unrelated failures. Use the retry budget for rerunnable failures, wait for pending jobs, or stop and report the blocker when the failure is persistent or infrastructure-owned.

If uncertain, inspect failed logs once before choosing rerun.

## Decision tree (fix vs rerun vs stop)

1. If PR is merged/closed: stop.
2. If there are new review items or unresolved review threads:
   - All review comments must be addressed and resolved.
   - For actionable code feedback: patch code locally, commit, push, reply to the comment/thread with commit references, and resolve the thread.
   - For questions or non-actionable feedback: freely reply directly on GitHub with clear explanation, and resolve the thread.
3. If there are failed checks:
   - Diagnose first.
   - If checks are still pending but an individual job has already failed: fetch that job's logs and diagnose now.
   - If branch-related: fix locally, commit, push.
   - If likely flaky/unrelated and all checks for the current SHA are terminal: rerun failed jobs.
   - If likely flaky/unrelated and not safely rerunnable: stop and report the blocker; do not edit unrelated tests, build scripts, CI configuration, dependency pins, or infrastructure code.
   - If checks are still pending and no failed job is available yet: wait.
4. If flaky reruns for the same SHA reach the configured limit (default 3): stop and report persistent failure.

## Review comment handling & resolution criteria

All review comments must be addressed and resolved as a core goal:

- **Actionable code suggestions**:
  - Apply the code changes in the branch.
  - Commit and push.
  - Reply to the review thread explaining what was updated and reference the commit.
  - Resolve the review thread on GitHub.

- **Questions & clarifications**:
  - Freely reply directly to the comment/thread on GitHub with a clear, polite, and helpful explanation.
  - Resolve the review thread on GitHub once addressed.

- **Non-actionable / declined suggestions**:
  - Reply explaining the technical reasoning or context why no code change is necessary.
  - Resolve the review thread on GitHub.

- **AI reviewer bot feedback (Copilot, CodeRabbit, Claude, etc.)**:
  - Address actionable suggestions with fixes, reply, and resolve the thread.
  - If a bot suggestion is invalid or a false positive, reply explaining why and resolve the thread.

## Stop-and-ask conditions

Stop and ask the user instead of continuing automatically when:

- The local worktree has unrelated uncommitted changes.
- `gh` auth/permissions fail.
- The PR branch cannot be pushed.
- CI failures persist after the flaky retry budget.
- Reviewer feedback requires a high-level product/design decision or cross-team coordination that cannot be determined safely from context.
