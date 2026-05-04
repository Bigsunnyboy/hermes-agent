from pathlib import Path

from hermes_local_agent_gateway.runner import CodexCliRunner


def test_builds_read_only_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/data-agent"),
        prompt="Analyze only.",
        mode="read",
    )

    assert command == [
        "codex",
        "exec",
        "--cd",
        "/home/projects/data-agent",
        "--sandbox",
        "read-only",
        "--json",
        "Analyze only.",
    ]


def test_builds_workspace_write_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/data-agent"),
        prompt="Fix tests.",
        mode="write",
    )

    assert "--sandbox" in command
    assert "workspace-write" in command
    assert "danger-full-access" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_builds_resume_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/data-agent"),
        prompt="Continue.",
        mode="read",
        codex_session_id="019dec87-6e36-77e0-9430-093e3fd31d10",
    )

    assert command == [
        "codex",
        "exec",
        "--cd",
        "/home/projects/data-agent",
        "--sandbox",
        "read-only",
        "--json",
        "resume",
        "019dec87-6e36-77e0-9430-093e3fd31d10",
        "Continue.",
    ]


def test_build_env_uses_managed_codex_home_without_user_hooks(tmp_path: Path) -> None:
    source_home = tmp_path / "source-codex-home"
    gateway_home = tmp_path / "gateway-codex-home"
    source_home.mkdir()
    (source_home / "auth.json").write_text("{}", encoding="utf-8")
    (source_home / "config.toml").write_text(
        "\n".join(
            [
                "notify = [\"node\", \"omx-notify.js\"]",
                'model_reasoning_effort = "high"',
                'developer_instructions = "load omx"',
                'model = "gpt-5.5"',
                "",
                "[mcp_servers.omx_state]",
                'command = "node"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (source_home / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    runner = CodexCliRunner(
        codex_executable="codex",
        codex_home=gateway_home,
        source_codex_home=source_home,
    )

    env = runner.build_env()

    assert env["CODEX_HOME"] == str(gateway_home)
    assert (gateway_home / "auth.json").is_symlink()
    assert not (gateway_home / "hooks.json").exists()
    config = (gateway_home / "config.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-5.5"' in config
    assert 'model_reasoning_effort = "high"' in config
    assert "notify" not in config
    assert "developer_instructions" not in config
    assert "mcp_servers" not in config
