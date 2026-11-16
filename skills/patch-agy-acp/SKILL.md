---
name: patch-agy-acp
description: Patch an Antigravity ACP server directory or the active T3 Code bundled agy_acp_server release with the stdio wrapper that enforces prefix-matched workspace trust, injects workspace AGENTS.md/CLAUDE.md/GEMINI.md, merges user MCP servers, and disables the builtin run_workflow skill materializer.
argument-hint: "[path-to-agy-acp-server-dir | active | --restore | --status]"
disable-model-invocation: true
---

# Patch Antigravity ACP Server

Install or restore the Python 3 stdio wrapper around `agy_acp_server.par` in either an explicit `agy_acp_server` directory or the currently active T3 Code bundled Antigravity ACP release.

## What the patch does

1. Moves the original `agy_acp_server.par` binary to `agy_acp_server.real.par` if not already moved, preserving its inode so running sessions are not disrupted.
2. Installs the executable Python 3 stdio wrapper at `agy_acp_server.par`. On `session/new`, `session/load`, `session/resume`, and `session/fork`, the wrapper:
   - Propagates prefix-based workspace trust into `$GEMINI_HOME/antigravity-acp/trusted_workspaces.json` (also consulting `~/.gemini/antigravity-acp/trusted_workspaces.json` for trusted prefixes): if `params.cwd` or any `params.additionalDirectories` path is a subdirectory of a trusted prefix (and not overridden by a more specific `untrusted` prefix), its canonical path is atomically added to `trusted` before `agy_acp_server.real.par` performs its exact-match check.
   - Adds `"run_workflow"` to `params._meta.antigravity.disabledTools` (and removes it from `enabledTools` if present) so `localharness_external` skips enabling the `run-workflow` builtin skill and does not materialize `skills/system/run-workflow/SKILL.md` into project workspaces.
   - Walks `params.cwd` and `params.additionalDirectories` up to the `.git` root, reads `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` while deduplicating symlinks by realpath, wraps each in `<workspace_instructions path="...">...</workspace_instructions>`, and appends them to `params._meta.antigravity.systemPrompt.append`.
   - When `params.mcpServers` is non-empty, merges enabled user MCP servers from `~/.gemini/config/mcp_config.json` and `<workspace>/.gemini/mcp_config.json` into `params.mcpServers`. Empty-MCP probe and background text-generation sessions are left untouched.
3. If `.install-complete.json` is present in the target directory, backs it up to `.install-complete.json.bak` and updates `executable.bytes` to match the wrapper script size so T3 Code's `AntigravityInstallation.completedRelease` check passes.

## How to run

Run `~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py` with `python3`:

### 1. Update the active T3 Code `agy_acp_server`

When the user asks to patch or update the active T3 `agy_acp_server` without providing a directory path:

```bash
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --active
```

This reads `~/.t3/tools/antigravity-acp/<platform>-<arch>/active.json` (or falls back to the active `antigravity` provider's `binaryPath` in `~/.t3/userdata/settings.json`) and applies the wrapper there.

### 2. Patch a specific `agy_acp_server` directory

When the user provides a path to an `agy_acp_server` directory, binary, or parent `antigravity-acp/<platform>-<arch>` folder:

```bash
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/agy_acp_server_dir
```

### 3. Check status or restore the original binary

```bash
# Check whether the active T3 release or a target directory is patched
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --status
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/agy_acp_server_dir --status

# Restore the unpatched binary and original .install-complete.json
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --restore
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/agy_acp_server_dir --restore
```

After patching, remind the user to start a new thread or run **Restart agent session** in T3 Code so running sessions pick up the wrapper.
