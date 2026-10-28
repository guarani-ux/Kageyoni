"""tests/test_subagent_forge.py
Test suite for Subagent Forge: P-N-S-C compiler, validator, PreToolUse hook,
sink verifier, SQLite append-only task ledger, and durable subagents.json mirror.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import pytest

from tools.subagent import (
    DEFAULT_ANTI_SLOP_BLACKLIST,
    GENESIS_PREV_HASH,
    SubagentEvent,
    SubagentLedger,
    SubagentTask,
    forge_contract,
    handle_hook_pre,
    install_hooks_config,
    validate_contract,
    verify_sink,
)


def test_forge_compilation_prompt_format():
    """Verify that forge_contract compiles a complete P-N-S-C prompt with anti-slop rules."""
    prompt, data = forge_contract(
        name="test-worker",
        role="Unit Tester",
        task="Execute tests across all components.",
        inputs=["tests/conftest.py", "tests/fixtures.json"],
        forego=["Mutating core code", "Adding external dependencies"],
        success=["All tests pass with exit code 0"],
        sink=["reports/test_output.json"],
        format_type="prompt",
    )

    assert "[SUBAGENT EXECUTION KERNEL: P-N-S-C]" in prompt
    assert "1. PAYLOAD:" in prompt
    assert "test-worker" in prompt
    assert "Unit Tester" in prompt
    assert "tests/conftest.py" in prompt

    assert "2. NEGATIVE BOUNDS (FOREGO):" in prompt
    assert "Mutating core code" in prompt
    for anti_slop in DEFAULT_ANTI_SLOP_BLACKLIST:
        assert anti_slop in prompt

    assert "3. SUCCESS INVARIANT (EPISTEMIC GATE):" in prompt
    assert "All tests pass with exit code 0" in prompt

    assert "4. COMPLETION SINK (PHYSICAL TERMINATION):" in prompt
    assert "reports/test_output.json" in prompt

    assert data["TypeName"] == "test-worker"
    assert data["Role"] == "Unit Tester"


def test_forge_compilation_json_format():
    """Verify that forge_contract with format_type='json' outputs valid JSON with proper structure."""
    json_str, data = forge_contract(
        name="json-scout",
        role="Discovery Scout",
        task="Scan filesystem for orphaned files.",
        format_type="json",
    )

    parsed = json.loads(json_str)
    assert parsed["TypeName"] == "json-scout"
    assert parsed["Role"] == "Discovery Scout"
    assert "Prompt" in parsed
    assert "contract" in parsed
    assert "payload" in parsed["contract"]
    assert "negative_bounds" in parsed["contract"]
    assert "success_invariant" in parsed["contract"]
    assert "completion_sink" in parsed["contract"]


def test_validate_valid_contract():
    """Verify that validate_contract succeeds on properly forged P-N-S-C prompts."""
    prompt, _ = forge_contract(
        name="worker",
        role="Builder",
        task="Build artifact",
        forego=["No deletions"],
        success=["Build exits 0"],
        sink=["dist/artifact.whl"],
    )

    is_valid, reason = validate_contract(prompt)
    assert is_valid is True
    assert "verified" in reason.lower()


def test_validate_missing_sections():
    """Verify that validate_contract rejects prompts missing any of the 4 P-N-S-C sections."""
    # Missing NEGATIVE BOUNDS
    broken_prompt = """
1. PAYLOAD:
   - Target: worker
   - Task: do something

3. SUCCESS INVARIANT:
   - Exits 0

4. COMPLETION SINK:
   - dist/output.txt
"""
    is_valid, reason = validate_contract(broken_prompt)
    assert is_valid is False
    assert "[2. NEGATIVE BOUNDS]" in reason

    # Missing COMPLETION SINK
    broken_prompt_2 = """
1. PAYLOAD:
   - Target: worker

2. NEGATIVE BOUNDS:
   - Forego slop

3. SUCCESS INVARIANT:
   - Exits 0
"""
    is_valid, reason = validate_contract(broken_prompt_2)
    assert is_valid is False
    assert "[4. COMPLETION SINK]" in reason


def test_validate_empty_section():
    """Verify that validate_contract rejects prompts with empty section bodies."""
    empty_section_prompt = """
1. PAYLOAD:
   - Target: worker
   - Task: do work

2. NEGATIVE BOUNDS:

3. SUCCESS INVARIANT:
   - Exits 0

4. COMPLETION SINK:
   - dist/output.txt
"""
    is_valid, reason = validate_contract(empty_section_prompt)
    assert is_valid is False
    assert "empty content" in reason.lower()
    assert "[2. NEGATIVE BOUNDS]" in reason


def test_hook_pre_unforged_prompt_denied():
    """Verify that handle_hook_pre denies unforged prompts with FM-FORGE-01."""
    payload = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": {
                "TypeName": "research",
                "Role": "Researcher",
                "Prompt": "Please do a quick survey of the code in tools/ and let me know what you find.",
            },
        }
    }

    result = handle_hook_pre(json.dumps(payload))
    assert result["decision"] == "deny"
    assert "FM-FORGE-01" in result["reason"]
    assert "Missing required P-N-S-C sections" in result["reason"]


def test_hook_pre_forged_prompt_allowed():
    """Verify that handle_hook_pre allows valid P-N-S-C forged contracts."""
    valid_prompt, _ = forge_contract(
        name="research",
        role="Researcher",
        task="Survey tools directory.",
        inputs=["tools/cartographer.py"],
        forego=["Writing to disk"],
        success=["Survey output complete"],
        sink=["reports/survey.md"],
    )

    payload = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": {
                "TypeName": "research",
                "Role": "Researcher",
                "Prompt": valid_prompt,
            },
        }
    }

    result = handle_hook_pre(json.dumps(payload))
    assert result["decision"] == "allow"
    assert "P-N-S-C Forge contract verified." in result["reason"]


def test_hook_pre_non_subagent_tool_allowed():
    """Verify that non-invoke_subagent tool calls bypass the forge check."""
    payload = {
        "toolCall": {
            "name": "read_file",
            "args": {"Path": "tools/subagent.py"},
        }
    }

    result = handle_hook_pre(json.dumps(payload))
    assert result["decision"] == "allow"
    assert "is not invoke_subagent" in result["reason"]


def test_verify_sink_functionality():
    """Verify that verify_sink correctly checks existence and byte thresholds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        good_file = tmp_path / "output.txt"
        good_file.write_text("Hello Subagent Forge! Non-empty deliverable.", encoding="utf-8")

        small_file = tmp_path / "small.txt"
        small_file.write_text("tiny", encoding="utf-8")

        nonexistent_file = tmp_path / "ghost.txt"

        # Case 1: Existing file >= min_bytes
        passed, diags = verify_sink([str(good_file)], min_bytes=10)
        assert passed is True
        assert any("[PASS]" in d for d in diags)

        # Case 2: File does not exist
        passed, diags = verify_sink([str(nonexistent_file)], min_bytes=1)
        assert passed is False
        assert any("does not exist" in d for d in diags)

        # Case 3: File exists but under byte threshold
        passed, diags = verify_sink([str(small_file)], min_bytes=100)
        assert passed is False
        assert any("bytes (required:" in d for d in diags)


def test_cli_subprocess_forge_and_validate():
    """Verify that the CLI can forge a contract and validate it via subshell pipelines."""
    forge_proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.subagent",
            "forge",
            "--name",
            "pipeline-agent",
            "--role",
            "Pipeline Auditor",
            "--task",
            "Verify CI artifacts",
            "--sink",
            "dist/ci.log",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    forged_output = forge_proc.stdout
    assert "[SUBAGENT EXECUTION KERNEL: P-N-S-C]" in forged_output

    # Pipe into validate
    val_proc = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "validate"],
        input=forged_output,
        capture_output=True,
        text=True,
    )
    assert val_proc.returncode == 0
    assert "[OK]" in val_proc.stdout


def test_cli_subprocess_hook_pre():
    """Verify that python -m tools.subagent hook pre handles un-forged and forged stdin payloads."""
    # 1. Un-forged prompt
    unforged_payload = json.dumps(
        {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Prompt": "Just summarize the code."},
            }
        }
    )
    proc_deny = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "hook", "pre"],
        input=unforged_payload,
        capture_output=True,
        text=True,
        check=True,
    )
    resp_deny = json.loads(proc_deny.stdout)
    assert resp_deny["decision"] == "deny"
    assert "FM-FORGE-01" in resp_deny["reason"]

    # 2. Forged prompt
    forged_prompt, _ = forge_contract(
        name="cli-agent",
        role="CLI Validator",
        task="Test hook pre invocation",
        sink=["reports/cli_test.json"],
    )
    forged_payload = json.dumps(
        {
            "toolCall": {
                "name": "invoke_subagent",
                "args": {"Prompt": forged_prompt},
            }
        }
    )
    proc_allow = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "hook", "pre"],
        input=forged_payload,
        capture_output=True,
        text=True,
        check=True,
    )
    resp_allow = json.loads(proc_allow.stdout)
    assert resp_allow["decision"] == "allow"


def test_hook_pre_corrupted_payload_fm_forge_02():
    """Verify that handle_hook_pre rejects malformed payloads with FM-FORGE-02 (force_ask)."""
    # 1. Non-string raw_input
    res_non_str = handle_hook_pre(12345)  # type: ignore
    assert res_non_str["decision"] == "force_ask"
    assert "FM-FORGE-02" in res_non_str["reason"]

    # 2. Corrupted JSON string
    res_corrupt_json = handle_hook_pre("{bad-json:")
    assert res_corrupt_json["decision"] == "force_ask"
    assert "FM-FORGE-02" in res_corrupt_json["reason"]

    # 3. JSON is not an object (e.g. list, integer, string literal)
    res_list = handle_hook_pre(json.dumps([1, 2, 3]))
    assert res_list["decision"] == "force_ask"
    assert "FM-FORGE-02" in res_list["reason"]

    res_int = handle_hook_pre("99999")
    assert res_int["decision"] == "force_ask"
    assert "FM-FORGE-02" in res_int["reason"]

    # 4. toolCall is not an object
    res_tool_not_obj = handle_hook_pre(json.dumps({"toolCall": "invoke_subagent"}))
    assert res_tool_not_obj["decision"] == "force_ask"
    assert "FM-FORGE-02" in res_tool_not_obj["reason"]


def test_hook_pre_type_guards_args_and_prompt():
    """Verify type guards when args is a serialized string, non-dict, or prompt is non-string."""
    forged_prompt, _ = forge_contract(
        name="string-args-agent",
        role="Tester",
        task="Test string args parsing",
        sink=["output.txt"],
    )

    # 1. args encoded as JSON string (common in some agent/MCP tool calling frameworks)
    payload_str_args = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": json.dumps({"Prompt": forged_prompt}),
        }
    }
    res_str_args = handle_hook_pre(json.dumps(payload_str_args))
    assert res_str_args["decision"] == "allow"

    # 2. args is a string with invalid JSON
    payload_bad_str_args = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": "not a json object",
        }
    }
    res_bad_str_args = handle_hook_pre(json.dumps(payload_bad_str_args))
    assert res_bad_str_args["decision"] == "deny"
    assert "FM-FORGE-01" in res_bad_str_args["reason"]

    # 3. args is a non-dict (e.g. integer or list)
    payload_int_args = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": 12345,
        }
    }
    res_int_args = handle_hook_pre(json.dumps(payload_int_args))
    assert res_int_args["decision"] == "deny"
    assert "FM-FORGE-01" in res_int_args["reason"]

    # 4. Prompt is not a string (e.g. integer, list)
    payload_int_prompt = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": {"Prompt": 42},
        }
    }
    res_int_prompt = handle_hook_pre(json.dumps(payload_int_prompt))
    assert res_int_prompt["decision"] == "deny"
    assert "FM-FORGE-01" in res_int_prompt["reason"]


def test_hook_pre_empty_section_evasion_fm_forge_03():
    """Verify that handle_hook_pre denies contracts with empty section content with FM-FORGE-03."""
    empty_section_prompt = """
[SUBAGENT EXECUTION KERNEL: P-N-S-C]
1. PAYLOAD:
   - Target: agent
   - Role: Tester
   - Assignment: Test something

2. NEGATIVE BOUNDS:

3. SUCCESS INVARIANT:
   - Exit 0

4. COMPLETION SINK:
   - reports/out.txt
"""
    payload = {
        "toolCall": {
            "name": "invoke_subagent",
            "args": {"Prompt": empty_section_prompt},
        }
    }
    result = handle_hook_pre(json.dumps(payload))
    assert result["decision"] == "deny"
    assert "FM-FORGE-03" in result["reason"]
    assert "Empty Section Evasion" in result["reason"]
    assert "[2. NEGATIVE BOUNDS]" in result["reason"]


def test_verify_sink_fm_forge_04():
    """Verify that verify_sink emits FM-FORGE-04 error diagnostics on missing or sub-threshold files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        missing_file = tmp_path / "ghost_artifact.json"
        undersized_file = tmp_path / "stub.txt"
        undersized_file.write_text("ok", encoding="utf-8")
        directory_sink = tmp_path / "some_dir"
        directory_sink.mkdir()

        # 1. Missing file triggers FM-FORGE-04
        passed, diags = verify_sink([str(missing_file)])
        assert passed is False
        assert any("FM-FORGE-04" in d for d in diags)
        assert any("Phantom Completion Sink" in d for d in diags)
        assert any("does not exist" in d for d in diags)

        # 2. Undersized file triggers FM-FORGE-04
        passed, diags = verify_sink([str(undersized_file)], min_bytes=100)
        assert passed is False
        assert any("FM-FORGE-04" in d for d in diags)
        assert any("bytes (required:" in d for d in diags)

        # 3. Directory path triggers FM-FORGE-04
        passed, diags = verify_sink([str(directory_sink)])
        assert passed is False
        assert any("FM-FORGE-04" in d for d in diags)
        assert any("not a regular file" in d for d in diags)


def test_install_hooks_config_merge():
    """Verify that install_hooks_config cleanly merges subagent_forge into existing hooks.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Case 1: Brand new installation
        installed_file = install_hooks_config(target_dir=tmp_path)
        assert installed_file.is_file()
        data = json.loads(installed_file.read_text(encoding="utf-8"))
        assert "subagent_forge" in data
        assert data["subagent_forge"]["enabled"] is True

        # Case 2: Clean merge with existing unrelated hooks
        existing_custom = {
            "pre_commit_linter": {
                "enabled": True,
                "PreToolUse": [{"matcher": "edit_file", "hooks": []}],
            },
            "custom_telemetry": {"endpoint": "https://telemetry.local"},
        }
        installed_file.write_text(json.dumps(existing_custom, indent=2), encoding="utf-8")

        # Run install_hooks_config again
        merged_file = install_hooks_config(target_dir=tmp_path)
        merged_data = json.loads(merged_file.read_text(encoding="utf-8"))

        # Check that existing keys were preserved
        assert "pre_commit_linter" in merged_data
        assert merged_data["pre_commit_linter"]["enabled"] is True
        assert "custom_telemetry" in merged_data
        # And subagent_forge was merged in
        assert "subagent_forge" in merged_data
        assert merged_data["subagent_forge"]["enabled"] is True

        # Case 3: Corrupted JSON in existing hooks.json recovers safely
        installed_file.write_text("{broken json...", encoding="utf-8")
        recovered_file = install_hooks_config(target_dir=tmp_path)
        recovered_data = json.loads(recovered_file.read_text(encoding="utf-8"))
        assert "subagent_forge" in recovered_data


def test_cli_exit_codes():
    """Verify CLI exit codes across subcommands (validate, verify-sink, hook, and help/errors)."""
    # 1. No subcommand -> exit 1
    proc_no_cmd = subprocess.run(
        [sys.executable, "-m", "tools.subagent"],
        capture_output=True,
        text=True,
    )
    assert proc_no_cmd.returncode == 1

    # 2. validate on invalid contract -> exit 1
    proc_val_fail = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "validate", "--prompt", "invalid prompt"],
        capture_output=True,
        text=True,
    )
    assert proc_val_fail.returncode == 1
    assert "FM-FORGE-01" in proc_val_fail.stderr

    # 3. validate on nonexistent file -> exit 1
    proc_val_nofile = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "validate", "--file", "nonexistent_file.txt"],
        capture_output=True,
        text=True,
    )
    assert proc_val_nofile.returncode == 1
    assert "not found" in proc_val_nofile.stderr

    # 4. verify-sink with no sinks provided -> exit 1
    proc_sink_noargs = subprocess.run(
        [sys.executable, "-m", "tools.subagent", "verify-sink"],
        capture_output=True,
        text=True,
    )
    assert proc_sink_noargs.returncode == 1
    assert "FM-FORGE-04" in proc_sink_noargs.stderr

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        good_file = tmp_path / "valid_sink.txt"
        good_file.write_text("Production output bytes", encoding="utf-8")

        # 5. verify-sink on valid existing file -> exit 0
        proc_sink_pass = subprocess.run(
            [sys.executable, "-m", "tools.subagent", "verify-sink", str(good_file), "--min-bytes", "10"],
            capture_output=True,
            text=True,
        )
        assert proc_sink_pass.returncode == 0
        assert "[PASS]" in proc_sink_pass.stdout

        # 6. verify-sink on missing file -> exit 1
        proc_sink_fail = subprocess.run(
            [sys.executable, "-m", "tools.subagent", "verify-sink", str(tmp_path / "missing.txt")],
            capture_output=True,
            text=True,
        )
        assert proc_sink_fail.returncode == 1
        assert "FM-FORGE-04" in proc_sink_fail.stderr


# ==============================================================================
# SUBAGENT TASK LEDGER & SUBAGENTS.JSON MIRROR TESTS
# ==============================================================================


def test_ledger_record_and_get_task():
    """Verify recording a subagent task and retrieving it by task_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_subagents.sqlite"
        json_path = tmp_path / "test_subagents.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)

        task = ledger.record_task(
            name="test-scout",
            role="Codebase Scout",
            task="Map codebase structure.",
            inputs=["tools/cartographer.py"],
            forego=["No deletes"],
            success=["Map exits 0"],
            sink=["reports/map.json"],
            prompt="[SUBAGENT EXECUTION KERNEL: P-N-S-C] ...",
            task_id="task_scout_001",
        )

        assert task.task_id == "task_scout_001"
        assert task.name == "test-scout"
        assert task.role == "Codebase Scout"
        assert task.status == "FORGED"
        assert task.inputs == ["tools/cartographer.py"]
        assert task.forego == ["No deletes"]
        assert task.success == ["Map exits 0"]
        assert task.sinks == ["reports/map.json"]

        fetched = ledger.get_task("task_scout_001")
        assert fetched is not None
        assert fetched.task_id == "task_scout_001"
        assert fetched.name == "test-scout"
        assert fetched.role == "Codebase Scout"
        assert fetched.status == "FORGED"

        # Nonexistent task returns None
        assert ledger.get_task("nonexistent_id") is None


def test_ledger_task_state_transitions():
    """Verify task state transitions: FORGED -> RUNNING -> COMPLETED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_subagents.sqlite"
        json_path = tmp_path / "test_subagents.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)

        task = ledger.record_task(
            name="transition-worker",
            role="Worker",
            task="Perform multi-stage transition.",
            task_id="task_trans_01",
        )
        assert task.status == "FORGED"
        assert task.completed_at is None

        # Transition to RUNNING
        running = ledger.update_task("task_trans_01", status="RUNNING")
        assert running is not None
        assert running.status == "RUNNING"
        assert running.completed_at is None

        # Transition to COMPLETED with receipt
        receipt = {"exit_code": 0, "tests_passed": 12}
        completed = ledger.update_task("task_trans_01", status="COMPLETED", receipt=receipt)
        assert completed is not None
        assert completed.status == "COMPLETED"
        assert completed.completed_at is not None
        assert completed.receipt["tests_passed"] == 12

        # Verify persisted in database
        final = ledger.get_task("task_trans_01")
        assert final is not None
        assert final.status == "COMPLETED"
        assert final.receipt["exit_code"] == 0


def test_ledger_cryptographic_chain_and_verify_integrity():
    """Verify cryptographic hash chaining across events and integrity verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "test_subagents.sqlite"
        json_path = tmp_path / "test_subagents.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)

        # Record multiple tasks and updates
        t1 = ledger.record_task(name="agent-1", task_id="t1")
        t2 = ledger.record_task(name="agent-2", task_id="t2")
        ledger.update_task("t1", status="RUNNING")
        ledger.update_task("t1", status="COMPLETED")
        ledger.update_task("t2", status="FAILED")

        events = ledger.get_events()
        assert len(events) == 5

        # Check sequence continuity and hash chaining
        assert events[0].sequence == 1
        assert events[0].prev_hash == GENESIS_PREV_HASH

        for i in range(1, len(events)):
            assert events[i].sequence == i + 1
            assert events[i].prev_hash == events[i - 1].event_hash

        # Run integrity verification
        valid, err = ledger.verify_integrity()
        assert valid is True
        assert err is None


def test_ledger_integrity_fails_on_tampering():
    """Verify that ledger.verify_integrity fails closed on sequence gap or payload tampering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "tamper_test.sqlite"
        json_path = tmp_path / "tamper_test.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        ledger.record_task(name="agent-1", task_id="t1")
        ledger.record_task(name="agent-2", task_id="t2")

        # 1. Verify initially valid
        valid, _ = ledger.verify_integrity()
        assert valid is True

        # 2. Tamper with an event payload directly in SQLite
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE subagent_events SET payload_json = '{\"tampered\": true}' WHERE sequence = 1")
        conn.commit()
        conn.close()

        # 3. Integrity check must now fail
        tampered_valid, tamper_err = ledger.verify_integrity()
        assert tampered_valid is False
        assert "Tampered record at sequence 1" in str(tamper_err)


def test_ledger_json_mirror_synchronization():
    """Verify that subagents.json mirror accurately reflects current SQLite state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "mirror_test.sqlite"
        json_path = tmp_path / "subagents.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path, auto_mirror=True)

        assert not json_path.exists()

        # Record task 1
        ledger.record_task(
            name="mirror-scout",
            role="Scout",
            task="Verify JSON mirror writeback",
            task_id="scout-1",
            sink=["reports/scout.json"],
        )

        assert json_path.is_file()
        mirror_content = json.loads(json_path.read_text(encoding="utf-8"))
        assert mirror_content["version"] == "1.0"
        assert mirror_content["total_subagents"] == 1
        assert len(mirror_content["subagents"]) == 1
        assert mirror_content["subagents"][0]["task_id"] == "scout-1"
        assert "scout-1" in mirror_content["by_id"]

        # Record task 2 and update task 1
        ledger.record_task(name="mirror-builder", task_id="builder-2")
        ledger.update_task("scout-1", status="COMPLETED")

        updated_mirror = json.loads(json_path.read_text(encoding="utf-8"))
        assert updated_mirror["total_subagents"] == 2
        assert updated_mirror["by_id"]["scout-1"]["status"] == "COMPLETED"
        assert updated_mirror["by_id"]["builder-2"]["status"] == "FORGED"


def test_ledger_complete_with_verify_sinks():
    """Verify complete_task behavior when validating completion sinks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "sink_test.sqlite"
        json_path = tmp_path / "sink_test.json"

        good_sink = tmp_path / "output.txt"
        good_sink.write_text("Durable subagent deliverable output bytes.", encoding="utf-8")

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)

        # Case 1: Sink exists -> complete succeeds
        ledger.record_task(
            name="sink-worker",
            task_id="task_good_sink",
            sink=[str(good_sink)],
        )
        passed, task, diags = ledger.complete_task("task_good_sink", verify_sinks=True, min_bytes=10)
        assert passed is True
        assert task is not None
        assert task.status == "COMPLETED"
        assert task.receipt["sink_verification"] == "PASSED"

        # Case 2: Sink missing -> complete fails and marks task FAILED
        missing_sink = tmp_path / "missing_deliverable.txt"
        ledger.record_task(
            name="failing-worker",
            task_id="task_bad_sink",
            sink=[str(missing_sink)],
        )
        failed_pass, failed_task, failed_diags = ledger.complete_task(
            "task_bad_sink", verify_sinks=True, min_bytes=1
        )
        assert failed_pass is False
        assert failed_task is not None
        assert failed_task.status == "FAILED"
        assert failed_task.receipt["sink_verification"] == "FAILED"


def test_ledger_list_filtering():
    """Verify filtering tasks in ledger by status and name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "filter_test.sqlite"
        json_path = tmp_path / "filter_test.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)

        ledger.record_task(name="alpha", task_id="a1", status="FORGED")
        ledger.record_task(name="beta", task_id="b1", status="COMPLETED")
        ledger.record_task(name="alpha", task_id="a2", status="COMPLETED")
        ledger.record_task(name="gamma", task_id="g1", status="FAILED")

        # Filter by status
        completed_tasks = ledger.list_tasks(status="COMPLETED")
        assert len(completed_tasks) == 2
        assert {t.task_id for t in completed_tasks} == {"b1", "a2"}

        # Filter by name
        alpha_tasks = ledger.list_tasks(name="alpha")
        assert len(alpha_tasks) == 2
        assert {t.task_id for t in alpha_tasks} == {"a1", "a2"}

        # Limit
        limited = ledger.list_tasks(limit=1)
        assert len(limited) == 1


def test_cli_ledger_record_and_list():
    """Verify CLI tools.subagent ledger record and ledger list commands via subprocess."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "cli_subagents.sqlite"
        json_path = tmp_path / "cli_subagents.json"

        # 1. Record task via CLI
        rec_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "record",
                "--name",
                "cli-recorder",
                "--role",
                "CLI Specialist",
                "--task",
                "Test CLI recording",
                "--task-id",
                "cli_task_001",
                "--sink",
                "out.txt",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert rec_proc.returncode == 0
        assert "[OK] Subagent task recorded: cli_task_001" in rec_proc.stdout

        # 2. List tasks via CLI with --json
        list_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "list",
                "--json",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert list_proc.returncode == 0
        tasks = json.loads(list_proc.stdout)
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "cli_task_001"
        assert tasks[0]["name"] == "cli-recorder"


def test_cli_ledger_show_and_update():
    """Verify CLI tools.subagent ledger show and update commands via subprocess."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "cli_update.sqlite"
        json_path = tmp_path / "cli_update.json"

        # Pre-seed via Python API
        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        ledger.record_task(name="worker", task_id="target_task", status="FORGED")

        # 1. CLI show
        show_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "show",
                "target_task",
                "--json",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        task_data = json.loads(show_proc.stdout)
        assert task_data["task_id"] == "target_task"
        assert task_data["status"] == "FORGED"

        # 2. CLI update
        up_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "update",
                "target_task",
                "--status",
                "RUNNING",
                "--receipt",
                json.dumps({"stage": "active"}),
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert up_proc.returncode == 0
        assert "[OK] Subagent task updated: target_task [RUNNING]" in up_proc.stdout

        # Verify update reflected in JSON mirror
        mirror = json.loads(json_path.read_text(encoding="utf-8"))
        assert mirror["by_id"]["target_task"]["status"] == "RUNNING"
        assert mirror["by_id"]["target_task"]["receipt"]["stage"] == "active"


def test_cli_ledger_complete_and_verify():
    """Verify CLI tools.subagent ledger complete and verify commands."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "cli_complete.sqlite"
        json_path = tmp_path / "cli_complete.json"

        sink_file = tmp_path / "deliverable.txt"
        sink_file.write_text("Verified delivery output.", encoding="utf-8")

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        ledger.record_task(name="completer", task_id="comp_01", sink=[str(sink_file)])

        # 1. Complete with sink verification via CLI
        comp_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "complete",
                "comp_01",
                "--verify-sinks",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert comp_proc.returncode == 0
        assert "[OK] Subagent task completed: comp_01 [COMPLETED]" in comp_proc.stdout

        # 2. Verify ledger integrity via CLI
        ver_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "verify",
                "--db",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert ver_proc.returncode == 0
        assert "[PASS] Subagent ledger cryptographic hash chain verified" in ver_proc.stdout


def test_cli_ledger_sync():
    """Verify CLI tools.subagent ledger sync regenerates subagents.json mirror."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "sync.sqlite"
        json_path = tmp_path / "subagents.json"

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        ledger.record_task(name="sync-worker", task_id="s1")

        # Remove JSON mirror
        json_path.unlink()
        assert not json_path.exists()

        # Run sync via CLI
        sync_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "ledger",
                "sync",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert sync_proc.returncode == 0
        assert "[OK] Subagents mirror synchronized to:" in sync_proc.stdout
        assert json_path.is_file()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["total_subagents"] == 1
        assert "s1" in data["by_id"]


def test_cli_forge_with_record_flag():
    """Verify that forge --record automatically persists task to SQLite and JSON mirror."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "forge_rec.sqlite"
        json_path = tmp_path / "forge_rec.json"

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "forge",
                "--name",
                "auto-recorded-agent",
                "--role",
                "Forge Recorder",
                "--task",
                "Compile and record",
                "--task-id",
                "auto_001",
                "--sink",
                "dist/out.json",
                "--record",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
        assert "[SUBAGENT EXECUTION KERNEL: P-N-S-C]" in proc.stdout

        # Verify task was recorded in SQLite and JSON mirror
        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        task = ledger.get_task("auto_001")
        assert task is not None
        assert task.name == "auto-recorded-agent"
        assert task.status == "FORGED"

        mirror = json.loads(json_path.read_text(encoding="utf-8"))
        assert "auto_001" in mirror["by_id"]


def test_cli_verify_sink_with_task_id():
    """Verify that verify-sink --task-id automatically completes task in ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "verify_sink_ledger.sqlite"
        json_path = tmp_path / "verify_sink_ledger.json"

        sink_file = tmp_path / "finished_output.txt"
        sink_file.write_text("Finished deliverable output bytes.", encoding="utf-8")

        ledger = SubagentLedger(db_path=db_path, json_path=json_path)
        ledger.record_task(
            name="sink-finisher",
            task_id="finish_01",
            sink=[str(sink_file)],
        )

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.subagent",
                "verify-sink",
                str(sink_file),
                "--task-id",
                "finish_01",
                "--min-bytes",
                "5",
                "--db",
                str(db_path),
                "--json-path",
                str(json_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
        assert "[PASS]" in proc.stdout

        # Verify task in ledger is now COMPLETED
        updated = ledger.get_task("finish_01")
        assert updated is not None
        assert updated.status == "COMPLETED"
