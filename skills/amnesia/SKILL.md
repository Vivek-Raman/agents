---
name: amnesia
description: Show work in progress for the current project, centered on uncommitted or unmerged worktrees, using T3 HTML tools. Use when explicitly requested to catch up on pending work.
disable-model-invocation: true
---

# Amnesia

Remind the user what work is still in progress in the current project. The unit of the report is a worktree with uncommitted changes or unmerged work, not a session or a history of past actions. Keep this a quick, useful snapshot rather than a comprehensive audit.

## Find work in progress

- Scope to the current project, or the repository/project explicitly requested by the user. Resolve it from current thread metadata or match the working directory to workspace roots from `t3_project_list`. Include other project IDs only when their repository identity confirms the same repository. Ask which project to use if ambiguous; never scan unrelated projects.
- Discover the available T3 tools and their schemas. Prefer the T3 connector for project, worktree, and PR metadata. Use `t3_worktree_list` with a current-project thread ID to find checkouts. Its refs may include branches without worktrees; use actual checkout paths. For an accessible local repository, `git -C <root> worktree list --porcelain` can supply or supplement the checkout list. Include the primary checkout. Do not inventory historical branches without checkouts.
- Check each current project worktree once with `git -C <path> status --porcelain=v1 --branch --untracked-files=normal`. Use read-only commands and safely quoted paths. Summarize staged, unstaged, untracked, or conflicted changes without dumping filenames or diffs. Worktrees with current changes matter even without recent thread activity.
- Identify unmerged work using available linked PR state and branch/upstream metadata. Prioritize open PRs and unpublished commits; inspect local ahead/behind counts or branch differences only when useful to determine what remains. Do not fetch or mutate Git state, exhaust branch history, or treat every non-default branch as unfinished work. A clean checkout does not prove its work is merged; a missing PR does not prove completion. Local ancestry alone cannot establish that a squash-merged PR remains unmerged.
- Omit clean worktrees whose relevant PRs are merged. Do not read their threads or audit their history further. If a checkout has fresh uncommitted changes or explicit new work after a merge, include that remaining work without recapping the merged PR.
- Group by repository identity and actual checkout path, once per worktree. Use the live branch when checked; thread branch metadata may be historical. If the checkout is remote, removed, or inaccessible, label its state unknown instead of inspecting a similarly named local path. Brief uncertainty is enough; do not chase complete certainty or turn unknown status into an open-work claim.

## Add recent context only where useful

- Use threads to explain a worktree's purpose, blocker, or next action, not to decide which checkouts deserve a Git check. Default to the last three days of thread activity, honoring a requested time range or limit. State that this window applies to supporting context, while Git state is current. Do not search older sessions to fill gaps or omit observed pending work because its thread is older.
- Use `t3_thread_list` with the resolved project ID and `includeSubagents: false`. Never use `allProjects: true` or an unscoped listing. Match threads to the included worktrees using repository and checkout metadata, not title alone. Start with the newest relevant activity, page only as needed, and stop at the time boundary. Skip merged-PR threads and do not dig through settled, snoozed, or archived threads for completeness.
- Before citing or describing a thread, read it with `t3_thread_read`. Start with its latest user request and final response; read more only to resolve a concrete pending action. Preserve its returned canonical link verbatim. Do not reconstruct history or treat an intermediate progress message as the outcome. One useful context link per worktree is usually enough; do not list every associated session.
- If no recent context is available, report the observed Git or PR state and leave the purpose or next action unknown. Distinguish thread claims from verified observations. If tools or project filtering are unavailable, disclose the limitation rather than broadening the scan or fabricating context.

## Present the catch-up

Use the `frontend-design` skill to guide the visualization. Read its instructions before composing the HTML. The subject is already defined: a compact reminder of worktrees with pending work and what to do next. Plan and critique the layout briefly, then build with the real gathered content. Apply the T3 renderer's theme and embedding requirements over conflicting standalone-page design advice.

Center the visualization on worktrees, ordered by what needs attention. For each, show its branch or checkout, a short description of the unfinished work, observed uncommitted or unmerged state, and next action or blocker if known. Add a supporting thread or PR link when useful. Keep thread titles, session states, and past actions secondary. Use clear labels and hierarchy to distinguish changes to commit, work to push, and PRs awaiting checks, review, or merge. Show only states supported by evidence. Use color as a supporting cue and charts only when helpful. Avoid decorative metrics and dashboard chrome.

- Discover T3 Code's `html_preview` and `html_render` tools and read their schemas. Create self-contained HTML with inline styles and scripts only as needed. Escape thread text and preserve canonical link destinations. Keep the report read-only; links navigate to threads or PRs, and any filters or disclosure controls affect only the presentation.
- Follow `html_render`'s layout contract: transparent outer background, no outer card, banner title, or side padding; fluid width; content-driven height; T3 theme CSS variables and fonts. Keep it readable on mobile, with keyboard-accessible links and controls.
- Pass the HTML or an absolute HTML file path to `html_preview`. Inspect its image, content height, and console output; fix clipping, unreadable text, broken layout, or runtime errors before delivery. Then call `html_render` with the finished HTML or path and the preview's content height within the tool's accepted range. The render is the deliverable; an HTML file link or screenshot alone does not show it in the thread. Do not start a server or use browser preview tools for this report.
- If the design skill or HTML tools are unavailable, disclose the limitation briefly and provide the same concise catch-up in text. Do not expand the data scan to compensate.

Omit completed work, merged-PR recaps, session inventories, and empty sections. Do not add older history for coverage. If no pending work is found, say so briefly within the checked scope. Mention material access limits in one short note rather than pursuing exhaustive coverage.

This is a read-only catch-up. Creating its HTML presentation is allowed; do not message, resume, settle, archive, or otherwise modify sessions, worktrees, branches, or PRs.
