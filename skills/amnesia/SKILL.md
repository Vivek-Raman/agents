---
name: amnesia
description: Summarize recent T3 Code sessions by repository and worktree, with thread links, Git state, and pending work. Use when explicitly requested to catch up on recent work.
disable-model-invocation: true
---

# Amnesia

Give the user a brief, high-level catch-up on recent T3 Code work. Cover repositories, worktree branches, linked sessions, and what remains to do. Prioritize breadth over implementation detail.

## Gather context

- Honor any requested repository, time range, or session limit. Otherwise cover all projects in the current T3 environment over the last seven days. State the actual scope and snapshot time. If that window is empty, show the latest available sessions and say how old they are.
- Discover the available T3 tools and their schemas. Prefer the T3 connector over internal databases or application files. If unavailable, report that limitation without fabricating session context.
- Use `t3_project_list` to map project IDs to repository identities and workspace roots. Use `t3_thread_list` with `allProjects: true` and `includeSubagents: false`, or the requested project. Include settled and snoozed sessions as well as open ones. Follow pagination until the requested time range is covered, deduplicating thread IDs if pages shift. If results are capped or inaccessible, disclose the coverage gap.
- Read each included thread with `t3_thread_read` before summarizing it. Start with recent messages and the latest user request and final response. Read older pages or truncated text only as needed to establish the outcome, unresolved requests, or blockers. Do not treat an intermediate progress message as the final outcome.
- Capture the returned canonical `link`, branch, worktree path, update time, settled/archive state, run state, and any linked PR state. Use links verbatim. If a link is missing, mark it unavailable rather than constructing one.
- Use `t3_worktree_list` for each represented repository, using a representative thread ID. Its refs include branches without checkouts, so only entries with a worktree path represent worktrees. Page as needed. For accessible local repositories, `git -C <root> worktree list --porcelain` also finds detached worktrees omitted by the T3 tool.
- Group by repository identity and actual checkout path, not by thread title or branch alone. Consolidate multiple T3 projects for the same repository. Several sessions can share a checkout. Use project roots for primary checkouts only when supported by the metadata; leave ambiguous associations unknown. Keep sessions for removed worktrees and mark the checkout as removed.

## Verify worktree state

Use read-only Git commands on accessible paths. Quote paths safely and avoid checkout, fetch, pull, or other mutations.

- Check each worktree once with `git -C <path> status --porcelain=v1 --branch --untracked-files=normal`. Report staged, unstaged, untracked, or conflicted changes briefly. Do not dump filenames or diffs unless they explain a pending task.
- Verify the current branch or detached HEAD. Thread metadata can describe an earlier branch; label historical associations when it differs from the live checkout.
- If an upstream exists, use locally available refs to check ahead/behind counts, for example `git -C <path> rev-list --left-right --count HEAD...@{upstream}`. Label these as local observations; do not fetch. No upstream means publication status is unknown.
- A clean checkout proves only that there are no observed uncommitted changes. It does not prove the task is finished, pushed, reviewed, or merged. A completed agent turn is not a closed task, and a settled thread can still have dirty files.
- Reconcile the latest thread context with Git and available PR metadata. State concrete pending actions such as implementation, review, checks, push, merge, or a user decision only when supported. Distinguish "thread reports committed" from a live verified Git observation. Flag conflicting or stale evidence briefly.
- If Git is unavailable, the checkout is remote, or a worktree was removed, label Git state unknown. Never inspect a similarly named local path as a substitute for a remote checkout. Do not infer a clean state from silence in the thread.

## Organize the catch-up

Use these groups, with repository and worktree branch/path under each:

1. **Open / uncommitted work.** Include dirty worktrees and those with unfinished requests, active runs, unresolved blockers, open PRs, or commits awaiting push. A clean worktree with pending work belongs here too.
2. **Closed / committed work.** Include worktrees whose latest relevant context supports completion or closure, with no known pending work or uncommitted changes. State the actual evidence, such as clean, committed, pushed, settled, or merged. These labels describe different facts; do not substitute one for another.
3. **Unclear status.** Use only when the evidence cannot establish either group. Say what is missing. If completion is supported but live Git is unavailable, keep that uncertainty explicit rather than presenting the checkout as verified clean.

Place a shared worktree once, in the open group if any associated work is still pending. Include both completed and open sessions beneath it with their individual states. Untracked worktrees in the represented repositories can appear with "no recent session context" and their observed Git state. Do not assign them a task from a neighboring branch.

For each worktree, write one short summary with its purpose, observed Git state, and pending action if known. For each session, include the canonical thread link and one short note describing its outcome or next step, plus its state and last activity when useful. Use compact bullets or a table, whichever makes the report easier to scan. Keep technical detail and old conversational history out of the summary.

Example shape, using real links and evidence in the actual report:

```text
Scope: last seven days, all projects in this environment. Checked <time>.

Open / uncommitted work
<repo> · <branch> · <worktree path>
  <purpose>; <Git state>. Pending: <supported next step>.
  <canonical thread link> · <session state> · <short session note>

Closed / committed work
<repo> · <branch> · <worktree path>
  <outcome>; <completion and Git evidence>.
  <canonical thread link> · <session state> · <short session note>
```

This is a read-only catch-up. Do not message, resume, settle, archive, or otherwise modify sessions, worktrees, branches, or PRs. Mention access failures and omitted scope in one short closing note when relevant.
