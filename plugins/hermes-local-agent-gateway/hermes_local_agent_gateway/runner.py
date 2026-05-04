from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


class CodexCliRunner:
    def __init__(
        self,
        *,
        codex_executable: str,
        codex_home: Path | None = None,
        source_codex_home: Path | None = None,
    ) -> None:
        self.codex_executable = codex_executable
        self.codex_home = codex_home or _default_gateway_codex_home()
        self.source_codex_home = source_codex_home or _default_source_codex_home()

    def build_command(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        codex_session_id: str | None = None,
    ) -> list[str]:
        sandbox = "read-only" if mode == "read" else "workspace-write"
        command = [
            self.codex_executable,
            "exec",
            "--cd",
            str(project_path),
            "--sandbox",
            sandbox,
            "--json",
        ]
        if codex_session_id:
            command.extend(["resume", codex_session_id, prompt])
        else:
            command.append(prompt)
        return command

    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        codex_session_id: str | None = None,
    ) -> dict[str, Any]:
        command = self.build_command(
            project_path=project_path,
            prompt=prompt,
            mode=mode,
            codex_session_id=codex_session_id,
        )
        started = time.monotonic()
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(
                command,
                text=True,
                stdout=stdout,
                stderr=stderr,
                check=False,
                env=self.build_env(),
            )
        return {
            "command": command,
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "codex_session_id": _extract_thread_id(stdout_path),
        }

    def build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(_prepare_gateway_codex_home(self.codex_home, self.source_codex_home))
        return env


def _default_gateway_codex_home() -> Path:
    return Path.home() / ".hermes" / "codex_home"


def _default_source_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def _prepare_gateway_codex_home(codex_home: Path, source_codex_home: Path) -> Path:
    codex_home.mkdir(parents=True, exist_ok=True)
    _ensure_symlink(source_codex_home / "auth.json", codex_home / "auth.json")
    _write_sanitized_config(source_codex_home / "config.toml", codex_home / "config.toml")
    return codex_home


def _ensure_symlink(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        return
    if not source.exists():
        return
    destination.symlink_to(source)


def _write_sanitized_config(source: Path, destination: Path) -> None:
    if destination.is_symlink():
        destination.unlink()
    if destination.exists():
        return
    if not source.exists():
        return
    allowed_keys = {
        "model",
        "model_reasoning_effort",
        "model_context_window",
        "model_auto_compact_token_limit",
    }
    lines: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        key = stripped.split("=", 1)[0].strip()
        if key in allowed_keys:
            lines.append(line)
    if lines:
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _extract_thread_id(stdout_path: Path) -> str | None:
    try:
        with stdout_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    thread_id = event.get("thread_id")
                    return str(thread_id) if thread_id else None
    except FileNotFoundError:
        return None
    return None
