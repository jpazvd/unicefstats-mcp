"""Integration regression tests for the EQA harness alignment guarantees.

These tests guard against three structural bugs that bit us in May 2026
(see `internal/BUG_resume_batch_row_alignment.md`):

  1. **Case-ordering mismatch** between benchmark and resume scripts.
  2. **Custom_id ↔ test-case binding** silently changing between save and
     load of a checkpoint.
  3. **Sample-CSV drift** between benchmark write and resume load
     producing misaligned states without a loud failure.

Approach: rather than spinning up a full benchmark + Anthropic API
roundtrip (slow, $$$), we test the indexing contract directly using
the `load_sample_in_benchmark_order` helper and the checkpoint
serialization layer. If any future refactor breaks the contract, these
tests fail loudly.
"""

from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("anthropic")
pytest.importorskip("dotenv")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))


@pytest.fixture(autouse=True)
def _patch_sample_csv():
    """Point benchmark_eqa at the mcp060 sample for these tests."""
    import benchmark_eqa

    repo_root = os.path.join(os.path.dirname(__file__), "..")
    sample = os.path.join(repo_root, "examples", "ground_truth_mcp060", "sample.csv")
    if not os.path.exists(sample):
        pytest.skip(
            f"Sample CSV not found at {sample}; this test needs the mcp060 "
            "ground truth to exercise the reorder."
        )
    orig_csv = benchmark_eqa.SAMPLE_CSV
    orig_gt = benchmark_eqa.GT_VALUES_CSV
    benchmark_eqa.SAMPLE_CSV = sample
    benchmark_eqa.GT_VALUES_CSV = os.path.join(
        os.path.dirname(sample), "ground_truth_values.csv"
    )
    yield
    benchmark_eqa.SAMPLE_CSV = orig_csv
    benchmark_eqa.GT_VALUES_CSV = orig_gt


class TestCanonicalOrdering:
    """The pos+T1+T2 reorder is the canonical contract — verify it."""

    def test_helper_returns_pos_t1_t2_in_order(self):
        from benchmark_eqa import load_sample_in_benchmark_order

        cases = load_sample_in_benchmark_order()
        types = [c.query_type for c in cases]
        # All POS first, then all T1, then all T2 — no interleaving
        first_t1 = next(i for i, t in enumerate(types) if t == "HALLUCINATION_T1")
        first_t2 = next(i for i, t in enumerate(types) if t == "HALLUCINATION_T2")
        last_pos = max(i for i, t in enumerate(types) if t == "POSITIVE")
        last_t1 = max(i for i, t in enumerate(types) if t == "HALLUCINATION_T1")
        assert last_pos < first_t1, "POS section bleeds into T1 — reorder broken"
        assert last_t1 < first_t2, "T1 section bleeds into T2 — reorder broken"

    def test_helper_with_limit_truncates_each_section(self):
        from benchmark_eqa import load_sample_in_benchmark_order

        limited = load_sample_in_benchmark_order(limit_per_section=2)
        # Each section limited to 2 → max 6 total
        assert len(limited) <= 6
        # And the proportions reflect what's actually in the sample
        pos_count = sum(1 for c in limited if c.query_type == "POSITIVE")
        t1_count = sum(1 for c in limited if c.query_type == "HALLUCINATION_T1")
        t2_count = sum(1 for c in limited if c.query_type == "HALLUCINATION_T2")
        assert pos_count <= 2 and t1_count <= 2 and t2_count <= 2
        # Limit doesn't break the ordering
        types = [c.query_type for c in limited]
        if "POSITIVE" in types and "HALLUCINATION_T1" in types:
            last_pos = max(i for i, t in enumerate(types) if t == "POSITIVE")
            first_t1 = next(i for i, t in enumerate(types) if t == "HALLUCINATION_T1")
            assert last_pos < first_t1

    def test_load_sample_returns_csv_order_not_benchmark_order(self):
        """load_sample() is intentionally CSV-order — that's the *raw* read.

        Callers that want canonical order MUST go through
        load_sample_in_benchmark_order. This test documents that
        contract: load_sample is NOT a stable index source for
        custom_ids.
        """
        from benchmark_eqa import load_sample, load_sample_in_benchmark_order

        csv_order = load_sample()
        bench_order = load_sample_in_benchmark_order()
        assert len(csv_order) == len(bench_order)
        # If someone "fixes" load_sample() to be in benchmark order,
        # this test will start passing identity by accident — which is
        # fine, but the explicit reorder helper should still exist as
        # the public API.
        # We test that they have the SAME cases (set-equal), just
        # potentially different orders.
        csv_qids = {(c.indicator_code, c.country_code, c.year, c.prompt_type)
                    for c in csv_order}
        bench_qids = {(c.indicator_code, c.country_code, c.year, c.prompt_type)
                      for c in bench_order}
        assert csv_qids == bench_qids


class TestCustomIdBinding:
    """The custom_id ↔ test-case binding must be deterministic across save/load."""

    def test_same_custom_id_same_case_across_loads(self):
        """Loading twice produces the same custom_id → test-case mapping."""
        from benchmark_eqa import load_sample_in_benchmark_order
        from benchmark_eqa_batch import QueryState

        cases1 = load_sample_in_benchmark_order()
        cases2 = load_sample_in_benchmark_order()
        # Build states for both loads and compare
        for idx, (tc1, tc2) in enumerate(zip(cases1, cases2, strict=True)):
            for cond in ("A", "B"):
                s1 = QueryState(idx, tc1, cond)
                s2 = QueryState(idx, tc2, cond)
                assert s1.custom_id == s2.custom_id == f"q{idx:04d}_{cond}"
                assert s1.tc.indicator_code == s2.tc.indicator_code
                assert s1.tc.country_code == s2.tc.country_code

    def test_custom_id_changes_under_wrong_ordering(self):
        """If a script forgets the reorder, custom_ids point at different cases.

        This is a negative test — it documents the bug we just fixed by
        showing what would go wrong without the helper.
        """
        from benchmark_eqa import load_sample, load_sample_in_benchmark_order

        csv_order = load_sample()
        bench_order = load_sample_in_benchmark_order()
        # Find at least one index where the two orderings diverge
        # (must exist because POS comes last in CSV but first in benchmark order)
        diverged = False
        for idx in range(min(len(csv_order), len(bench_order))):
            if (csv_order[idx].indicator_code != bench_order[idx].indicator_code
                or csv_order[idx].country_code != bench_order[idx].country_code):
                diverged = True
                break
        assert diverged, (
            "csv_order and benchmark_order produce identical sequences — "
            "either the sample is trivially small or load_sample now applies "
            "the reorder itself (and the helper is redundant)."
        )


class TestCheckpointAlignment:
    """The checkpoint round-trip must preserve custom_id ↔ test-case binding."""

    def test_save_load_preserves_state_to_case_binding(self, tmp_path):
        from benchmark_eqa import load_sample_in_benchmark_order
        from benchmark_eqa_batch import (
            QueryState,
            load_checkpoint,
            save_checkpoint,
        )

        cases = load_sample_in_benchmark_order()

        # Build states for the full sample, mark every B-side state with a
        # marker so we can verify it round-trips to the right case.
        states_by_id = {}
        for idx, tc in enumerate(cases):
            for cond in ("A", "B"):
                s = QueryState(idx, tc, cond)
                if cond == "B":
                    # Marker: we'll check that loaded_state.tc maps back to
                    # this exact (indicator, country, year) triple.
                    s.final_text = (
                        f"MARKER:{tc.indicator_code}|{tc.country_code}|{tc.year}"
                    )
                    s.done = True
                states_by_id[s.custom_id] = s

        path = str(tmp_path / "alignment_check.json")
        save_checkpoint(states_by_id, path, batch_ids=["msgbatch_test"])

        # Load with the SAME helper that saved — alignment must hold.
        loaded, _ = load_checkpoint(path, cases)

        for cid, s in loaded.items():
            if s.condition == "B" and s.final_text.startswith("MARKER:"):
                marker = s.final_text[len("MARKER:"):]
                expected = f"{s.tc.indicator_code}|{s.tc.country_code}|{s.tc.year}"
                assert marker == expected, (
                    f"Checkpoint round-trip misaligned: state {cid} has "
                    f"marker {marker!r} but loaded tc says {expected!r}"
                )

    def test_load_with_csv_order_misaligns_by_construction(self, tmp_path):
        """If the load uses the WRONG ordering, the marker check fails — proves
        the alignment guarantee is an ordering guarantee, not magic."""
        from benchmark_eqa import load_sample, load_sample_in_benchmark_order
        from benchmark_eqa_batch import (
            QueryState,
            load_checkpoint,
            save_checkpoint,
        )

        # Save with benchmark-order cases (the canonical path).
        bench_cases = load_sample_in_benchmark_order()
        states_by_id = {}
        for idx, tc in enumerate(bench_cases):
            for cond in ("A", "B"):
                s = QueryState(idx, tc, cond)
                if cond == "B":
                    s.final_text = (
                        f"MARKER:{tc.indicator_code}|{tc.country_code}|{tc.year}"
                    )
                    s.done = True
                states_by_id[s.custom_id] = s
        path = str(tmp_path / "wrong_order_check.json")
        save_checkpoint(states_by_id, path, batch_ids=[])

        # Load with CSV-order cases (the historical bug). The marker check
        # should now FAIL on most rows because cases[idx] is a different
        # test case than the state was saved with.
        csv_cases = load_sample()
        loaded, _ = load_checkpoint(path, csv_cases)

        misaligned = 0
        total = 0
        for _cid, s in loaded.items():
            if s.condition == "B" and s.final_text.startswith("MARKER:"):
                marker = s.final_text[len("MARKER:"):]
                expected = f"{s.tc.indicator_code}|{s.tc.country_code}|{s.tc.year}"
                total += 1
                if marker != expected:
                    misaligned += 1
        assert misaligned > 0, (
            "Loading with CSV-order cases produced perfect alignment — the "
            "ordering must be coincidentally identical (e.g., a tiny sample), "
            "or the bug class has been silently fixed elsewhere."
        )
        # Document the rate so a regression that suppresses the misalignment
        # without fixing the cause becomes visible.
        rate = misaligned / total if total else 0
        assert rate > 0.3, (
            f"CSV-order load misaligned only {rate:.1%} of rows — expected "
            f">30% on the mcp060 sample where POS+T1+T2 ≠ T1+T2+POS."
        )
