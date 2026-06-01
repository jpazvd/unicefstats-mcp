"""Tests for the indicator-name resolver (v0.7.0)."""

from __future__ import annotations

import pytest

from unicefstats_mcp.indicator_resolver import (
    _normalize,
    resolve_indicator,
    resolve_indicators,
)


class TestNormalize:
    """The normalize helper underpins every lookup; check edge cases."""

    def test_lowercases(self):
        assert _normalize("Neonatal Mortality Rate") == "neonatal mortality rate"

    def test_strips_diacritics(self):
        assert _normalize("Côte d'Ivoire") == "cote divoire"

    def test_keeps_hyphens(self):
        # Hyphens matter for codes like ED_15-24_LR and names like "Under-five".
        assert _normalize("Under-five mortality") == "under-five mortality"

    def test_collapses_internal_whitespace(self):
        assert _normalize("Height-for-age   <-2 SD") == "height-for-age -2 sd"

    def test_drops_unknown_punctuation(self):
        # `<` is neither alnum nor in the separator list; should disappear.
        assert "<" not in _normalize("Height-for-age <-2 SD")

    def test_treats_parentheses_as_separators(self):
        assert _normalize("Wasting (severe)") == "wasting severe"

    def test_returns_empty_for_non_string(self):
        assert _normalize(None) == ""  # type: ignore[arg-type]
        assert _normalize(123) == ""  # type: ignore[arg-type]


class TestCodePassthrough:
    """Inputs that already look like valid codes return code_passthrough."""

    def test_canonical_uppercase_code(self):
        r = resolve_indicator("CME_MRM0")
        assert r.status == "code_passthrough"
        assert r.code == "CME_MRM0"
        assert r.name == "Neonatal mortality rate"

    def test_lowercase_code_is_normalized(self):
        r = resolve_indicator("cme_mrm0")
        assert r.status == "code_passthrough"
        assert r.code == "CME_MRM0"

    def test_whitespace_stripped(self):
        r = resolve_indicator("  CME_MRM0  ")
        assert r.status == "code_passthrough"
        assert r.code == "CME_MRM0"

    def test_tier_2_parent_still_passes_through(self):
        # CME (without suffix) is a tier=2 category. Code passthrough doesn't
        # filter on tier — the SDMX endpoint will decide what's queryable.
        r = resolve_indicator("CME")
        assert r.status == "code_passthrough"
        assert r.code == "CME"


class TestSynonymMatch:
    """Curated synonyms resolve to canonical leaf codes."""

    @pytest.mark.parametrize(
        "synonym,expected_code",
        [
            ("neonatal mortality", "CME_MRM0"),
            ("Neonatal Mortality Rate", "CME_MRM0"),
            ("NMR", "CME_MRM0"),
            ("infant mortality", "CME_MRY0"),
            ("IMR", "CME_MRY0"),
            ("under-five mortality", "CME_MRY0T4"),
            ("Under Five Mortality Rate", "CME_MRY0T4"),
            ("U5MR", "CME_MRY0T4"),
            ("stillbirth rate", "CME_SBR"),
            ("SBR", "CME_SBR"),
            ("stunting", "NT_ANT_HAZ_NE2"),
            ("wasting", "NT_ANT_WHZ_NE2"),
            ("underweight", "NT_ANT_WAZ_NE2"),
            ("overweight", "NT_ANT_WHZ_PO2"),
            ("low birth weight", "NT_BW_LBW"),
            ("LBW", "NT_BW_LBW"),
            ("primary completion rate", "ED_CR_L1"),
            ("youth literacy", "ED_15-24_LR"),
            ("BCG coverage", "IM_BCG"),
            ("DTP3 coverage", "IM_DTP3"),
            ("antenatal care", "MNCH_ANC1"),
            ("ANC1", "MNCH_ANC1"),
            ("skilled birth attendant", "MNCH_SAB"),
            ("SAB", "MNCH_SAB"),
        ],
    )
    def test_known_synonyms(self, synonym: str, expected_code: str):
        r = resolve_indicator(synonym)
        assert r.status == "synonym_match", f"{synonym!r} did not match a synonym"
        assert r.code == expected_code

    def test_synonym_match_includes_canonical_name(self):
        r = resolve_indicator("U5MR")
        assert r.code == "CME_MRY0T4"
        assert r.name == "Under-five mortality rate"


class TestNameIndexHit:
    """Names not in the synonym table fall through to the canonical-name index."""

    def test_canonical_name_resolves(self):
        # CME_SB is a tier=1 indicator with name "Stillbirths" — not in
        # the synonym table, so it must come through the name index.
        r = resolve_indicator("Stillbirths")
        assert r.status == "name_index_hit"
        assert r.code == "CME_SB"

    def test_canonical_name_with_brackets_normalizes(self):
        r = resolve_indicator("Height-for-age <-2 SD (stunting)")
        # This canonical name string maps to NT_ANT_HAZ_NE2.
        assert r.status == "name_index_hit"
        assert r.code == "NT_ANT_HAZ_NE2"


class TestAmbiguous:
    """Genuinely ambiguous phrases refuse with a disambiguation list."""

    def test_child_mortality_returns_multiple_candidates(self):
        r = resolve_indicator("child mortality")
        assert r.status == "ambiguous"
        assert r.code is None
        candidate_codes = [c for c, _ in r.candidates]
        # Should include at least these four canonical mortality variants.
        assert "CME_MRM0" in candidate_codes
        assert "CME_MRY0" in candidate_codes
        assert "CME_MRY0T4" in candidate_codes
        assert "CME_MRY1T4" in candidate_codes

    def test_vaccination_returns_multiple_vaccines(self):
        r = resolve_indicator("vaccination")
        assert r.status == "ambiguous"
        candidate_codes = [c for c, _ in r.candidates]
        assert "IM_DTP3" in candidate_codes
        assert "IM_BCG" in candidate_codes

    def test_candidates_carry_human_readable_names(self):
        r = resolve_indicator("child mortality")
        for code, name in r.candidates:
            assert isinstance(code, str) and code
            assert isinstance(name, str) and name


class TestHyphenatedCodes:
    """Hyphenated codes (e.g. ED_15-24_LR, PT_F_15-49_FGM) must round-trip
    through both the synonym path AND the code-passthrough path.

    Added in v0.7.3 to lock in the codelist contract: if `unicefdata`'s YAML
    ever drops a hyphen from one of these codes, the synonym entry's
    `if code in code_to_name` guard would silently fall through to "unknown",
    and the user-facing failure would be a 404 at the SDMX layer with no hint
    that the resolver dropped the input. This test makes the drift visible.
    """

    def test_youth_literacy_synonym_resolves(self):
        r = resolve_indicator("youth literacy")
        assert r.status == "synonym_match"
        assert r.code == "ED_15-24_LR"
        assert r.name  # canonical name populated

    def test_youth_literacy_rate_synonym_resolves(self):
        r = resolve_indicator("youth literacy rate")
        assert r.status == "synonym_match"
        assert r.code == "ED_15-24_LR"

    def test_hyphenated_code_passthrough(self):
        r = resolve_indicator("ED_15-24_LR")
        assert r.status == "code_passthrough"
        assert r.code == "ED_15-24_LR"

    def test_lowercase_hyphenated_code_normalizes(self):
        r = resolve_indicator("ed_15-24_lr")
        assert r.status == "code_passthrough"
        assert r.code == "ED_15-24_LR"

    def test_fgm_hyphenated_code_passthrough(self):
        # PT_F_15-49_FGM is referenced by a synonym AND must passthrough as code.
        r = resolve_indicator("PT_F_15-49_FGM")
        assert r.status == "code_passthrough"
        assert r.code == "PT_F_15-49_FGM"


class TestUnknown:
    """Inputs that don't match anything return unknown."""

    def test_invented_code(self):
        r = resolve_indicator("CME_FAKE_CODE_XYZ")
        assert r.status == "unknown"
        assert r.code is None

    def test_random_string(self):
        r = resolve_indicator("this is not an indicator")
        assert r.status == "unknown"

    def test_empty_string(self):
        r = resolve_indicator("")
        assert r.status == "unknown"

    def test_non_string_returns_unknown(self):
        r = resolve_indicator(None)  # type: ignore[arg-type]
        assert r.status == "unknown"


class TestOriginalInputPreserved:
    """The original_input field round-trips for callers that want to echo it."""

    def test_passthrough_preserves_input(self):
        r = resolve_indicator("CME_MRM0")
        assert r.original_input == "CME_MRM0"

    def test_synonym_preserves_input_with_capitalization(self):
        r = resolve_indicator("Neonatal Mortality")
        assert r.original_input == "Neonatal Mortality"

    def test_ambiguous_preserves_input(self):
        r = resolve_indicator("child mortality")
        assert r.original_input == "child mortality"


class TestResolveIndicators:
    """Batch resolver returns one resolution per input + convenience codes list."""

    def test_all_resolved(self):
        resolutions, codes = resolve_indicators(["CME_MRM0", "stunting", "U5MR"])
        assert len(resolutions) == 3
        assert all(r.code is not None for r in resolutions)
        assert codes == ["CME_MRM0", "NT_ANT_HAZ_NE2", "CME_MRY0T4"]

    def test_mixed_outcomes_preserved(self):
        resolutions, codes = resolve_indicators(
            ["CME_MRM0", "child mortality", "made_up"]
        )
        assert len(resolutions) == 3
        assert resolutions[0].status == "code_passthrough"
        assert resolutions[1].status == "ambiguous"
        assert resolutions[2].status == "unknown"
        # Only the passthrough produced a usable code.
        assert codes == ["CME_MRM0"]

    def test_empty_list(self):
        resolutions, codes = resolve_indicators([])
        assert resolutions == []
        assert codes == []
