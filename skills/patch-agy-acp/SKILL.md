---
name: patch-agy-acp
description: Patch an Antigravity binary (`antigravity` or `agy`) or the active T3 Code bundled release with the stdio wrapper that passes through non-ACP commands, enforces prefix-matched workspace trust, injects ~/.gemini/GEMINI.md (plus un-loaded CLAUDE.md), merges user MCP servers, and disables the builtin run_workflow skill materializer.
argument-hint: "[path-to-antigravity-bin-or-dir | active | --restore | --status]"
disable-model-invocation: true
---

# Patch Antigravity ACP

Install or restore the Python 3 wrapper around the `antigravity` / `agy` binary in either an explicit path/directory or the currently active T3 Code bundled release.

## What the patch does

1. Moves the original binary (`antigravity` or `agy`) to `<name>.real` if not already moved, preserving its inode so running sessions are not disrupted.
2. Installs the executable Python 3 wrapper at `<name>`:
   - Non-ACP invocations (`--version`, `login`, etc.) `os.execv` directly into `<name>.real` with no overhead.
   - On `acp` invocations (`antigravity acp ...`), intercepts `session/new`, `session/load`, `session/resume`, and `session/fork`:
     - Propagates prefix-based workspace trust into `<gemini-dir>/<app-data-dir>/trusted_workspaces.json` (respecting `--gemini-dir` and `--app-data-dir` CLI flags as well as `$GEMINI_HOME` and `~/.gemini`).
     - Adds `"run_workflow"` to `params._meta.antigravity.disabledTools` (and removes it from `enabledTools` if present) so `localharness_external` skips enabling `run-workflow` inside project workspaces.
     - Injects global `~/.gemini/GEMINI.md` (which T3's `--gemini-dir` override otherwise skips) into `params._meta.antigravity.systemPrompt.append`, plus workspace `CLAUDE.md` when not symlinked to an already-loaded `AGENTS.md`/`GEMINI.md`.
     - When `params.mcpServers` is non-empty, merges enabled user MCP servers from `~/.gemini/config/mcp_config.json` and `<workspace>/.gemini/mcp_config.json` into `params.mcpServers`. Empty-MCP probe and background text-generation sessions are left untouched.
3. If `.install-complete.json` is present in the target directory, backs it up to `.install-complete.json.bak` and updates `executable.bytes` to match the wrapper script size so T3 Code's `AntigravityInstallation.completedRelease` check passes.

## How to run

Run `~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py` with `python3`:

### 1. Update the active T3 Code Antigravity binary

When the user asks to patch or update the active T3 `antigravity` release without providing a path:

```bash
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --active
```

This reads `~/.t3/tools/antigravity-acp/<platform>-<arch>/active.json` (or falls back to the active `antigravity` provider's `binaryPath` in `~/.t3/userdata/settings.json`) and applies the wrapper to the executable named in `.install-complete.json`.

### 2. Patch a specific binary or directory

When the user provides a path to an `antigravity` / `agy` binary, version directory, or parent `antigravity-acp/<platform>-<arch>` folder:

```bash
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/antigravity_or_dir
```

### 3. Check status or restore the original binary

```bash
# Check whether the active T3 release or a target binary is patched
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --status
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/antigravity_or_dir --status

# Restore the unpatched binary and original .install-complete.json
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py --restore
python3 ~/.agents/skills/patch-agy-acp/scripts/patch_agy_acp.py /path/to/antigravity_or_dir --restore
```

After patching, remind the user to start a new thread or run **Restart agent session** in T3 Code so running sessions pick up the wrapper.
