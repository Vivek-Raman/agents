---
name: patch-agy-acp
description: Patch an Antigravity binary (`antigravity` or `agy`) or the active T3 Code bundled release with the stdio wrapper that passes through non-ACP commands and merges enabled user MCP servers into live sessions.
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
     - When `params.mcpServers` is non-empty, merges enabled user MCP servers from `~/.gemini/config/mcp_config.json` and `<workspace>/.gemini/mcp_config.json` into `params.mcpServers`. Empty-MCP probe and background text-generation sessions are left untouched.
3. If `.install-complete.json` is present in the target directory, temporarily unlocks T3 Code's read-only release permissions (`0500`/`0555`/`0400`), backs up `.install-complete.json` to `.install-complete.json.bak`, updates `executable.bytes` to match the wrapper size so `AntigravityInstallation.completedRelease` passes, and restores the lock permissions.

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
