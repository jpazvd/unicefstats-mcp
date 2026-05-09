"""Tests for the wave-state checkpoint persistence layer.

These checkpoints are the resume mechanism that replaces the legacy
`replay_existing_wave` live-tool-re-dispatch path which produced
row-misaligned parquets (see `internal/BUG_resume_batch_row_alignment.md`).

The test fixture builds a synthetic `QueryState` with realistic field
shapes — list-of-dict messages, list-of-dict tool_calls, primitive
counters — and verifies that `state_to_dict` → `json.dumps` →
`json.loads` → `state_from_dict` produces a state whose every field
equals the original.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# `benchmark_eqa.py` imports `anthropic` at module top (it's the batch
# harness's API client). The MCP server itself doesn't depend on it,
# and CI's `[dev]` extras don't install it. Skip these tests cleanly
# rather than failing collection when the integration harness isn't
# importable. Same goes for `dotenv`, used by benchmark_eqa_batch.py
# to load API keys.
pytest.importorskip("anthropic")
pytest.importorskip("dotenv")

# Resume_batch_run.py and benchmark_eqa_batch.py expect to be importable
# from the examples directory as siblings. Match that pattern.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

from benchmark_eqa import TestCase  # noqa: E402
from benchmark_eqa_batch import (  # noqa: E402
    CHECKPOINT_SCHEMA_VERSION,
    QueryState,
    load_checkpoint,
    save_checkpoint,
    state_from_dict,
    state_to_dict,
)


@pytest.fixture
def synthetic_tc():
    """A minimal TestCase that satisfies the dataclass shape."""
    return TestCase(
        indicator_code="CME_MRY0T4",
        indicator_name="Under-five mortality rate",
        unit="deaths_per_1000",
        country_code="BRA",
        country_name="Brazil",
        year=2023,
        query_type="POSITIVE",
        prompt_type="direct",
        prompt_text="What was Under-five mortality rate for Brazil in 2023?",
        ground_truth_value=14.2,
        ground_truth_latest_year=2024,
    )


@pytest.fixture
def populated_state(synthetic_tc):
    """A QueryState that has been advanced through ~3 waves of activity."""
    s = QueryState(query_idx=42, tc=synthetic_tc, condition="B")
    s.messages = [
        {"role": "user", "content": synthetic_tc.prompt_text},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Let me search for that indicator."},
            {"type": "tool_use", "id": "tu_1", "name": "search_indicators",
             "input": {"query": "under-five mortality"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": '{"results": [{"code": "CME_MRY0T4"}]}'},
        ]},
    ]
    s.done = False
    s.final_text = "Working on it..."
    s.tool_error = None
    s.tool_calls = [
        {"tool": "search_indicators", "input": {"query": "under-five mortality"}},
    ]
    s.rounds = 2
    s.tokens_input = 12345
    s.tokens_output = 678
    s.cache_creation = 0
    s.cache_read = 9876
    s.first_wave_started_at = 1714867200.0
    return s


class TestStateRoundTrip:
    """state_to_dict ↔ state_from_dict preserves every field."""

    def test_basic_roundtrip(self, populated_state, synthetic_tc):
        d = state_to_dict(populated_state)
        # Verify dict is JSON-serialisable (no exotic types like datetime, bytes)
        json_str = json.dumps(d)
        d_reloaded = json.loads(json_str)
        rebuilt = state_from_dict(d_reloaded, synthetic_tc)

        assert rebuilt.query_idx == populated_state.query_idx
        assert rebuilt.condition == populated_state.condition
        assert rebuilt.messages == populated_state.messages
        assert rebuilt.done == populated_state.done
        assert rebuilt.final_text == populated_state.final_text
        assert rebuilt.tool_error == populated_state.tool_error
        assert rebuilt.tool_calls == populated_state.tool_calls
        assert rebuilt.rounds == populated_state.rounds
        assert rebuilt.tokens_input == populated_state.tokens_input
        assert rebuilt.tokens_output == populated_state.tokens_output
        assert rebuilt.cache_creation == populated_state.cache_creation
        assert rebuilt.cache_read == populated_state.cache_read
        assert rebuilt.first_wave_started_at == populated_state.first_wave_started_at

    def test_custom_id_stable_across_roundtrip(self, populated_state, synthetic_tc):
        """custom_id is the lookup key for batch results — must survive."""
        d = state_to_dict(populated_state)
        rebuilt = state_from_dict(d, synthetic_tc)
        assert rebuilt.custom_id == populated_state.custom_id == "q0042_B"

    def test_done_state_preserved(self, synthetic_tc):
        """A `done=True` state with final_text round-trips."""
        s = QueryState(query_idx=0, tc=synthetic_tc, condition="A")
        s.done = True
        s.final_text = "I cannot answer without data access."
        s.rounds = 1
        s.tokens_input = 21
        s.tokens_output = 148

        d = state_to_dict(s)
        rebuilt = state_from_dict(d, synthetic_tc)
        assert rebuilt.done is True
        assert rebuilt.final_text == "I cannot answer without data access."
        assert rebuilt.rounds == 1

    def test_tc_not_serialised(self, populated_state):
        """The TestCase is intentionally NOT in the dict — it's reconstructed
        from `cases[idx]` at load time. Verifies we don't accidentally
        bloat the checkpoint with redundant metadata that could go stale."""
        d = state_to_dict(populated_state)
        assert "tc" not in d
        assert "indicator_code" not in d  # also not flattened in by mistake


class TestSaveLoadCheckpoint:
    """End-to-end save → atomic-rename → load."""

    def test_save_and_load(self, populated_state, synthetic_tc, tmp_path):
        states_by_id = {populated_state.custom_id: populated_state}
        # Need at least 43 cases for query_idx=42 to be reachable
        cases = [synthetic_tc] * 50
        path = str(tmp_path / "ckpt.json")

        save_checkpoint(states_by_id, path, batch_ids=["msgbatch_aaa", "msgbatch_bbb"])
        assert os.path.exists(path)
        # Verify the .tmp companion got cleaned up by the atomic rename
        assert not os.path.exists(f"{path}.tmp")

        loaded_states, loaded_batch_ids = load_checkpoint(path, cases)
        assert len(loaded_states) == 1
        assert "q0042_B" in loaded_states
        assert loaded_batch_ids == ["msgbatch_aaa", "msgbatch_bbb"]

        s = loaded_states["q0042_B"]
        assert s.tokens_input == 12345
        assert s.tool_calls[0]["tool"] == "search_indicators"

    def test_atomic_write_via_tmp(self, populated_state, synthetic_tc, tmp_path):
        """save_checkpoint must write through a .tmp + rename so a crash
        mid-write doesn't leave a half-written file that crashes load."""
        path = str(tmp_path / "atomic.json")
        save_checkpoint({populated_state.custom_id: populated_state}, path,
                        batch_ids=[])
        assert os.path.exists(path)
        # The temp file should not linger after a successful rename
        assert not os.path.exists(f"{path}.tmp")

    def test_unsupported_schema_version_raises(self, tmp_path, synthetic_tc):
        path = str(tmp_path / "bad_schema.json")
        with open(path, "w") as f:
            json.dump({"schema_version": 99, "states": [], "batch_ids": []}, f)
        with pytest.raises(ValueError, match="Unsupported checkpoint schema_version"):
            load_checkpoint(path, [synthetic_tc])

    def test_query_idx_out_of_range_raises(self, tmp_path, synthetic_tc):
        """If the sample CSV shrank between save and load, a checkpoint
        referencing query_idx=999 should error rather than silently
        misalign by reusing a wrong test case."""
        path = str(tmp_path / "stale_ckpt.json")
        with open(path, "w") as f:
            json.dump({
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "states": [{
                    "query_idx": 999, "condition": "A", "messages": [],
                    "done": True, "final_text": "", "tool_error": None,
                    "tool_calls": [], "rounds": 0, "tokens_input": 0,
                    "tokens_output": 0, "cache_creation": 0, "cache_read": 0,
                    "first_wave_started_at": None,
                }],
                "batch_ids": [],
            }, f)
        with pytest.raises(ValueError, match="query_idx=999.*only 1 test cases"):
            load_checkpoint(path, [synthetic_tc])

    def test_empty_states_loads_cleanly(self, tmp_path):
        path = str(tmp_path / "empty.json")
        with open(path, "w") as f:
            json.dump({
                "schema_version": CHECKPOINT_SCHEMA_VERSION,
                "states": [], "batch_ids": [],
            }, f)
        states, batch_ids = load_checkpoint(path, [])
        assert states == {}
        assert batch_ids == []


class TestSchemaVersion:
    """The schema version is part of the public contract."""

    def test_version_in_payload(self, populated_state, tmp_path):
        path = str(tmp_path / "v.json")
        save_checkpoint({populated_state.custom_id: populated_state}, path,
                        batch_ids=[])
        with open(path) as f:
            payload = json.load(f)
        assert payload["schema_version"] == CHECKPOINT_SCHEMA_VERSION
        assert "n_states" in payload  # convenience field for grep-debugging
