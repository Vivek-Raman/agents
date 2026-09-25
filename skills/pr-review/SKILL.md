---
name: pr-review
description: Conduct high-signal, multi-perspective code review for pull requests (including draft PRs) with deep architectural, correctness, security, readability, and performance analysis, parallel subagent dispatch, rigorous confidence scoring, and inline diff comments via GitHub review API. Always checks out the PR branch directly in the current repository without using git worktrees.
disable-model-invocation: true
---

# Review PR & Code Quality

Provide a high-signal, low-noise, multi-dimensional code review for a GitHub pull request (supporting both draft and ready-for-review PRs).

The review leverages direct branch checkout in the repository (without using git worktrees), parallel analytical perspectives followed by independent verification and confidence scoring, filtering out pedantic nitpicks and false positives, and submitting verified actionable findings as **inline comments directly on the code diff** via GitHub's Review API.

---

## The Approval Standard & Review Philosophy

- **Continuous Improvement Over Perfection:** Approve a change when it definitely improves overall code health, even if it isn't perfect. Don't block a change because it isn't exactly how you would have written it. If it improves the codebase and follows project conventions, approve it.
- **Lead With What Matters:** Order findings by leverage: correctness and security first, then structural regressions and missed simplifications, then everything else. If you have one structural problem and ten nits, the structural problem *is* the review.
- **Propose the Move, Not Just the Problem:** When flagging an architectural or structural problem, propose a concrete named restructuring or replacement code block rather than just stating "this is complex."
- **Honesty & Anti-Sycophancy:** Do not rubber-stamp ("LGTM" without review). Do not soften real issues. Quantify problems where possible (e.g., "This N+1 query adds ~50ms per item in the list"). Push back on problematic approaches directly while maintaining focus on the code, not the author.

---

## Environment & Prerequisites

- **Work Environment Configuration**: When operating within `~/Documents/Work` (or any subdirectory), ensure `GH_CONFIG_DIR=~/.config/gh-work` is set for all `gh` CLI invocations.
- **Branch Checkout Requirement**: Always check out the PR branch directly in the current repository before performing the review (`gh pr checkout <pr_number_or_url>`).
- **Strict No-Worktrees Policy**: Never create or use `git worktree` (e.g., `git worktree add`). All file inspection, code analysis, git history checks, repository instruction discovery, and local test executions must run directly on the checked-out branch in the active workspace repository.
- **CLI Tooling**: Use `gh` commands for all GitHub interactions (`gh pr checkout`, `gh pr view`, `gh pr diff`, `gh pr review`, `gh api`, `gh pr list`, `gh issue list`).
- **Git Inspection**: Use local `git` commands for deep history and invariant analysis (`git log -S`, `git blame -L`, `git log -p -n 5 <file>`).

---

## Execution Modes & Subagent Parallelism

This skill is agent-agnostic and supports two execution models depending on the harness capabilities:

### 1. Subagent / Multi-Agent Harness (Antigravity, Gemini CLI, Claude Code, OpenAI Codex)
- **Pre-Flight & Branch Checkout:** Check out the PR branch directly into the working directory (do not use worktrees). Run fast/lightweight models for pre-flight eligibility checks, repo instruction discovery, and initial diff summary.
- **Large Delta Validation Gate (>1,000 Lines):** Before subagents are dispatched, inspect the per-file line deltas (additions + deletions). Flag any file exceeding 1,000 lines of delta and prompt the user to decide whether to review or skip it. Pass the resulting exclusion list directly to all analytical review subagents.
- **Parallel Multi-Perspective Review:** Dispatch parallel subagents across the analytical review lenses using standard/capable models, explicitly instructing them on any excluded/skipped files confirmed by the user. Subagents inherit the workspace and inspect the checked-out repository directly without creating separate worktrees. Each subagent focuses deeply on its assigned dimension.
- **Parallel Independent Verification:** Dispatch parallel verification subagents to evaluate and confidence-score candidate issues before aggregating findings into inline comments.

```
                  ┌───────────────────────────────┐
                  │ Pre-Flight & Branch Checkout  │
                  │   (Direct checkout, no WT)    │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │ Repo Guidelines & Diff Context│
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │ Large Delta Validation        │
                  │ (>1,000 lines delta per file) │
                  │ Prompt user: Review or Skip?  │
                  └───────────────┬───────────────┘
                                  │ (Provide exclusions)
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ Subagent Lens A │      │ Subagent Lens B │      │ Subagent Lens C │
│  (Correctness)  │      │ (Architecture)  │      │   (Security)    │
│ [Skip Excluded] │      │ [Skip Excluded] │      │ [Skip Excluded] │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                  ┌───────────────────────────────┐
                  │ Parallel Confidence Scoring   │
                  │     & Verification (>= 80)    │
                  └───────────────┬───────────────┘
                                  ▼
                  ┌───────────────────────────────┐
                  │   Submit PR Review Payload    │
                  │  (Inline Diff Comments + Body)│
                  └───────────────────────────────┘
```

### 2. Single-Agent Harness (Cursor, Single-Session CLI)
- Check out the PR branch directly in the working directory (no worktrees).
- Run pre-flight checks, repository guideline discovery, and diff extraction.
- Validate per-file deltas (>1,000 lines) and prompt the user whether to review or skip before proceeding.
- Execute sequential analytical passes across each review lens in the current session (omitting skipped files).
- Systematically evaluate confidence scoring for each candidate issue before assembling the inline comments and review submission.

---

## Change Sizing & Internal Steering Discipline

Understanding change sizing is critical for directing review depth and budget:

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~1000 lines changed  → Large change. Flag to the user internally to steer review scope.
```

> [!IMPORTANT]
> **Internal Steering Only — Never Complain to the Author About Change Size:**
> Line delta thresholds and change sizing checks are strictly internal control gates to alert you (the user running the review) so you can steer the review scope and direct subagents. **Do NOT post review comments to GitHub telling the author that changes are too large, files have too much delta, or asking them to split the PR.**

- **Large Delta Validation Gate (>1,000 Lines):** When any single file has a delta (additions + deletions) exceeding 1,000 lines, it often represents auto-generated output, schemas, lockfiles, data migrations, or massive refactorings. Always flag these files internally to the user before subagent dispatch to determine whether each file should be reviewed or skipped.
- **Watch Total File Size:** Around 1000 *total* lines in a single file is an architectural signal. When reviewing additions to an already-large file, check whether new functionality should be factored into cohesive subcomponents or helpers rather than inflating an existing monolith.
- **Change Descriptions:** Require a concise imperative first line ("Delete the FizzBuzz RPC", not "Deleting...") and an informative body explaining *what* and *why*, linking design docs, bug trackers, and benchmark results.

---

## Step-by-Step Review Workflow

### 1. Pre-Flight Eligibility Check

Inspect the pull request to determine if review should proceed.

```bash
gh pr view <pr_number_or_url> --json number,title,state,isDraft,author,headRefOid,comments,reviews
```

**Do not proceed if:**
- The PR is closed or merged.
- The PR does not need a review (e.g., trivial automated bot PR, auto-generated dependency bump without manual intervention requested).
- The PR already has an up-to-date review from you on the current `headRefOid`.

*(Note: Draft PRs (`isDraft: true`) are explicitly supported to provide early feedback on architecture, correctness, and implementation approach before marking ready for review.)*

### 2. Check Out PR Branch Directly (No Worktrees)

Always check out the PR branch directly in the current repository:

```bash
gh pr checkout <pr_number_or_url>
```

- **Strict No-Worktrees Policy:** Do **NOT** use `git worktree`, `git worktree add`, or create isolated worktree folders. All file reads, symbol lookups, git commands, and local tests must execute directly in the current workspace repository on the checked-out branch.
- **Clean Working Tree:** Ensure any uncommitted local modifications are resolved before checking out so `gh pr checkout` succeeds cleanly without overwriting unstaged work.
- **Fallback Checkout:** If `gh pr checkout` is not supported in the current environment, fetch and check out the branch directly:
  ```bash
  git fetch origin pull/<pr_number>/head:<branch_name> && git checkout <branch_name>
  ```

### 3. Discover Repository Guidelines & Project Instructions

With the branch checked out locally, locate project-specific instruction and guideline files to understand the repository's coding standards:
- Search root and parent directories: `AGENTS.md`, `CLAUDE.md`, `COPILOT.md`, `CURSOR.md`, `.cursorrules`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`, style guides, or architecture docs.
- Search touched target subdirectories for localized guideline files.
- Note discovered rules (do not flood context with irrelevant sections until auditing specific files).

### 4. Extract PR Context, Changes & Intent

Retrieve the full diff and metadata:

```bash
gh pr diff <pr_number_or_url>
gh pr view <pr_number_or_url> --json baseRefOid,headRefOid,title,body
```

- Review the test changes first: What behavior do the tests expect? Are edge cases covered?
- Summarize intent, touched modules, architectural impact, and critical paths.
- Inspect the checked-out files directly for surrounding context.
- Note exact file paths and line numbers modified in the diff for mapping inline review comments.

### 5. Large Delta Validation & Review Scope Confirmation (>1,000 Lines)

Before starting the review and spinning off analytical subagents, inspect the delta scale of each modified file in the pull request:

```bash
# Option A: Query file additions and deletions via GitHub CLI
gh pr view <pr_number_or_url> --json files --jq '.files[] | {path: .path, additions: .additions, deletions: .deletions, totalDelta: (.additions + .deletions)}'

# Option B: Query local git diff numstat against the base branch
git diff --numstat origin/<base_branch>...HEAD
```

#### Validation Procedure:

1. **Calculate Per-File Delta:**
   For every modified file in the PR diff, compute:
   $$\text{Line Delta} = \text{Additions} + \text{Deletions}$$

2. **Flag Files Over Threshold (>1,000 Lines):**
   Identify all files where $\text{Line Delta} > 1,000$. These large deltas frequently indicate generated code, bundled assets, vendor dependencies, snapshots, lockfiles, or sweeping mechanical renames.

3. **Prompt the User for Review vs. Skip Decisions (Internal Only — Do Not Post to Author):**
   - This alert is **strictly internal between the agent and you (the user)** to steer the review pipeline. **No comment, warning, or feedback regarding delta size is ever posted to the PR or PR author.**
   - If one or more files exceed 1,000 lines of delta, **pause before spinning off subagents**.
   - Present the flagged files with their exact additions, deletions, and total delta.
   - Prompt the user directly whether each flagged file should be **reviewed** or **skipped**:
     > **Large Delta Validation (Internal Review Steering):**
     > The following file(s) exceed 1,000 lines of delta:
     > - `src/generated/types.ts`: +1,420 / -180 (1,600 total delta)
     > - `data/fixtures/mock-data.json`: +3,100 / -0 (3,100 total delta)
     >
     > Would you like me to review or skip each of these files?

4. **Incorporate User Decisions into Subagent Instructions:**
   - Compile all files designated as **skipped** into an explicit exclusion list (`SKIPPED_FILES`).
   - When dispatching each analytical lens subagent, inject the exclusion instructions:
     ```markdown
     **Skipped Files Directive:**
     The user has confirmed to SKIP the following large-delta files (>1,000 lines):
     - `src/generated/types.ts`
     - `data/fixtures/mock-data.json`

     Do NOT inspect these files, do NOT review their diffs, and do NOT flag any issues or generate inline comments for them. Focus your review exclusively on the remaining changed files.

     **Author-Facing Feedback Rule:**
     Do NOT tell the PR author that files were skipped or that changes are too large. Delta thresholds are strictly internal for user steering.
     ```
   - For files confirmed for **review**, include them in the subagent review scope as normal.
   - If no files exceed 1,000 lines of delta, continue automatically to Step 6 without interrupting the user.

### 6. Parallel Multi-Perspective Deep Review (The Analytical Lenses)

Analyze the pull request independently across these analytical lenses (via parallel subagents inheriting the checked-out workspace or dedicated sequential passes). Subagents must be instructed to skip any files excluded during Step 5. Each lens flags candidate findings with exact file path, diff line number (and `start_line` if multi-line), description, and concrete code replacement:

#### Lens 1 — Repository Guidelines & Project Conventions
- Audit changes against discovered instruction files (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, etc.).
- Verify compliance with explicit project rules, architectural boundaries, naming conventions, and patterns.
- *Note*: Ignore authoring-only advice that does not apply to code review.

#### Lens 2 — Correctness, Logic & Error Handling
- **Functional Bugs:** Scan modified lines for logic errors, off-by-one errors, null/nil pointer dereferences, type coercion traps, unhandled error paths, and state inconsistencies.
- **Edge Cases:** Check boundaries (null, empty strings, zero, negative values, maximum collections, unexpected types).
- **Concurrency & State:** Look for race conditions, deadlock risks, un-synchronized shared mutable state, or improper transaction boundaries.
- **Test Integrity:** Verify tests test real behavior and assertions (not mock implementation details), and verify that regression tests accompany bug fixes.

#### Lens 3 — Architecture, Structural Integrity & Complexity Reduction
- **Concept Count:** Does this refactor reduce complexity or just relocate it? Count the concepts a reader must hold. If a "cleaner" version leaves that count unchanged, prefer restructuring that eliminates whole branches, modes, or layers.
- **Module Boundaries:** Is feature-specific logic leaking into shared/general-purpose modules? Keep logic in its owning package.
- **Canonical Helpers:** Is the change introducing a bespoke near-duplicate of an existing helper instead of reusing the canonical one?
- **Type Boundaries:** Question gratuitous `any`, `unknown`, loose type assertions, or silent fallbacks that paper over an unclear invariant.
- **Design Smells:**
  - *Bolted Conditionals:* Is a new conditional bolted onto an unrelated flow? Push logic into its own helper, state, or policy.
  - *Repeated Conditionals on Same Shape:* Signals a missing polymorphic model or explicit dispatcher.

#### Lens 4 — Readability, Simplicity & Code Hygiene
- **Simplicity:** Could this be done in fewer lines without sacrificing clarity? Are abstractions earning their complexity (don't generalize until the third use case)?
- **Naming & Flow:** Are names descriptive and context-rich (no ambiguous `temp`, `data`, `res`)? Is control flow straightforward (no nested ternaries, deep callback pyramids)?
- **Dead Code Hygiene:** Identify any dead code artifacts: unreachable paths, no-op variables (`_unused`), obsolete shims, or commented-out code.

#### Lens 5 — Security & Boundary Hardening
- **Input Validation & Sanitization:** Ensure all external inputs (API payloads, query params, headers, files, webhooks) are validated and sanitized at system boundaries.
- **Secrets:** Verify no API keys, credentials, tokens, or PII are exposed in code, logs, or version control.
- **Injection Risks:** Check for parameterized database queries (no SQL string concatenation), command injection, and output encoding for XSS prevention.
- **Auth & Access Control:** Verify authentication and authorization checks exist at all protected endpoints and action handlers.

#### Lens 6 — Performance & Scalability
- **Database & I/O:** Look for N+1 queries, missing batch lookups, or unindexed filters.
- **Resource Constraints:** Identify unbounded loops, unconstrained data fetching, missing pagination on list endpoints, and memory/resource leaks (unclosed streams, file handles).
- **Execution Paths:** Check for unnecessary synchronous operations blocking async loops, heavy object allocations in hot loops, and unnecessary UI re-renders.

#### Lens 7 — Git History, Invariants & Regression Analysis
- **Commit History & Blame:** Inspect `git blame -L <start>,<end> <file>` and `git log -S "<symbol>" -p -n 5 <file>` on modified sections in the checked-out repository.
- **Invariant Preservation:** Ensure the PR does not inadvertently revert past bug fixes, break historical invariants, or violate domain assumptions established in prior commits.

#### Lens 8 — Prior PR Context & Historical Discussions
- **Related Issues & PRs:** Search related discussions touching the same files:
  ```bash
  gh pr list --state all --search "<file_or_feature>"
  gh issue list --search "<keyword>"
  ```
- Check if similar changes encountered regressions, reviewer objections, or unexpected edge cases in the past.

#### Lens 9 — Dependency Discipline & Lockfile Audit
- **New Dependencies:** Ensure existing standard library or existing utilities cannot solve the problem. Verify license, bundle size impact, and maintenance health.
- **Upgrades:** Review changelogs (not just version numbers). Ensure one dependency per change. Verify lockfile diff (`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`) is committed and not hand-edited.

---

## Structural Remedies: Proposing Named Moves

When flagging architectural or design problems, propose the specific structural remedy:

| Structural Problem | Recommended Remedy |
|---|---|
| Chain of conditionals on shape/type | Replace with a typed model, strategy pattern, or explicit dispatcher. |
| Duplicate branching logic | Collapse duplicate branches into a single unified flow. |
| Mixed concerns | Separate orchestration/coordination from core business logic. |
| Leaking domain logic | Move feature-specific logic out of shared modules into the owning domain package. |
| Bespoke duplicate utility | Reuse the existing canonical helper. |
| Fuzzy type fallback | Make the type boundary explicit so downstream branching disappears. |
| Unnecessary indirection | Delete pass-through wrappers that add layers without clarifying the API. |
| Bloated file (>1000 lines) | Extract focused subcomponents, helpers, or cohesive submodules. |

---

## Confidence Scoring & False Positive Filtering

For each candidate issue identified across the lenses, perform rigorous verification on the checked-out codebase and assign a score on a scale of **0–100**:

### Confidence Rubric

| Score | Classification | Description |
|---|---|---|
| **0** | Invalid / False Positive | Pre-existing issue on unmodified code, misunderstanding of PR intent, or incorrect assumption. |
| **25** | Low Confidence / Unverified | Possible issue but cannot be verified. Stylistic preference not mandated by repository guidelines. |
| **50** | Moderate Confidence | Real issue, but a minor nitpick, low-frequency edge case, or negligible impact relative to PR scope. |
| **75** | High Confidence | Verified issue likely encountered in practice, breaking edge case, or explicit violation of repo guidelines. |
| **100** | Absolutely Certain | Definite bug, security vulnerability, data corruption/loss risk, or regression backed by hard evidence. |

### False Positive Discard Rules (Always Discard < 80 Score)

**Threshold: Discard any issue with a score strictly less than 80.**

Always discard candidate issues that fall into these categories:
1. **Pre-existing code:** Issues on lines not modified by the PR.
2. **Pedantic style nitpicks:** Stylistic preferences not explicitly codified in the repository's guideline files.
3. **Linter/Compiler territory:** Issues caught by compiler, typechecker, or linter (e.g., missing imports, syntax errors, formatting) — assume CI handles these.
4. **Unmandated quality commentary:** General commentary (e.g., "could add more tests") unless explicitly mandated by project guidelines.
5. **Explicitly suppressed rules:** Code containing explicit lint-ignore comments (e.g., `// nolint`, `# noqa`, `@ts-ignore`).
6. **Intentional functional changes:** Modifications that are central to the PR's stated objective.
7. **Change size / PR scope commentary:** Issues or comments complaining that a file or PR is too large, has too many lines of delta, or asking the author to split the PR. Change sizing and delta checks are strictly internal control gates for the user to steer review scope, never author-facing review feedback.

---

## Finding Classification & Severity Prefixes

Label all verified findings with clear severity prefixes so the author immediately knows what is blocking vs. optional:

| Prefix | Meaning | Author Action |
|---|---|---|
| **Critical:** | Blocks merge | Security vulnerability, data loss, severe functional bug, or regression. |
| *(no prefix)* | Required change | Functional bug, explicit guideline violation, or structural debt that must be resolved. |
| **Optional:** / **Consider:** | Suggestion | Valuable suggestion or cleaner alternative; author may adopt or decline. |
| **Nit:** | Minor optional | Cosmetic preference or tiny cleanup; author may ignore. |
| **FYI** | Informational | Context for future reference; no action required. |

---

## GitHub PR Review & Inline Comment Guidelines

Instead of posting a single comment that tags or links to code blocks, submit **inline review comments directly on the modified diff lines** via GitHub's Pull Request Review API.

### Inline Comment Rules
- **Direct Diff Attachment:** Attach each issue directly to the relevant file path (`path`) and line number (`line`) in the PR diff. For multi-line spans, specify `start_line` and `line` (`side: "RIGHT"`).
- **Use Suggestion Blocks:** Whenever proposing a concrete fix or replacement, use GitHub's markdown suggestion syntax (```` ```suggestion ````) so the author can review and accept the change with a single click.
- **Concise & Actionable:** Keep descriptions direct, crisp, and focused on solutions without decorative emojis or filler.
- **High-Level Summary in Body:** The review `body` provides the overall summary and notes on architectural health, while line-specific findings are placed in the `comments` array. PR-wide findings that don't correspond to a specific diff line remain in the review `body`.

### Inline Comment Format

#### Format for Single-Line or Multi-Line Finding with Code Suggestion:

```markdown
**Critical:** Memory leak caused by unremoved event listener on component unmount. (Violates resource cleanup guidelines)

```suggestion
  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);
```
```

#### Format for Finding with Explanation / Structural Move:

```markdown
**Consider:** Extract duplicated tax calculation into the canonical `calculateOrderTax` helper.

*Suggested fix:* Replace lines 45-52 with `const tax = calculateOrderTax(order.items, customer.jurisdiction);`
```

---

## Review Payload Structure & Templates

### 1. PR Review Submission Payload (JSON for `gh api`)

When issues are found, structure the submission payload for `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews`:

```json
{
  "commit_id": "<40_char_head_sha>",
  "body": "### Code Review Summary\n\nFound 2 issues on modified lines across the PR.\n\n🤖 Generated by Agent PR Review",
  "event": "COMMENT",
  "comments": [
    {
      "path": "src/services/payment.ts",
      "line": 42,
      "side": "RIGHT",
      "body": "**Critical:** Potential unhandled promise rejection if gateway times out.\n\n```suggestion\n  try {\n    return await paymentGateway.charge(params);\n  } catch (err) {\n    logger.error({ err, orderId: params.orderId }, \"Payment gateway charge failed\");\n    throw new PaymentProcessingError(\"Unable to complete transaction\", { cause: err });\n  }\n```"
    },
    {
      "path": "src/utils/formatters.ts",
      "start_line": 15,
      "line": 18,
      "side": "RIGHT",
      "body": "**Consider:** Use canonical `formatCurrency` helper instead of bespoke string concatenation."
    }
  ]
}
```

### 2. Review Body Template When No Issues Are Found

When all lenses pass with 0 verified issues (score >= 80):

```markdown
### Code Review Summary

No issues found. Verified for correctness, security, architecture, performance, regressions, git history, and repository guideline compliance.

🤖 Generated by Agent PR Review
```

---

## Post-Flight Check & Submitting Review

### 7. Post-Flight Eligibility Recheck
Before submitting, re-verify that the PR remains open (or draft) and has not been concurrently merged or closed:

```bash
gh pr view <pr_number_or_url> --json state,isDraft,headRefOid
```

### 8. Submit GitHub PR Review with Inline Comments

Submit the review payload containing the top-level summary and all inline comments in a single atomic review call.

#### Option A: Submit Review with Inline Comments via `gh api`

Extract the static 40-character `headRefOid` and submit the review with inline comments:

```bash
# 1. Resolve PR number, repo, and head commit SHA
HEAD_SHA=$(gh pr view <pr_number_or_url> --json headRefOid -q .headRefOid)

# 2. Submit review with inline comments
gh api repos/{owner}/{repo}/pulls/<pr_number>/reviews --input - << EOF
{
  "commit_id": "${HEAD_SHA}",
  "body": "### Code Review Summary\n\nFound <N> verified issues on modified lines.\n\n🤖 Generated by Agent PR Review",
  "event": "COMMENT",
  "comments": [
    {
      "path": "<relative_file_path>",
      "line": <diff_line_number>,
      "side": "RIGHT",
      "body": "<formatted_inline_comment_body>"
    }
  ]
}
EOF
```

*(Note: Use `event: "COMMENT"` for standard review or draft PRs. If the PR is ready for review and non-draft, `event: "REQUEST_CHANGES"` may be used when blocking/Critical issues are identified, or `event: "APPROVE"` when no blocking issues exist.)*

#### Option B: Submitting Review When No Issues Found

When no issues are found, submit a clean review directly:

```bash
gh pr review <pr_number_or_url> --comment -b "### Code Review Summary

No issues found. Verified for correctness, security, architecture, performance, regressions, git history, and repository guideline compliance.

🤖 Generated by Agent PR Review"
```

#### Option C: Posting Single Inline Comment (Standalone)

If adding a single standalone inline comment outside a batch review:

```bash
gh api repos/{owner}/{repo}/pulls/<pr_number>/comments \
  -f body="<inline_comment_body>" \
  -f commit_id="${HEAD_SHA}" \
  -f path="<relative_file_path>" \
  -F line=<diff_line_number> \
  -f side="RIGHT"
```

---

## Review Speed, Disagreements & Quality Gates

### Review Speed & Cadence
- **Respond promptly:** The cost of reviewer context-switching is far lower than the waiting cost imposed on the author and team.
- **Prioritize fast turnaround on updates:** Quick iterations reduce cycle time even if multiple rounds are required.

### Handling Disagreements (Hierarchy of Authority)
When resolving review disputes, apply this strict hierarchy:
1. **Technical facts and empirical data** override opinions and preferences.
2. **Repository style guides & instruction files** are the absolute authority on style matters.
3. **Software design principles** must be evaluated on engineering merits (coupling, cohesion, complexity).
4. **Codebase consistency** is acceptable as long as it does not degrade overall health.
5. **Never accept "I'll clean it up later"**: Deferred cleanup rarely happens. Require cleanup before merge, or require a linked issue filed with self-assignment for genuine emergencies.

### Common Rationalizations & Red Flags

| Rationalization | Reality |
|---|---|
| *"It works, that's good enough"* | Working code that is unreadable, insecure, or architecturally tangled creates compounding debt. |
| *"I wrote it, so I know it's correct"* | Authors are blind to their own assumptions. Every change needs independent verification. |
| *"We'll clean it up later"* | Later never comes. The review is the quality gate. Require cleanup before merge. |
| *"AI-generated code is probably fine"* | AI code requires more scrutiny, not less. It is confident and plausible even when subtly wrong. |
| *"Tests pass, so it's good"* | Tests are necessary but not sufficient. They do not catch architectural rot, security flaws, or unhandled boundaries. |
| *"The refactor makes it cleaner"* | Relocating complexity is not reducing it. Count the concepts the reader must hold. |
| *"It's only a small addition to this file"* | Small diffs can push a bloated file over the edge. Decompose before piling more on. |
| *"It's just a routine dependency bump"* | A bump is a behavioral change written by a third party. Read the changelog; inspect lockfile diffs. |

### Final Verification Checklist

Before finalizing and submitting the review:
- [ ] PR branch checked out directly in the working repository (`gh pr checkout`) without using git worktrees.
- [ ] Context understood (PR intent, requirements, touched systems).
- [ ] Diff size assessed (~100 / ~300 / ~1000 lines) and file size evaluated.
- [ ] Per-file delta validated (>1,000 lines flagged, user prompted to review or skip, subagents informed of skipped files).
- [ ] All 9 analytical lenses evaluated directly on the checked-out repository (excluding skipped files).
- [ ] Confidence scoring applied to all findings (discarded all < 80).
- [ ] Findings categorized by severity (`Critical:`, *(Required)*, `Consider:`, `Nit:`, `FYI`).
- [ ] Line-specific findings formatted as inline comments with exact `path`, `line` (or `start_line`..`line`), and `side: "RIGHT"`.
- [ ] Concrete replacement code formatted with GitHub ` ```suggestion ` blocks where applicable.
- [ ] Structural remedies proposed for design and architectural issues.
- [ ] PR state and `headRefOid` rechecked before submitting review payload via `gh api` or `gh pr review`.
