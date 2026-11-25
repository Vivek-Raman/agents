---
name: amnesia
description: Give a quick catch-up on recent T3 Code work for the current project, with thread links and pending actions. Use when explicitly requested to catch up on recent work.
disable-model-invocation: true
---

# Amnesia

Give the user a brief, high-level catch-up on recent T3 Code work for the current project. Focus on what is active, blocked, or needs attention. This is a recent snapshot, not a comprehensive audit.

## Gather recent context

- Scope the catch-up to the current project, or the repository/project explicitly requested by the user. Honor any requested time range or session limit; default to the last three days. State the scope and snapshot time. If that window is empty, say there is no recent activity. Do not search older sessions or broaden to unrelated projects to fill the report.
- Discover the available T3 tools and their schemas. Prefer the T3 connector over internal databases or application files. If unavailable, report that limitation without fabricating session context.
- Before listing threads, resolve the project from the current thread's project metadata or match the working directory to workspace roots from `t3_project_list`. Include other project IDs only when their repository identity confirms they belong to the same repository. If the project cannot be identified unambiguously, ask which project to use before scanning threads.
- Use `t3_thread_list` with the resolved project ID and `includeSubagents: false`. Never use `allProjects: true` or an unscoped thread listing. Read only threads belonging to that scope. If project filtering is unavailable, report the limitation instead of scanning all threads.
- Start with the newest activity and prioritize active runs, unfinished requests, blockers, and open PRs. Page only as needed for a useful recent picture; stop at the time boundary and do not exhaust pagination for completeness. Do not dig through settled, snoozed, or archived threads unless recent metadata suggests pending work.
- Skip threads whose relevant PRs are already merged. When listing metadata shows this, skip without reading the thread. Otherwise stop investigating once merged status is established. Do not audit their history, Git state, or worktrees. Revisit only if the user asks or recent context explicitly identifies new work after the merge.
- Read each thread you will summarize with `t3_thread_read`. Start with its latest user request and final response. Read additional context only to resolve a concrete current question. Do not reconstruct older history or chase every truncated message; leave uncertain status brief and explicit. Do not treat an intermediate progress message as the final outcome.
- Capture the returned canonical `link` and useful branch, checkout, activity, run, and PR metadata. Use links verbatim. If a link is missing, mark it unavailable rather than constructing one.

## Check state where useful

- Check only worktrees associated with included recent work, and only when live Git state helps identify the next action. Use `t3_worktree_list` if needed to resolve a checkout; do not inventory every worktree or branch.
- Use read-only Git commands on accessible paths. Check a relevant worktree once with `git -C <path> status --porcelain=v1 --branch --untracked-files=normal`. Check ahead/behind counts with local refs only when publication status matters. Do not fetch or mutate Git state.
- Group shared checkouts once using repository identity and actual path. Thread branch metadata may be historical; distinguish it from the current branch when checked. Do not assign tasks based only on neighboring branches or similarly named local paths.
- A clean checkout or completed agent turn does not prove the work is pushed, reviewed, or merged. State pending actions only when supported. Distinguish thread reports from live observations. If Git is unavailable or unnecessary to check, do not imply the checkout is verified clean. Brief uncertainty is enough; do not expand the investigation to eliminate it.

## Write the catch-up

Lead with recent work that needs attention. Use compact bullets or a small table, grouped by worktree only when that helps. For each included thread, give its canonical link, purpose or recent outcome, and next action if known. Add branch, Git state, or last activity only when useful.

A short note on other recent completed work is optional. Omit merged-PR threads and empty sections. Do not create a closed-work inventory, list unrelated worktrees, or add older history for coverage. If there is nothing actionable, say so briefly. Mention material access limits in one short note rather than pursuing exhaustive coverage.

This is a read-only catch-up. Do not message, resume, settle, archive, or otherwise modify sessions, worktrees, branches, or PRs.
