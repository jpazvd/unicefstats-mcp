"""v1.5.3 — Curated defaults for the long-tail ambiguity_abstain clusters.

v1.5.2 curated the biggest single ambiguity_abstain cluster (ED_CR +
ED_ROFST × UIS_MOD families). v1.5.3 closes the long tail:

  PT_F_PS-SX_V_PTNR_12MNTH    (intimate-partner violence; SDG 5.2.1)
  PT_F_18-29_SX-V_AGE-18      (sexual violence by 18; SDG 16.2.3)
  MNCH_BIRTH18                (early childbearing; was in _SYNONYMS
                               but the heuristic still fired)
  PT_CHLD_5-17_LBR_ECON       (child labour; SDG 8.7.1)
  ED_ROFST_L02                (one year before primary entry age, UIS)
  HVA_PED_LOST                (children orphaned by AIDS, UNAIDS)

Empirical projection on the v1.5.1 1484-cell sample (search-layer-only):
  +40 cells net = +2.7pp full-sample EQA lift (on top of v1.5.2's +6.5pp).

The 4 losses on PT_F_18-29_SX-V_AGE-18 are PT_M_18-29 male siblings
with the SAME prompt template (sex absent from the question); defaulting
to female matches the SDG 16.2.3 custodian convention — same policy
cost as v1.5.2's ED_CR_L1.
"""

from __future__ import annotations

import pytest

from unicefstats_mcp.curated import CURATED_PREFERRED, lookup_preferred


@pytest.mark.parametrize(
    "query,expected_code",
    [
        # PT_F_PS-SX_V_PTNR_12MNTH (intimate partner violence)
        (
            "What was Proportion of ever-partnered women and girls aged 15-49 years "
            "subjected to physical and/or sexual violence by a current or former intimate "
            "partner for X in 2020?",
            "PT_F_PS-SX_V_PTNR_12MNTH",
        ),
        # PT_F_18-29_SX-V_AGE-18 (sexual violence by 18)
        (
            "What was Proportion of population aged 18-29 years who experienced sexual "
            "violence by age of 18 (% of women aged 18-29) for X in 2020?",
            "PT_F_18-29_SX-V_AGE-18",
        ),
        # MNCH_BIRTH18 (early childbearing)
        (
            "What was Early childbearing - percentage of women (aged 20-24 years) who "
            "gave birth before age 18 for X in 2020?",
            "MNCH_BIRTH18",
        ),
        # PT_CHLD_5-17_LBR_ECON (child labour)
        (
            "What was Percentage of children (aged 5-17 years) engaged in child labour "
            "(economic activities) for X in 2020?",
            "PT_CHLD_5-17_LBR_ECON",
        ),
        # ED_ROFST_L02 (out-of-school L02)
        (
            "What was Out-of-school rate for children one year before the official "
            "primary entry age (%) for X in 2020?",
            "ED_ROFST_L02",
        ),
        # HVA_PED_LOST (AIDS-orphaned children)
        (
            "What was Estimated number of children (aged 0-17 years) who have lost one "
            "or both parents due to AIDS for X in 2020?",
            "HVA_PED_LOST",
        ),
    ],
)
def test_v153_long_tail_prompts_route_correctly(query: str, expected_code: str) -> None:
    """v1.5.3 contract: each of the six new curated families routes the
    actual benchmark prompt to the right code."""
    result = lookup_preferred(query)
    assert result is not None, f"v1.5.3 regression: {query[:80]!r} returned None"
    assert result["code"] == expected_code, (
        f"v1.5.3 regression: {query[:80]!r} routed to {result['code']!r} "
        f"instead of {expected_code}"
    )


def test_ed_rofst_l02_synonyms_do_not_catch_anar_l02() -> None:
    """Critical narrowing test: the v1.5.3 ED_ROFST_L02 synonyms MUST
    include 'out-of-school' or 'rofst' so they don't substring-match
    ED_ANAR_L02 (adjusted net attendance, same tier) or ED_NERA_L02
    (adjusted net enrolment, same tier). Initial v1.5.3 draft had loose
    'one year before primary entry age' synonyms that caught 12
    ED_ANAR_L02 cells empirically."""
    anar_prompt = (
        "What was Adjusted net attendance rate, one year before the official "
        "primary entry age for X in 2020?"
    )
    result = lookup_preferred(anar_prompt)
    # Either no curated match (ED_ANAR_L02 is not in CURATED_PREFERRED yet) or
    # it routes to something OTHER than ED_ROFST_L02 (NOT the out-of-school
    # default that the narrowing fix protects against).
    assert result is None or result["code"] != "ED_ROFST_L02", (
        "v1.5.3 narrowing failed: ED_ANAR_L02 prompt routed to "
        "ED_ROFST_L02 — broad 'one year before primary' synonym slipped back in"
    )


@pytest.mark.parametrize(
    "code,must_mention",
    [
        ("PT_F_PS-SX_V_PTNR_12MNTH", ["15-49", "SDG 5.2.1"]),
        ("PT_F_18-29_SX-V_AGE-18", ["18-29", "SDG 16.2.3"]),
        ("MNCH_BIRTH18", ["20-24"]),
        ("PT_CHLD_5-17_LBR_ECON", ["SDG 8.7.1", "PT_CHLD_5-17_LBR_ECON-HC"]),
        ("ED_ROFST_L02", ["L02", "ED_ANAR_L02", "ED_NERA_L02"]),
        ("HVA_PED_LOST", ["UNAIDS"]),
    ],
)
def test_v153_dimension_hint_names_alternatives(
    code: str, must_mention: list[str]
) -> None:
    """Every v1.5.3 entry's dimension_hint must explicitly name the
    alternative versions in the data warehouse + the relevant SDG /
    custodian-agency convention."""
    entry = CURATED_PREFERRED.get(code)
    assert entry is not None, f"{code} missing from CURATED_PREFERRED"
    hint = entry["dimension_hint"]
    for token in must_mention:
        assert (
            token in hint
        ), f"{code}.dimension_hint should mention {token!r}; got {hint!r}"


def test_v152_and_v151_entries_still_resolve() -> None:
    """v1.5.3 must not break v1.5.0/v1.5.1/v1.5.2 curated entries."""
    for q, expected in [
        ("primary school attendance", "ED_ANAR_L1"),
        ("anemia women", "NT_ANE_WOM_15_49_MOD"),
        ("primary completion rate", "ED_CR_L1_UIS_MOD"),
        ("out-of-school rate lower secondary", "ED_ROFST_L2_UIS_MOD"),
        ("unimproved drinking water sources", "WS_PPL_W-UI"),
    ]:
        result = lookup_preferred(q)
        assert result is not None and result["code"] == expected, (
            f"v1.5.3 regression on {q!r}: expected {expected}, got "
            f"{result['code'] if result else None}"
        )
