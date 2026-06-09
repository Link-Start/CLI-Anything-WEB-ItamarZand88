import json

import click
import pytest
from cli_web_core.doctor import register_doctor_command, run_doctor
from click.testing import CliRunner


@pytest.fixture()
def demo_cli():
    @click.group()
    def cli():
        """Demo CLI."""

    register_doctor_command(cli, app_name="demo-doctor-test")
    return cli


def test_doctor_registers_command(demo_cli):
    assert "doctor" in demo_cli.commands


def test_doctor_runs_and_reports(demo_cli):
    result = CliRunner().invoke(demo_cli, ["doctor"])
    assert "python:" in result.output
    assert "entry point:" in result.output
    # No fail-level checks expected in a clean env (warns are fine)
    assert result.exit_code == 0


def test_doctor_json_envelope(demo_cli):
    result = CliRunner().invoke(demo_cli, ["doctor", "--json"])
    payload = json.loads(result.output)
    assert payload["success"] is True
    names = [c["name"] for c in payload["data"]["checks"]]
    assert "python" in names and "config dir" in names


def test_run_doctor_no_auth_module_is_ok():
    checks = {c.name: c for c in run_doctor("demo-doctor-test", "demo_doctor_test")}
    assert checks["auth"].status == "ok"
    assert "public site" in checks["auth"].detail


def test_run_doctor_auth_cli_warns_without_auth_file(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLI_WEB_LINKEDIN_AUTH_JSON", raising=False)
    checks = {c.name: c for c in run_doctor("linkedin", "linkedin")}
    assert checks["auth file"].status == "warn"
    assert "auth login" in checks["auth file"].detail


def test_run_doctor_env_var_short_circuits(monkeypatch):
    monkeypatch.setenv("CLI_WEB_LINKEDIN_AUTH_JSON", '{"li_at": "x"}')
    checks = {c.name: c for c in run_doctor("linkedin", "linkedin")}
    assert checks["auth source"].status == "ok"


def test_run_doctor_flags_world_readable_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLI_WEB_LINKEDIN_AUTH_JSON", raising=False)
    cfg = tmp_path / ".config" / "cli-web-linkedin"
    cfg.mkdir(parents=True)
    auth = cfg / "auth.json"
    auth.write_text('{"li_at": "x"}')
    auth.chmod(0o644)
    checks = {c.name: c for c in run_doctor("linkedin", "linkedin")}
    assert checks["auth file"].status == "ok"
    assert checks["auth file permissions"].status == "warn"
    assert "chmod 600" in checks["auth file permissions"].detail
    assert checks["auth file format"].status == "ok"
