---
name: review-pr
description: Code review a pull request with multi-perspective analysis (guideline compliance, bug scanning, git history, prior PR context, code comments) and rigorous confidence scoring.
---

# Review PR

Provide a high-signal, low-noise code review for a GitHub pull request.

The review runs five independent analytical perspectives followed by independent verification and confidence scoring, filtering out pedantic nitpicks and false positives so only verified, actionable issues are reported.

## Environment & Prerequisites

- **Work Environment Configuration**: When operating within `~/Documents/Work` (or any subdirectory), ensure `GH_CONFIG_DIR=~/.config/gh-work` is set for all `gh` CLI invocations.
- **CLI Tooling**: Use `gh` commands for all GitHub interactions (`gh pr view`, `gh pr diff`, `gh pr comment`, `gh api`).

## Execution Modes

This skill is agent-agnostic and supports two execution models depending on the harness capabilities:

1. **Subagent / Multi-Agent Harness** (e.g., Antigravity, Gemini CLI, Claude Code, OpenAI Codex):
   - Use fast/lightweight models for screening, summary, and confidence scoring.
   - Dispatch parallel subagents across the 5 review perspectives using standard/capable models.
   - Dispatch parallel verification subagents for confidence scoring.
2. **Single-Agent Harness** (e.g., Cursor, single-session CLI):
   - Run the pre-flight checks, summary, and each of the 5 review lenses sequentially in the current session.
   - Evaluate confidence scoring systematically before composing the final comment.

---

## Step-by-Step Workflow

### 1. Pre-Flight Eligibility Check

Inspect the pull request to determine if review should proceed. Do not proceed if:
- The PR is closed or merged.
- The PR is a draft (`isDraft: true`).
- The PR does not need a review (e.g., automated dependency bump, bot PR, trivial auto-generated change).
- The PR already has an up-to-date review from you on the current HEAD SHA.

```bash
gh pr view <pr_number_or_url> --json number,title,state,isDraft,author,headRefOid,comments,reviews
```

### 2. Discover Repository Guideline & Instruction Files

Search for repository-specific instruction and guideline files to understand the project's coding standards:
- Root and subdirectory instruction files: `AGENTS.md`, `CLAUDE.md`, `COPILOT.md`, `CURSOR.md`, `.cursorrules`, `.github/copilot-instructions.md`, `CONTRIBUTING.md`, style guides, or architecture docs.
- Target directories touched by the PR to find localized guideline files.
- Note the file paths (do not load full contents into main context until needed for guideline auditing).

### 3. Extract PR Context & Changes

Fetch the PR diff and commit summary:
- Retrieve the full diff: `gh pr diff <pr_number_or_url>`
- Identify base and head commit SHAs: `gh pr view <pr_number_or_url> --json baseRefOid,headRefOid`
- Summarize the change: intent, touched files, architecture impact, and critical paths.

### 4. Multi-Perspective Review (5 Analytical Lenses)

Analyze the pull request independently across 5 distinct perspectives (via parallel subagents or sequential passes). Each perspective flags candidate issues with the file path, line range, description, and triggering reason:

1. **Lens 1 — Repository Guidelines & Instructions Adherence**
   - Audit changes against discovered repository instruction files (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.cursorrules`, etc.).
   - Verify compliance with explicit project rules, architectural boundaries, naming conventions, and constraints.
   - *Note*: Ignore authoring-only guidance that does not apply to code review.
2. **Lens 2 — Direct Bug & Logic Scanning**
   - Perform a focused scan of modified lines for logic errors, off-by-one errors, null/nil pointer dereferences, unhandled error paths, resource/memory leaks, and concurrency/race conditions.
   - Focus strictly on real functional bugs in modified code. Ignore pre-existing issues and stylistic preferences.
3. **Lens 3 — Git History & Invariant Analysis**
   - Inspect git blame and recent commit history on modified lines (`git log -S`, `git blame -L`, `git log -p -n 5 <file>`).
   - Ensure the change does not inadvertently revert past bug fixes, break historical invariants, or violate domain assumptions established in prior commits.
4. **Lens 4 — Prior PR Context & Related Discussions**
   - Search for related pull requests and issues that touched the same files (`gh pr list --state all --search "<file-or-feature>"`, `gh issue list --search ...`).
   - Check if similar changes encountered regressions, reviewer objections, or edge cases in the past.
5. **Lens 5 — Code Comments & Contract Verification**
   - Inspect docstrings, inline comments, type definitions, and interface contracts in and around modified functions.
   - Verify that the changes comply with stated contracts and invariants, and that comments are not rendered misleading or stale by the change.

### 5. Confidence Scoring & Verification

For each candidate issue found in Step 4, perform an independent verification and confidence scoring on a scale of **0–100** using this rubric:

| Score | Meaning | Description |
|---|---|---|
| **0** | Not confident / Invalid | False positive, pre-existing issue on unmodified code, or misunderstanding of intent. |
| **25** | Low confidence / Unverified | Possible issue but cannot be verified. Stylistic preference not mandated by repository guidelines. |
| **50** | Moderate confidence | Real issue, but a minor nitpick, low-frequency edge case, or negligible impact relative to PR scope. |
| **75** | High confidence | Verified real issue likely encountered in practice, breaking edge case, or explicit violation of repository guidelines. |
| **100** | Absolutely certain | Definite bug, security vulnerability, data loss risk, or regression backed by clear evidence. |

For issues flagged under Lens 1 (guidelines), confirm that the repository instruction file explicitly mandates the rule.

### 6. Filter False Positives & Low-Confidence Findings

**Threshold**: Discard any issue with a score strictly less than **80**.

#### False Positive Rules (Always Discard):
- Pre-existing issues on lines not modified by the PR.
- Pedantic stylistic nitpicks not codified in repository instruction files.
- Issues caught by compiler, typechecker, or linter (e.g., missing imports, syntax errors, type mismatches, formatting) — assume CI handles these.
- General code quality commentary (e.g., "could add more unit tests") unless explicitly mandated by repository guidelines.
- Rules explicitly suppressed in code (e.g., lint ignore comments like `// nolint`, `# noqa`, `@ts-ignore`).
- Intentional functionality changes integral to the PR's goal.

If no issues score ≥ 80, the review is clean.

### 7. Post-Flight Eligibility Recheck

Before posting, re-verify that the PR is still open and has not been merged, closed, or reviewed concurrently.

### 8. Post GitHub Review Comment

Format and post the review comment using `gh pr comment`:

```bash
gh pr comment <pr_number_or_url> --body "<formatted_comment>"
```

---

## Comment Format & Guidelines

### Comment Writing Rules
- Keep output concise, direct, and actionable.
- Avoid decorative emojis in issue descriptions.
- Every reported issue must cite the exact file path, full 40-character commit SHA, line range, and reasoning.
- Never use dynamic shell expansions like `$(git rev-parse HEAD)` in markdown comment bodies; resolve and provide the static SHA.

### Code Link Format
Format code permalinks as:
`https://github.com/<owner>/<repo>/blob/<full_40_char_sha>/<filepath>#L<start>-L<end>`

- Use the full commit SHA (`headRefOid`).
- Match the exact repository owner and name.
- Include 1–2 lines of context around the target line (e.g., commenting on lines 10–11 → link `#L9-L12`).

---

### Comment Templates

#### Template A: When Issues Are Found

```markdown
### Code review

Found <N> issues:

1. <brief description of issue> (<Guideline file or reason, e.g. AGENTS.md says "..." or Logic bug in error handling>)

https://github.com/<owner>/<repo>/blob/<head_sha>/<filepath>#L<start>-L<end>

2. <brief description of issue> (<reason>)

https://github.com/<owner>/<repo>/blob/<head_sha>/<filepath>#L<start>-L<end>

🤖 Generated by Agent PR Review
```

#### Template B: When No Issues Are Found

```markdown
### Code review

No issues found. Checked for bugs, regressions, historical context, and repository guideline compliance.

🤖 Generated by Agent PR Review
```
