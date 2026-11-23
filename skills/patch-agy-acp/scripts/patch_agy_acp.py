#!/usr/bin/env python3
"""Patch an Antigravity binary (`antigravity` or `agy`) or the active T3 Code release.

Replaces the target executable with a Python 3 wrapper (moving the original
binary to `<name>.real`). Non-ACP subcommands (`--version`, `login`, etc.)
`execv` straight into `<name>.real`; `acp` sessions intercept JSON-RPC
lifecycle requests (`session/new`, `session/load`, `session/resume`,
`session/fork`) to:

1. Append enabled user MCP servers from `~/.gemini/config/mcp_config.json` and
   `<workspace>/.gemini/mcp_config.json` into `params.mcpServers` on live chat
   sessions (skipping empty-MCP probe and text-generation sessions).
2. Update `executable.bytes` in `.install-complete.json` when present (handling
   T3 Code's read-only release directory lock permissions) so
   `AntigravityInstallation.completedRelease` passes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import sys

WRAPPER_CODE = '''#!/usr/bin/env python3
"""ACP stdio wrapper for antigravity/agy: non-ACP exec passthrough and user MCP server merging."""

import json
import os
import signal
import subprocess
import sys

SESSION_METHODS = ("session/new", "session/load", "session/resume", "session/fork")


def _find_real_binary() -> str:
    self_path = os.path.abspath(__file__)
    here = os.path.dirname(self_path)
    base = os.path.basename(self_path)
    for name in (f"{base}.real", "antigravity.real", "agy.real"):
        cand = os.path.join(here, name)
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(f"Could not locate real Antigravity binary beside {self_path}")


def _is_acp_invocation(argv: list[str]) -> bool:
    for arg in argv:
        if arg == "acp":
            return True
        if not arg.startswith("-"):
            return False
    return False


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


def _maybe_inject_session_params(raw_line: bytes) -> bytes:
    if not raw_line.startswith(b"{"):
        return raw_line
    try:
        msg = json.loads(raw_line)
        if not isinstance(msg, dict) or msg.get("method") not in SESSION_METHODS:
            return raw_line
        params = msg.get("params")
        if not isinstance(params, dict):
            return raw_line

        extra_mcp = _load_user_mcp_servers(params)
        if not extra_mcp:
            return raw_line

        params["mcpServers"] = [*params["mcpServers"], *extra_mcp]
        return (json.dumps(msg, separators=(",", ":")) + "\\n").encode("utf-8")
    except Exception:
        return raw_line


def main() -> int:
    real_bin = _find_real_binary()
    argv = sys.argv[1:]
    if not _is_acp_invocation(argv):
        os.execv(real_bin, [real_bin, *argv])

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
            out_line = _maybe_inject_session_params(raw_line)
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


def _is_dir_locked(directory: str) -> bool:
    if os.name == "nt":
        return False
    return (stat.S_IMODE(os.stat(directory).st_mode) & stat.S_IWUSR) == 0


def _unlock_for_write(version_dir: str, paths: tuple[str, ...]) -> bool:
    """Temporarily add owner write bits so T3's 0500/0555/0400 lock permits patching."""
    if os.name == "nt":
        return False
    was_locked = _is_dir_locked(version_dir)
    dir_mode = stat.S_IMODE(os.stat(version_dir).st_mode)
    if (dir_mode & stat.S_IWUSR) == 0:
        os.chmod(version_dir, dir_mode | stat.S_IRWXU)
    for p in paths:
        if os.path.exists(p) and not os.path.islink(p):
            mode = stat.S_IMODE(os.stat(p).st_mode)
            if (mode & stat.S_IWUSR) == 0:
                os.chmod(p, mode | stat.S_IWUSR)
    return was_locked


def _relock_release(version_dir: str, bin_path: str, record_path: str) -> None:
    """Restore T3 Code's read-only release lock (0500 dir, 0555 bin, 0400 record)."""
    if os.name == "nt":
        return
    if os.path.isfile(bin_path) and not os.path.islink(bin_path):
        os.chmod(bin_path, 0o555)
    if os.path.isfile(record_path) and not os.path.islink(record_path):
        os.chmod(record_path, 0o400)
    os.chmod(version_dir, 0o500)


def patch_directory(version_dir: str, label: str, bin_name: str) -> None:
    bin_path = os.path.join(version_dir, bin_name)
    real_bin_path = os.path.join(version_dir, _real_binary_name(bin_name))
    record_path = os.path.join(version_dir, ".install-complete.json")
    record_bak_path = os.path.join(version_dir, ".install-complete.json.bak")

    was_locked = _unlock_for_write(
        version_dir, (bin_path, real_bin_path, record_path, record_bak_path)
    )
    try:
        if not os.path.exists(real_bin_path):
            if not os.path.exists(bin_path):
                raise FileNotFoundError(f"Missing binary at {bin_path}")
            shutil.move(bin_path, real_bin_path)

        if not os.path.exists(record_bak_path) and os.path.isfile(record_path):
            shutil.copy2(record_path, record_bak_path)

        with open(bin_path, "w", encoding="utf-8") as f:
            f.write(WRAPPER_CODE)
        os.chmod(bin_path, 0o555 if was_locked else 0o755)

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
    finally:
        if was_locked:
            _relock_release(version_dir, bin_path, record_path)

    print(
        f"Patched Antigravity ACP ({version_str}, {label}):\n"
        f"  directory: {version_dir}\n"
        f"  wrapper: {bin_path} ({new_size} bytes)\n"
        f"  real binary: {real_bin_path}"
        + (f"\n  record: {record_path}" if os.path.isfile(record_path) else "")
        + ("\n  release lock: restored (0500/0555/0400)" if was_locked else "")
    )


def restore_directory(version_dir: str, label: str, bin_name: str) -> None:
    bin_path = os.path.join(version_dir, bin_name)
    real_bin_path = os.path.join(version_dir, _real_binary_name(bin_name))
    record_path = os.path.join(version_dir, ".install-complete.json")
    record_bak_path = os.path.join(version_dir, ".install-complete.json.bak")

    if not os.path.exists(real_bin_path):
        print(f"Target {version_dir} ({label}) is not patched (no {real_bin_path} found).")
        return

    was_locked = _unlock_for_write(
        version_dir, (bin_path, real_bin_path, record_path, record_bak_path)
    )
    try:
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
    finally:
        if was_locked:
            _relock_release(version_dir, bin_path, record_path)

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
        f"  dir locked: {_is_dir_locked(version_dir)}\n"
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
