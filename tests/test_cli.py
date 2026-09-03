"""Tests for CLI user-facing behavior: friendly errors and actionable guidance."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from src.cli import cli

runner = CliRunner()


def write_config(dir_path: str, data: dict) -> None:
    with open(f"{dir_path}/qa-config.json", "w") as f:
        json.dump(data, f)


def test_run_missing_config_prints_friendly_error() -> None:
    """run must not dump a traceback when qa-config.json is missing."""
    result = runner.invoke(cli, ["run"])
    assert result.exit_code == 1
    assert "Config file not found" in result.output
    assert "Traceback" not in result.output


def test_crawl_missing_config_prints_friendly_error() -> None:
    result = runner.invoke(cli, ["crawl"])
    assert result.exit_code == 1
    assert "Config file not found" in result.output
    assert "Traceback" not in result.output


def test_hint_add_missing_config_prints_friendly_error() -> None:
    result = runner.invoke(cli, ["hint", "add", "checkout is critical"])
    assert result.exit_code == 1
    assert "Config file not found" in result.output
    assert "Traceback" not in result.output


def test_invalid_json_config_prints_friendly_error() -> None:
    with runner.isolated_filesystem():
        with open("qa-config.json", "w") as f:
            f.write('{"target_url":')
        result = runner.invoke(cli, ["coverage"])
        assert result.exit_code == 1
        assert "not valid JSON" in result.output
        assert "Traceback" not in result.output


def test_execute_missing_plan_file_prints_friendly_error() -> None:
    with runner.isolated_filesystem():
        write_config(".", {"target_url": "https://example.com"})
        result = runner.invoke(cli, ["execute", "--plan-file", "nope.json"])
        assert result.exit_code == 1
        assert "Test plan file not found" in result.output
        assert "Traceback" not in result.output


def test_coverage_gaps_missing_site_model_prints_actionable_hint() -> None:
    with runner.isolated_filesystem():
        write_config(".", {"target_url": "https://example.com"})
        result = runner.invoke(cli, ["coverage", "--gaps"])
        assert result.exit_code == 0
        assert "No site model found" in result.output
        assert "python -m src.cli crawl" in result.output


def test_init_guidance_uses_module_invocation() -> None:
    """Help text must match the documented invocation form (README uses python -m src.cli)."""
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "--target", "https://example.com"])
        assert result.exit_code == 0
        assert "python -m src.cli run" in result.output
        assert "python -m src.cli hint add" in result.output
        assert "qa-framework run" not in result.output


def test_hint_flow_roundtrip() -> None:
    with runner.isolated_filesystem():
        write_config(".", {"target_url": "https://example.com"})
        result = runner.invoke(cli, ["hint", "add", "checkout is critical"])
        assert result.exit_code == 0
        assert "Added hint" in result.output

        result = runner.invoke(cli, ["hint", "list"])
        assert result.exit_code == 0
        assert "checkout is critical" in result.output

        result = runner.invoke(cli, ["hint", "clear"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["hint", "list"])
        assert result.exit_code == 0
        assert "No hints configured" in result.output
