#!/usr/bin/env python3
"""Patch an Antigravity binary (`antigravity` or `agy`) or the active T3 Code release.

Replaces the target executable with a Python 3 wrapper (moving the original
binary to `<name>.real`). Non-ACP subcommands (`--version`, `login`, etc.)
`execv` straight into `<name>.real`; `acp` sessions intercept JSON-RPC
lifecycle requests (`session/new`, `session/load`, `session/resume`,
`session/fork`) to:

1. Propagate prefix-based workspace trust in `trusted_workspaces.json` (respecting
   `--gemini-dir` and `--app-data-dir` CLI flags as well as `$GEMINI_HOME` /
   `~/.gemini`) so any session directory (`cwd` or `additionalDirectories`) under
   a trusted prefix (e.g. `~/.t3/worktrees`) is automatically recorded as trusted.
2. Inject `~/.gemini/GEMINI.md` and un-loaded workspace `CLAUDE.md` files (when
   not symlinked to natively loaded `AGENTS.md`/`GEMINI.md`) into
   `params._meta.antigravity.systemPrompt.append`.
3. Append user MCP servers from `~/.gemini/config/mcp_config.json` and
   `<workspace>/.gemini/mcp_config.json` into `params.mcpServers` on live chat
   sessions (skipping empty-MCP probe and text-generation sessions).
4. Add `run_workflow` to `params._meta.antigravity.disabledTools` so
   `localharness` does not materialize `skills/system/run-workflow/SKILL.md`
   inside project workspaces.
5. Update `executable.bytes` in `.install-complete.json` when present so T3
   Code's `AntigravityInstallation.completedRelease` size check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys

WRAPPER_CODE = '''#!/usr/bin/env python3
"""ACP stdio wrapper for antigravity/agy that preserves non-ACP exec, enforces prefix-matched workspace trust, injects GEMINI.md/CLAUDE.md, user MCP servers, and disabled builtin tools."""

import json
import os
import signal
import subprocess
import sys
import tempfile

NATIVE_RULE_FILENAMES = ("AGENTS.md", "GEMINI.md")
SESSION_METHODS = ("session/new", "session/load", "session/resume", "session/fork")
DISABLED_BUILTIN_TOOLS = ("run_workflow",)


def _find_real_binary() -> str:
    self_path = os.path.abspath(__file__)
    here = os.path.dirname(self_path)
    base = os.path.basename(self_path)
    for name in (f"{base}.real", "antigravity.real", "agy.real"):
        cand = os.path.join(here, name)
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(f"Could not locate real Antigravity binary beside {self_path}")


def _parse_acp_flags(argv: list[str]) -> tuple[str | None, str]:
    gemini_dir: str | None = None
    app_data_dir = "antigravity-cli"
    i = 0
    while i < len(argv):
        arg = argv[i]
        for flag in ("--gemini-dir", "--gemini_dir"):
            if arg == flag and i + 1 < len(argv):
                gemini_dir = argv[i + 1]
                i += 1
                break
            if arg.startswith(flag + "="):
                gemini_dir = arg.split("=", 1)[1]
                break
        else:
            for flag in ("--app-data-dir", "--app_data_dir"):
                if arg == flag and i + 1 < len(argv):
                    app_data_dir = argv[i + 1]
                    i += 1
                    break
                if arg.startswith(flag + "="):
                    app_data_dir = arg.split("=", 1)[1]
                    break
        i += 1
    return gemini_dir, app_data_dir


def _is_acp_invocation(argv: list[str]) -> bool:
    for arg in argv:
        if arg == "acp":
            return True
        if not arg.startswith("-"):
            return False
    return False


def _candidate_dirs(start_dir: str, home_dir: str) -> list[str]:
    cur = os.path.abspath(start_dir)
    if not os.path.isdir(cur):
        return []
    chain: list[str] = []
    found_git = False
    while True:
        if cur == home_dir or cur == os.path.dirname(cur):
            break
        chain.append(cur)
        if os.path.exists(os.path.join(cur, ".git")):
            found_git = True
            break
        cur = os.path.dirname(cur)
    if not found_git:
        chain = chain[:2]
    chain.reverse()
    return chain


def _workspace_roots(params: dict) -> list[str]:
    roots: list[str] = []
    cwd = params.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        roots.append(cwd.strip())
    for key in ("additionalDirectories", "additional_directories"):
        extra = params.get(key)
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, str) and item.strip():
                    roots.append(item.strip())
    return roots


def _canonical_path(path: str) -> str:
    return os.path.abspath(os.path.realpath(os.path.expanduser(path)))


def _is_subpath(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _trusted_workspaces_paths(
    gemini_dir_flag: str | None = None,
    app_data_dir: str = "antigravity-cli",
) -> tuple[str, list[str]]:
    default_home = os.path.join(os.path.expanduser("~"), ".gemini")
    if gemini_dir_flag:
        active_home = os.path.abspath(os.path.expanduser(gemini_dir_flag))
    else:
        env_home = os.environ.get("GEMINI_HOME", "").strip()
        active_home = os.path.expanduser(env_home) if env_home else default_home

    active_path = os.path.join(active_home, app_data_dir, "trusted_workspaces.json")
    candidates = [
        active_path,
        os.path.join(active_home, "antigravity-acp", "trusted_workspaces.json"),
        os.path.join(default_home, "antigravity-acp", "trusted_workspaces.json"),
        os.path.join(default_home, "antigravity-cli", "trusted_workspaces.json"),
    ]
    source_paths: list[str] = []
    seen: set[str] = set()
    for p in candidates:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            source_paths.append(p)
    return active_path, source_paths


def _load_trust_file(path: str) -> tuple[list[str], list[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return [], []
    if not isinstance(data, dict):
        return [], []
    trusted = data.get("trusted", [])
    untrusted = data.get("untrusted", [])
    return (
        [p for p in trusted if isinstance(p, str) and p.strip()]
        if isinstance(trusted, list)
        else [],
        [p for p in untrusted if isinstance(p, str) and p.strip()]
        if isinstance(untrusted, list)
        else [],
    )


def _ensure_prefix_trusted_workspaces(
    params: dict,
    gemini_dir_flag: str | None = None,
    app_data_dir: str = "antigravity-cli",
) -> None:
    roots = _workspace_roots(params)
    if not roots:
        return

    active_path, source_paths = _trusted_workspaces_paths(gemini_dir_flag, app_data_dir)
    active_trusted, active_untrusted = _load_trust_file(active_path)
    trusted_set = set(active_trusted)
    untrusted_set = set(active_untrusted)

    all_trusted_prefixes: set[str] = set()
    all_untrusted_prefixes: set[str] = set()
    for src in source_paths:
        t_list, u_list = (
            (active_trusted, active_untrusted)
            if src == active_path
            else _load_trust_file(src)
        )
        for p in t_list:
            all_trusted_prefixes.add(_canonical_path(p))
            all_trusted_prefixes.add(os.path.abspath(os.path.expanduser(p)))
        for p in u_list:
            all_untrusted_prefixes.add(_canonical_path(p))
            all_untrusted_prefixes.add(os.path.abspath(os.path.expanduser(p)))

    if not all_trusted_prefixes:
        return

    modified = False
    for root in roots:
        canonical = _canonical_path(root)
        if canonical in trusted_set or canonical in untrusted_set:
            continue

        best_trusted_len = max(
            (len(p) for p in all_trusted_prefixes if _is_subpath(canonical, p)),
            default=-1,
        )
        best_untrusted_len = max(
            (len(p) for p in all_untrusted_prefixes if _is_subpath(canonical, p)),
            default=-1,
        )
        if best_trusted_len > best_untrusted_len and best_trusted_len >= 0:
            trusted_set.add(canonical)
            modified = True

    if not modified:
        return

    target_dir = os.path.dirname(active_path)
    try:
        os.makedirs(target_dir, exist_ok=True)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_dir, prefix=".trusted_workspaces_", suffix=".tmp"
        )
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "trusted": sorted(trusted_set),
                        "untrusted": sorted(untrusted_set),
                    },
                    f,
                    indent=2,
                )
            os.replace(temp_path, active_path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
    except OSError:
        pass


def _load_workspace_instructions(params: dict) -> str:
    home_dir = os.path.abspath(os.path.expanduser("~"))
    seen_dirs: set[str] = set()
    seen_files: set[str] = set()
    sections: list[str] = []

    global_gemini = os.path.join(home_dir, ".gemini", "GEMINI.md")
    if os.path.isfile(global_gemini):
        try:
            real_global = os.path.realpath(global_gemini)
            with open(real_global, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                seen_files.add(real_global)
                sections.append(
                    f\'<global_instructions path="{global_gemini}">\\n{content}\\n</global_instructions>\'
                )
        except OSError:
            pass

    roots = _workspace_roots(params)
    if not roots:
        return "\\n\\n".join(sections)

    for root in roots:
        for d in _candidate_dirs(root, home_dir):
            if d in seen_dirs:
                continue
            seen_dirs.add(d)
            for native_name in NATIVE_RULE_FILENAMES:
                native_path = os.path.join(d, native_name)
                if os.path.isfile(native_path):
                    try:
                        seen_files.add(os.path.realpath(native_path))
                    except OSError:
                        pass
            fpath = os.path.join(d, "CLAUDE.md")
            if not os.path.isfile(fpath):
                continue
            try:
                real_fpath = os.path.realpath(fpath)
                if real_fpath in seen_files:
                    continue
                with open(real_fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    seen_files.add(real_fpath)
                    sections.append(
                        f\'<workspace_instructions path="{fpath}">\\n{content}\\n</workspace_instructions>\'
                    )
            except OSError:
                continue

    return "\\n\\n".join(sections)


def _load_user_mcp_servers(params: dict) -> list[dict]:
    existing = params.get("mcpServers")
    if not isinstance(existing, list) or not existing:
        return []

    existing_names = {
        s.get("name")
        for s in existing
        if isinstance(s, dict) and isinstance(s.get("name"), str)
    }

    home_dir = os.path.abspath(os.path.expanduser("~"))
    config_paths = [os.path.join(home_dir, ".gemini", "config", "mcp_config.json")]
    for root in _workspace_roots(params):
        config_paths.append(os.path.join(os.path.abspath(root), ".gemini", "mcp_config.json"))

    seen_paths: set[str] = set()
    injected: list[dict] = []

    for path in config_paths:
        if not os.path.isfile(path):
            continue
        try:
            real_path = os.path.realpath(path)
            if real_path in seen_paths:
                continue
            seen_paths.add(real_path)
            with open(real_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue

        if not isinstance(data, dict):
            continue
        servers_dict = data.get("mcpServers", data)
        if not isinstance(servers_dict, dict):
            continue

        for name, cfg in servers_dict.items():
            if (
                not isinstance(name, str)
                or not name
                or name in existing_names
                or not isinstance(cfg, dict)
                or cfg.get("disabled") is True
                or cfg.get("enabled") is False
            ):
                continue
            if "command" in cfg and cfg["command"]:
                args_raw = cfg.get("args")
                args_list = [str(a) for a in args_raw] if isinstance(args_raw, list) else []
                env_raw = cfg.get("env")
                env_list = (
                    [
                        {"name": str(k), "value": os.path.expandvars(str(v))}
                        for k, v in env_raw.items()
                    ]
                    if isinstance(env_raw, dict)
                    else []
                )
                injected.append(
                    {
                        "name": name,
                        "command": str(cfg["command"]),
                        "args": args_list,
                        "env": env_list,
                    }
                )
                existing_names.add(name)
            elif "url" in cfg and cfg["url"]:
                hdr_raw = cfg.get("headers")
                hdr_list = (
                    [
                        {"name": str(k), "value": os.path.expandvars(str(v))}
                        for k, v in hdr_raw.items()
                    ]
                    if isinstance(hdr_raw, dict)
                    else []
                )
                srv_type = "sse" if cfg.get("type") == "sse" else "http"
                injected.append(
                    {
                        "type": srv_type,
                        "name": name,
                        "url": str(cfg["url"]),
                        "headers": hdr_list,
                    }
                )
                existing_names.add(name)

    return injected


def _maybe_inject_session_params(
    raw_line: bytes,
    gemini_dir_flag: str | None = None,
    app_data_dir: str = "antigravity-cli",
) -> bytes:
    if not raw_line.startswith(b"{"):
        return raw_line
    try:
        msg = json.loads(raw_line)
        if not isinstance(msg, dict) or msg.get("method") not in SESSION_METHODS:
            return raw_line
        params = msg.get("params")
        if not isinstance(params, dict):
            return raw_line

        _ensure_prefix_trusted_workspaces(params, gemini_dir_flag, app_data_dir)

        changed = False
        meta = params.get("_meta")
        if not isinstance(meta, dict):
            meta = {}
            params["_meta"] = meta
        ag = meta.get("antigravity")
        if not isinstance(ag, dict):
            ag = {}
            meta["antigravity"] = ag

        disabled_tools = ag.get("disabledTools")
        if not isinstance(disabled_tools, list):
            disabled_tools = []
            ag["disabledTools"] = disabled_tools
            changed = True
        for tool_name in DISABLED_BUILTIN_TOOLS:
            if tool_name not in disabled_tools:
                disabled_tools.append(tool_name)
                changed = True

        enabled_tools = ag.get("enabledTools")
        if isinstance(enabled_tools, list):
            filtered_enabled = [
                t for t in enabled_tools if t not in DISABLED_BUILTIN_TOOLS
            ]
            if len(filtered_enabled) != len(enabled_tools):
                ag["enabledTools"] = filtered_enabled
                changed = True

        injected_prompt = _load_workspace_instructions(params)
        if injected_prompt:
            sp = ag.get("systemPrompt")
            if not isinstance(sp, dict):
                sp = {}
                ag["systemPrompt"] = sp

            existing = sp.get("append")
            if isinstance(existing, str) and existing.strip():
                if injected_prompt not in existing:
                    sp["append"] = f"{existing.rstrip()}\\n\\n{injected_prompt}"
                    changed = True
            else:
                sp["append"] = injected_prompt
                changed = True

        extra_mcp = _load_user_mcp_servers(params)
        if extra_mcp:
            params["mcpServers"] = [*params["mcpServers"], *extra_mcp]
            changed = True

        if not changed:
            return raw_line
        return (json.dumps(msg, separators=(",", ":")) + "\\n").encode("utf-8")
    except Exception:
        return raw_line


def main() -> int:
    real_bin = _find_real_binary()
    argv = sys.argv[1:]
    if not _is_acp_invocation(argv):
        os.execv(real_bin, [real_bin, *argv])

    gemini_dir_flag, app_data_dir = _parse_acp_flags(argv)

    proc = subprocess.Popen(
        [real_bin, *argv],
        stdin=subprocess.PIPE,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def _forward_signal(signum: int, _frame: object) -> None:
        try:
            proc.send_signal(signum)
        except ProcessLookupError:
            pass

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(sig, _forward_signal)
        except (OSError, ValueError):
            pass

    try:
        while True:
            raw_line = sys.stdin.buffer.readline()
            if not raw_line:
                break
            out_line = _maybe_inject_session_params(
                raw_line,
                gemini_dir_flag=gemini_dir_flag,
                app_data_dir=app_data_dir,
            )
            assert proc.stdin is not None
            proc.stdin.write(out_line)
            proc.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except OSError:
            pass

    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _default_platform_arch() -> str:
    sys_name = sys.platform
    os_name = (
        "darwin"
        if sys_name == "darwin"
        else "linux"
        if sys_name.startswith("linux")
        else sys_name
    )
    machine = platform.machine().lower()
    arch = (
        "arm64"
        if machine in ("arm64", "aarch64")
        else "x64"
        if machine in ("x86_64", "amd64")
        else machine
    )
    return f"{os_name}-{arch}"


KNOWN_BINARIES = ("antigravity", "agy")


def _real_binary_name(bin_name: str) -> str:
    return f"{bin_name}.real"


def _resolve_executable_name(version_dir: str, explicit_name: str | None = None) -> str:
    if explicit_name:
        return explicit_name
    record_path = os.path.join(version_dir, ".install-complete.json")
    if os.path.isfile(record_path):
        try:
            with open(record_path, "r", encoding="utf-8") as f:
                rec = json.load(f)
            exe = rec.get("executable") if isinstance(rec, dict) else None
            name = exe.get("name") if isinstance(exe, dict) else None
            if isinstance(name, str) and name.strip():
                clean_name = name.strip()
                if os.path.exists(os.path.join(version_dir, clean_name)) or os.path.exists(
                    os.path.join(version_dir, _real_binary_name(clean_name))
                ):
                    return clean_name
        except (OSError, ValueError):
            pass
    for candidate in KNOWN_BINARIES:
        if os.path.exists(os.path.join(version_dir, candidate)) or os.path.exists(
            os.path.join(version_dir, _real_binary_name(candidate))
        ):
            return candidate
    return "antigravity"


def _resolve_configured_binary_dir(t3_home: str) -> tuple[str, str, str | None] | None:
    for rel_settings in (os.path.join("userdata", "settings.json"), "settings.json"):
        settings_path = os.path.join(t3_home, rel_settings)
        if not os.path.isfile(settings_path):
            continue
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        instances = data.get("providerInstances") if isinstance(data, dict) else None
        if not isinstance(instances, dict):
            continue
        for inst_id, inst in instances.items():
            if not isinstance(inst, dict) or inst.get("driver") != "antigravity":
                continue
            if inst.get("enabled") is False:
                continue
            cfg = inst.get("config")
            bin_path = cfg.get("binaryPath") if isinstance(cfg, dict) else None
            if isinstance(bin_path, str) and bin_path.strip():
                expanded = os.path.abspath(os.path.expanduser(bin_path.strip()))
                if os.path.isfile(expanded):
                    return str(inst_id), os.path.dirname(expanded), os.path.basename(expanded)
                if os.path.isdir(expanded):
                    return str(inst_id), expanded, None
    return None


def _resolve_t3_version_dir(t3_home: str, release_id: str | None) -> tuple[str, str, str | None]:
    arch = _default_platform_arch()
    candidate_bases = [
        os.path.join(t3_home, "tools", "antigravity-acp", arch),
        os.path.join(t3_home, "userdata", "tools", "antigravity-acp", arch),
    ]
    base_dir = next(
        (b for b in candidate_bases if os.path.isdir(b)), candidate_bases[0]
    )
    if not release_id:
        active_path = os.path.join(base_dir, "active.json")
        if not os.path.isfile(active_path):
            configured = _resolve_configured_binary_dir(t3_home)
            if configured is not None:
                return configured
            raise FileNotFoundError(f"Could not find active.json at {active_path}")
        with open(active_path, "r", encoding="utf-8") as f:
            release_id = json.load(f)["releaseId"]
    assert release_id is not None
    version_dir = os.path.join(base_dir, "versions", release_id)
    if not os.path.isdir(version_dir):
        raise FileNotFoundError(f"Version directory does not exist: {version_dir}")
    return release_id, version_dir, None


def _resolve_target_dir(
    target_path: str | None, t3_home: str, release_id: str | None
) -> tuple[str, str, str]:
    if target_path and target_path.strip().lower() not in ("active", "t3", "t3-active"):
        expanded = os.path.abspath(os.path.expanduser(target_path.strip()))
        explicit_name: str | None = None
        if os.path.isfile(expanded):
            explicit_name = os.path.basename(expanded)
            expanded = os.path.dirname(expanded)
        if not os.path.isdir(expanded):
            raise FileNotFoundError(f"Target directory does not exist: {expanded}")

        # If pointed at a parent directory containing active.json + versions/
        active_file = os.path.join(expanded, "active.json")
        versions_dir = os.path.join(expanded, "versions")
        has_direct_bin = any(
            os.path.exists(os.path.join(expanded, name))
            or os.path.exists(os.path.join(expanded, _real_binary_name(name)))
            for name in KNOWN_BINARIES
        )
        if (
            explicit_name is None
            and not has_direct_bin
            and os.path.isfile(active_file)
            and os.path.isdir(versions_dir)
        ):
            with open(active_file, "r", encoding="utf-8") as f:
                rel_id = release_id or json.load(f)["releaseId"]
            resolved_dir = os.path.join(versions_dir, rel_id)
            if not os.path.isdir(resolved_dir):
                raise FileNotFoundError(
                    f"Version directory does not exist: {resolved_dir}"
                )
            return rel_id, resolved_dir, _resolve_executable_name(resolved_dir)

        return (
            os.path.basename(expanded),
            expanded,
            _resolve_executable_name(expanded, explicit_name),
        )

    label, resolved_dir, explicit_name = _resolve_t3_version_dir(t3_home, release_id)
    return label, resolved_dir, _resolve_executable_name(resolved_dir, explicit_name)


def patch_directory(version_dir: str, label: str, bin_name: str) -> None:
    bin_path = os.path.join(version_dir, bin_name)
    real_bin_path = os.path.join(version_dir, _real_binary_name(bin_name))
    record_path = os.path.join(version_dir, ".install-complete.json")
    record_bak_path = os.path.join(version_dir, ".install-complete.json.bak")

    if not os.path.exists(real_bin_path):
        if not os.path.exists(bin_path):
            raise FileNotFoundError(f"Missing binary at {bin_path}")
        shutil.move(bin_path, real_bin_path)

    if not os.path.exists(record_bak_path) and os.path.isfile(record_path):
        shutil.copy2(record_path, record_bak_path)

    with open(bin_path, "w", encoding="utf-8") as f:
        f.write(WRAPPER_CODE)
    os.chmod(bin_path, 0o755)

    new_size = os.path.getsize(bin_path)
    version_str = "standalone"
    if os.path.isfile(record_path):
        with open(record_path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        version_str = str(rec.get("version", "unknown"))
        if isinstance(rec.get("executable"), dict):
            rec["executable"]["bytes"] = new_size
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, separators=(",", ":"))
            f.write("\n")

    print(
        f"Patched Antigravity ACP ({version_str}, {label}):\n"
        f"  directory: {version_dir}\n"
        f"  wrapper: {bin_path} ({new_size} bytes)\n"
        f"  real binary: {real_bin_path}"
        + (f"\n  record: {record_path}" if os.path.isfile(record_path) else "")
    )


def restore_directory(version_dir: str, label: str, bin_name: str) -> None:
    bin_path = os.path.join(version_dir, bin_name)
    real_bin_path = os.path.join(version_dir, _real_binary_name(bin_name))
    record_path = os.path.join(version_dir, ".install-complete.json")
    record_bak_path = os.path.join(version_dir, ".install-complete.json.bak")

    if not os.path.exists(real_bin_path):
        print(f"Target {version_dir} ({label}) is not patched (no {real_bin_path} found).")
        return

    shutil.move(real_bin_path, bin_path)
    if os.path.exists(record_bak_path):
        shutil.move(record_bak_path, record_path)
    elif os.path.isfile(record_path):
        real_size = os.path.getsize(bin_path)
        with open(record_path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        if isinstance(rec.get("executable"), dict):
            rec["executable"]["bytes"] = real_size
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, separators=(",", ":"))
            f.write("\n")

    print(f"Restored original Antigravity binary in {version_dir} ({label}).")


def status_directory(version_dir: str, label: str, bin_name: str) -> None:
    bin_path = os.path.join(version_dir, bin_name)
    real_bin_name = _real_binary_name(bin_name)
    real_bin_path = os.path.join(version_dir, real_bin_name)
    record_path = os.path.join(version_dir, ".install-complete.json")

    is_patched = os.path.exists(real_bin_path)
    bin_size = os.path.getsize(bin_path) if os.path.exists(bin_path) else None
    real_size = os.path.getsize(real_bin_path) if is_patched else None
    rec_bytes = None
    version_str = "standalone"
    if os.path.isfile(record_path):
        with open(record_path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        version_str = str(rec.get("version", "unknown"))
        if isinstance(rec.get("executable"), dict):
            rec_bytes = rec["executable"].get("bytes")

    print(
        f"Antigravity ACP status ({version_str}, {label}):\n"
        f"  directory: {version_dir}\n"
        f"  executable: {bin_name}\n"
        f"  patched: {is_patched}\n"
        f"  {bin_name} size: {bin_size}\n"
        f"  {real_bin_name} size: {real_size}\n"
        f"  .install-complete.json bytes: {rec_bytes}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Path to an Antigravity binary/directory (or 'active' for the active T3 Code release)",
    )
    parser.add_argument(
        "--target-dir",
        dest="target_dir",
        default=None,
        help="Explicit path to an Antigravity binary or directory",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="Target the active T3 Code bundled Antigravity release (default when no path is given)",
    )
    parser.add_argument(
        "--t3-home",
        default=os.environ.get("T3CODE_HOME", os.path.expanduser("~/.t3")),
        help="Path to T3 Code home directory (default: ~/.t3)",
    )
    parser.add_argument(
        "--release-id",
        default=None,
        help="Specific 64-char T3 release ID to patch (defaults to active.json)",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore the original unpatched Antigravity binary",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show patch status for the target directory without modifying files",
    )
    args = parser.parse_args()

    chosen_target = args.target_dir or ("active" if args.active else args.target)
    label, version_dir, bin_name = _resolve_target_dir(
        chosen_target, os.path.expanduser(args.t3_home), args.release_id
    )
    if args.status:
        status_directory(version_dir, label, bin_name)
    elif args.restore:
        restore_directory(version_dir, label, bin_name)
    else:
        patch_directory(version_dir, label, bin_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
