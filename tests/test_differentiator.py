"""Tests for the v1.0.0 differentiator helper.

Locks in the behavior that explain_difference() returns informative
one-line descriptions for common UNICEF code-family suffixes, and
gracefully degrades to either the raw suffix or the empty string when
no curated meaning applies.
"""

from __future__ import annotations

from unicefstats_mcp.differentiator import explain_difference


class TestExplainDifferenceMortalityFamily:
    """The CME_MR* mortality family is the canonical use case — four
    age-bracket variants that look almost identical to a model."""

    def test_neonatal_recognized(self):
        fam = ["CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"]
        assert "neonatal" in explain_difference("CME_MRM0", fam).lower()

    def test_under_five_recognized_and_marks_headline(self):
        fam = ["CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"]
        result = explain_difference("CME_MRY0T4", fam)
        assert "under-five" in result.lower()
        # SDG 3.2.1 headline should be marked
        assert "3.2.1" in result

    def test_infant_recognized(self):
        fam = ["CME_MRM0", "CME_MRY0", "CME_MRY0T4", "CME_MRY1T4"]
        assert "infant" in explain_difference("CME_MRY0", fam).lower()


class TestExplainDifferenceMethodologyVariants:
    """The empirical pathology from v9 Arm B — ECD_CHLD_LMPSL family
    with _MERGE / _PRXY suffixes — should produce informative diffs."""

    def test_merge_methodology(self):
        fam = ["ECD_CHLD_LMPSL", "ECD_CHLD_LMPSL_MERGE", "ECD_CHLD_LMPSL_PRXY"]
        assert "merged" in explain_difference("ECD_CHLD_LMPSL_MERGE", fam).lower()

    def test_proxy_methodology(self):
        fam = ["ECD_CHLD_LMPSL", "ECD_CHLD_LMPSL_MERGE", "ECD_CHLD_LMPSL_PRXY"]
        assert "proxy" in explain_difference("ECD_CHLD_LMPSL_PRXY", fam).lower()

    def test_base_variant_marked_canonical(self):
        """The code that IS the common prefix gets a special 'base'
        description so the model knows it's the un-suffixed canonical."""
        fam = ["ECD_CHLD_LMPSL", "ECD_CHLD_LMPSL_MERGE", "ECD_CHLD_LMPSL_PRXY"]
        result = explain_difference("ECD_CHLD_LMPSL", fam)
        assert "base" in result.lower() or "canonical" in result.lower()


class TestExplainDifferenceImmunization:
    """IM_DTP1 vs IM_DTP3 — same vaccine, different dose; the model
    needs to see the dose distinction explicitly."""

    # Use the realistic vaccination family (5 vaccines) so the common
    # prefix stays at "IM_" and suffixes are "DTP1", "DTP3", "BCG", etc.
    # A 2-code family [IM_DTP1, IM_DTP3] would have common prefix
    # "IM_DTP" and degenerate suffixes "1"/"3" — not a realistic case
    # (the _AMBIGUOUS dict's "vaccination coverage" entry has 5 codes).
    VACCINE_FAMILY = ["IM_BCG", "IM_DTP1", "IM_DTP3", "IM_MCV1", "IM_MCV2"]

    def test_dtp1_recognized(self):
        result = explain_difference("IM_DTP1", self.VACCINE_FAMILY)
        assert "dtp" in result.lower()
        assert "1st" in result.lower() or "first" in result.lower()

    def test_dtp3_recognized_as_sdg_headline(self):
        result = explain_difference("IM_DTP3", self.VACCINE_FAMILY)
        assert "dtp" in result.lower()
        # SDG 3.b.1 headline
        assert "3.b.1" in result or "headline" in result.lower()

    def test_bcg_recognized(self):
        result = explain_difference("IM_BCG", self.VACCINE_FAMILY)
        assert "bcg" in result.lower() or "tuberculosis" in result.lower()


class TestExplainDifferenceFallbacks:
    """When the suffix isn't in the curated mapping, the helper falls
    back gracefully — surface the raw suffix so the model can at least
    see what varies, but never invent a plain-English meaning."""

    def test_unknown_suffix_surfaces_raw(self):
        fam = ["FOO_BAR_XYZZY", "FOO_BAR_PLUGH"]
        result = explain_difference("FOO_BAR_XYZZY", fam)
        # Should mention the suffix even if not curated
        assert "XYZZY" in result

    def test_single_candidate_returns_empty(self):
        """No siblings means no contrast — empty string."""
        assert explain_difference("CME_MRY0T4", ["CME_MRY0T4"]) == ""

    def test_code_not_in_list_returns_empty(self):
        """Defensive: don't differentiate a code that isn't in the list."""
        assert explain_difference("FOO", ["BAR", "BAZ"]) == ""

    def test_marriage_age_cutoff(self):
        """U18 / U15 suffixes are common in marriage indicators."""
        fam = ["PT_F_15-19_MRD", "PT_F_20-24_MRD_U15", "PT_F_20-24_MRD_U18"]
        result = explain_difference("PT_F_20-24_MRD_U18", fam)
        # The token-level matcher should pick up U18
        assert "18" in result
