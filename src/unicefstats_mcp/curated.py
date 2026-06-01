"""Curated canonical-code catalog for unicefstats-mcp v1.1.0.

Each entry pins an ambiguous family (e.g. ED_ANAR with L1/L2/L3 variants)
to a single canonical code, with synonyms used by the resolver to detect
matches and a dimension_hint surfaced via assistant_guidance.

Sources: gap families ED_ANAR/NT_ANE/SPP_CHLD/PV_CHLD from v1.1.0_pattern_review.md;
high-frequency families from v9 A/B replay (Arm A wins).
"""

from typing import TypedDict


class CuratedEntry(TypedDict):
    family: str
    category: str
    code: str
    canonical_label: str
    alt_synonyms: list[str]
    dimension_hint: str | None
    validated_at: str


CURATED_PREFERRED: dict[str, CuratedEntry] = {
    # ──── GAP FAMILIES (ED_ANAR, NT_ANE, SPP_CHLD, PV_CHLD) ────
    "ED_ANAR_L1": {
        "family": "ED_ANAR",
        "category": "EDUCATION",
        "code": "ED_ANAR_L1",
        "canonical_label": "Net attendance rate, primary (Level 1)",
        "alt_synonyms": [
            "primary school attendance",
            "education attendance primary",
            "net attendance rate L1",
            "school enrollment primary level",
        ],
        "dimension_hint": (
            "If querying L2/L3 (lower/upper secondary), "
            "specify in get_data; default is L1."
        ),
        "validated_at": "2026-05-29",
    },
    "ED_ANAR_L2": {
        "family": "ED_ANAR",
        "category": "EDUCATION",
        "code": "ED_ANAR_L2",
        "canonical_label": "Net attendance rate, lower secondary (Level 2)",
        "alt_synonyms": [
            "secondary school attendance",
            "lower secondary attendance",
            "net attendance rate L2",
            "junior secondary education",
        ],
        "dimension_hint": "Specify level 2 disaggregation in get_data if not default.",
        "validated_at": "2026-05-29",
    },
    "ED_ANAR_L3": {
        "family": "ED_ANAR",
        "category": "EDUCATION",
        "code": "ED_ANAR_L3",
        "canonical_label": "Net attendance rate, upper secondary (Level 3)",
        "alt_synonyms": [
            "upper secondary attendance",
            "high school enrollment",
            "net attendance rate L3",
            "senior secondary education",
        ],
        "dimension_hint": "Specify level 3 disaggregation in get_data.",
        "validated_at": "2026-05-29",
    },
    "NT_ANE_WOM_15_49_MOD": {
        "family": "NT_ANE",
        "category": "NUTRITION",
        "code": "NT_ANE_WOM_15_49_MOD",
        "canonical_label": (
            "Prevalence of anemia among women of reproductive age "
            "(15-49 years, moderate or severe)"
        ),
        "alt_synonyms": [
            "anemia women",
            "women anemia prevalence",
            "anaemia reproductive age",
            "moderate severe anemia women",
        ],
        "dimension_hint": (
            "Severity variants (moderate, severe, any) available; "
            "default is moderate or severe combined."
        ),
        "validated_at": "2026-05-29",
    },
    "NT_ANE_WOM_15_49_ANY": {
        "family": "NT_ANE",
        "category": "NUTRITION",
        "code": "NT_ANE_WOM_15_49_ANY",
        "canonical_label": (
            "Prevalence of anemia among women of reproductive age "
            "(15-49 years, any severity)"
        ),
        "alt_synonyms": [
            "anemia women any severity",
            "total anemia prevalence women",
            "anaemia any level",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "NT_ANE_PG_ANY": {
        "family": "NT_ANE",
        "category": "NUTRITION",
        "code": "NT_ANE_PG_ANY",
        "canonical_label": "Prevalence of anemia among pregnant women",
        "alt_synonyms": [
            "pregnant women anemia",
            "pregnancy anaemia",
            "maternal anemia",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "SPP_CHLD_SOC_PROT": {
        "family": "SPP_CHLD",
        "category": "PROTECTION",
        "code": "SPP_CHLD_SOC_PROT",
        "canonical_label": "Children supported by social protection programmes and schemes (%)",
        "alt_synonyms": [
            "social protection children",
            "child social protection coverage",
            "children receiving social support",
            "social safety net children",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "SPP_CHLD_VOL_DIS": {
        "family": "SPP_CHLD",
        "category": "PROTECTION",
        "code": "SPP_CHLD_VOL_DIS",
        "canonical_label": "Children with disabilities receiving social protection",
        "alt_synonyms": [
            "disabled children social support",
            "children disabilities protection",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "PV_CHLD_INCM_PL": {
        "family": "PV_CHLD",
        "category": "POVERTY",
        "code": "PV_CHLD_INCM_PL",
        "canonical_label": "Children in income poverty (below poverty line, %)",
        "alt_synonyms": [
            "child income poverty",
            "children poverty rate",
            "monetary poverty children",
            "child poverty income",
        ],
        "dimension_hint": "Income-based measure; distinct from multidimensional poverty variants.",
        "validated_at": "2026-05-29",
    },
    "PV_CHLD_MPI_L1": {
        "family": "PV_CHLD",
        "category": "POVERTY",
        "code": "PV_CHLD_MPI_L1",
        "canonical_label": "Children in multidimensional poverty (severe deprivation, Level 1)",
        "alt_synonyms": [
            "multidimensional poverty children severe",
            "child poverty MPI",
            "severe deprivation children",
        ],
        "dimension_hint": "Deprivation level L1=severe; use L2 for moderate deprivation.",
        "validated_at": "2026-05-29",
    },
    "PV_CHLD_MPI_L2": {
        "family": "PV_CHLD",
        "category": "POVERTY",
        "code": "PV_CHLD_MPI_L2",
        "canonical_label": "Children in multidimensional poverty (moderate deprivation, Level 2)",
        "alt_synonyms": [
            "multidimensional poverty moderate",
            "moderate deprivation children",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    # ──── HIGH-FREQUENCY v9 CLUSTER ────
    "PT_F_20-24_MRD_U18": {
        "family": "PT_F",
        "category": "PROTECTION",
        "code": "PT_F_20-24_MRD_U18",
        "canonical_label": (
            "Percentage of women (aged 20-24 years) "
            "married or in union before age 18"
        ),
        "alt_synonyms": [
            "women married before 18",
            "child marriage women",
            "women aged 20-24 married before 18",
            "early marriage women",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "PT_F_15-19_MRD_U18": {
        "family": "PT_F",
        "category": "PROTECTION",
        "code": "PT_F_15-19_MRD_U18",
        "canonical_label": (
            "Percentage of women (aged 15-19 years) "
            "married or in union before age 18"
        ),
        "alt_synonyms": [
            "girls married before 18",
            "adolescent marriage",
            "women 15-19 married early",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "WS_PPL_W_SFD": {
        "family": "WS_PPL",
        "category": "WASH",
        "code": "WS_PPL_W_SFD",
        "canonical_label": "Population using safe drinking water (%)",
        "alt_synonyms": [
            "safe water access",
            "drinking water safety",
            "population water coverage",
            "safe water supply",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "WS_PPL_S_IMP": {
        "family": "WS_PPL",
        "category": "WASH",
        "code": "WS_PPL_S_IMP",
        "canonical_label": "Population using improved sanitation facilities (%)",
        "alt_synonyms": [
            "improved sanitation",
            "sanitation coverage",
            "access sanitation",
            "sanitation facilities population",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    # v1.1.1 NOTE: v1.1.0 carried both HVA_EPI_INF_RT_0_14 and
    # HVA_EPI_INF_RT_15_19 entries that pointed at codes which do NOT
    # exist as separate codes in the UNICEF SDMX catalog (verified via
    # _get_indicators()). The base HVA_EPI_INF_RT does exist and the
    # HIV_AIDS dataflow exposes the disaggregation as an AGE dimension
    # filter (Y0, Y0T4, Y0T14, Y0T19, Y10T14, Y10T19, Y15T19, Y15T24,
    # Y15T49, Y20T24, Y5T9, _T) — verified via the dataflow YAML at
    # site-packages/unicefdata/metadata/current/dataflows/HIV_AIDS.yaml.
    # So "HIV infection rate 15-19" maps to
    # get_data(indicator='HVA_EPI_INF_RT', age='Y15T19', ...) — NOT to
    # a separate _15-19 code. The single replacement entry below
    # consolidates synonyms onto the base code and uses dimension_hint
    # to explain the AGE filter recipe. Issue #80 tracks the v1.2.0
    # "dimension-aware search" feature that will surface the recommended
    # filter automatically from the dataflow YAML.
    "HVA_EPI_INF_RT": {
        "family": "HVA_EPI",
        "category": "HEALTH",
        "code": "HVA_EPI_INF_RT",
        "canonical_label": (
            "Estimated HIV incidence rate (new infections per 1,000 "
            "uninfected population)"
        ),
        "alt_synonyms": [
            "HIV infection rate",
            "HIV new infections",
            "HIV incidence rate",
            "new HIV infections per 1000",
            "HIV children",
            "child HIV infection",
            "pediatric HIV rate",
            "HIV prevalence children",
            "HIV adolescents 15-19",
            "HIV infection adolescents 15-19",
            "HIV 15-19",
            "HIV infection rate ages 15-19",
            "HIV teenagers 15-19",
        ],
        "dimension_hint": (
            "Available disaggregations on the HIV_AIDS dataflow: SEX "
            "(F/M/_T), AGE (Y0, Y0T4, Y0T14, Y0T19, Y10T14, Y10T19, "
            "Y15T19, Y15T24, Y15T49, Y20T24, Y5T9, _T), "
            "WEALTH_QUINTILE (Q1-Q5/_T), RESIDENCE (R/U/_T). For HIV "
            "by 15-19 age band, call get_data(indicator='HVA_EPI_INF_RT'"
            ", age='Y15T19', ...). v1.2.0 will surface this filter "
            "automatically via recommended_filter — see issue #80."
        ),
        "validated_at": "2026-05-30",
    },
    "ECD_CHLD_DEV_ON_TRK": {
        "family": "ECD_CHLD",
        "category": "EDUCATION",
        "code": "ECD_CHLD_DEV_ON_TRK",
        "canonical_label": "Children on developmental track (3-4 years, %)",
        "alt_synonyms": [
            "early childhood development",
            "children developmental milestones",
            "ECD on track",
            "preschool development",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "ECD_CHLD_PROG_ENROL": {
        "family": "ECD_CHLD",
        "category": "EDUCATION",
        "code": "ECD_CHLD_PROG_ENROL",
        "canonical_label": "Children enrolled in organized learning programmes (%)",
        "alt_synonyms": [
            "early learning programs",
            "preschool enrollment",
            "organized learning children",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "DM_POP_U5_CNT": {
        "family": "DM_POP",
        "category": "DEMOGRAPHICS",
        "code": "DM_POP_U5_CNT",
        "canonical_label": "Under-5 population (millions)",
        "alt_synonyms": [
            "under 5 population",
            "children under five",
            "U5 population count",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "DM_POP_CHILD_TOTAL": {
        "family": "DM_POP",
        "category": "DEMOGRAPHICS",
        "code": "DM_POP_CHILD_TOTAL",
        "canonical_label": "Children (0-17 years) — total population",
        "alt_synonyms": [
            "child population",
            "children 0-17",
            "total child population",
            "youth population 0-17",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "NT_ANT_WHZ_MOD_SV": {
        "family": "NT_ANT",
        "category": "NUTRITION",
        "code": "NT_ANT_WHZ_MOD_SV",
        "canonical_label": "Wasting in children under 5 (moderate and severe, %)",
        "alt_synonyms": [
            "wasting children",
            "acute malnutrition",
            "child wasting rate",
            "underweight acute",
        ],
        "dimension_hint": "Severity variants (moderate, severe, moderate+severe) available.",
        "validated_at": "2026-05-29",
    },
    "NT_ANT_STZ_MOD_SV": {
        "family": "NT_ANT",
        "category": "NUTRITION",
        "code": "NT_ANT_STZ_MOD_SV",
        "canonical_label": "Stunting in children under 5 (moderate and severe, %)",
        "alt_synonyms": [
            "stunting children",
            "chronic malnutrition",
            "child stunting rate",
            "stunted growth",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "NT_ANT_OWZ": {
        "family": "NT_ANT",
        "category": "NUTRITION",
        "code": "NT_ANT_OWZ",
        "canonical_label": "Overweight in children under 5 (%)",
        "alt_synonyms": ["overweight children", "child overweight rate"],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    # v1.2.0 fix: the entries below previously pointed at PHANTOM codes
    # (CME_U5MR, CME_IMR, CME_NMR don't exist in the unicefdata
    # registry). The real codes are CME_MRY0T4 / CME_MRY0 / CME_MRM0.
    # Pinning the wrong code meant v1.1.x callers asking for U5MR via
    # the curated path got back a code that 404s on get_data. The
    # alt_synonyms still drive lookup_preferred and now route to a
    # real code.
    "CME_MRY0T4": {
        "family": "CME",
        "category": "HEALTH",
        "code": "CME_MRY0T4",
        "canonical_label": "Under-five mortality rate",
        "alt_synonyms": [
            "under five mortality",
            "under-five mortality",
            "under 5 mortality",
            "under-5 mortality",
            "U5MR",
            "child mortality rate",
            "mortality children under 5",
            "under-five mortality rate",
            "under 5 mortality rate",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-30",
    },
    "CME_MRY0": {
        "family": "CME",
        "category": "HEALTH",
        "code": "CME_MRY0",
        "canonical_label": "Infant mortality rate",
        "alt_synonyms": [
            "infant mortality",
            "infant mortality rate",
            "IMR",
            "baby mortality rate",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-30",
    },
    "CME_MRM0": {
        "family": "CME",
        "category": "HEALTH",
        "code": "CME_MRM0",
        "canonical_label": "Neonatal mortality rate",
        "alt_synonyms": [
            "neonatal mortality",
            "neonatal mortality rate",
            "newborn mortality rate",
            "NMR",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-30",
    },
    "IM_BCG_1_CVG": {
        "family": "IM",
        "category": "HEALTH",
        "code": "IM_BCG_1_CVG",
        "canonical_label": "BCG vaccination coverage (%)",
        "alt_synonyms": [
            "BCG coverage",
            "tuberculosis vaccination",
            "BCG immunization",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "IM_DPT_1_CVG": {
        "family": "IM",
        "category": "HEALTH",
        "code": "IM_DPT_1_CVG",
        "canonical_label": "DPT1 vaccination coverage (%)",
        "alt_synonyms": ["DPT vaccination", "diphtheria coverage", "DPT1 immunization"],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "IM_POL_1_CVG": {
        "family": "IM",
        "category": "HEALTH",
        "code": "IM_POL_1_CVG",
        "canonical_label": "Polio (OPV1) vaccination coverage (%)",
        "alt_synonyms": ["polio vaccination", "OPV coverage", "oral polio vaccine"],
        "dimension_hint": None,
        "validated_at": "2026-05-29",
    },
    "IM_DTP3": {
        "family": "IM",
        "category": "HEALTH",
        "code": "IM_DTP3",
        "canonical_label": "Diphtheria-tetanus-pertussis (DTP3) third-dose coverage (%)",
        "alt_synonyms": [
            "DTP3 coverage",
            "DTP3 vaccine coverage",
            "third dose DTP",
            "DTP 3rd dose",
            "diphtheria tetanus pertussis third dose",
        ],
        "dimension_hint": (
            "TRGT = target; for the year-2030 national target version, "
            "use TRGT_2030_IM_DTP3 instead of IM_DTP3."
        ),
        "validated_at": "2026-05-30",
    },
    "IM_DTP1": {
        "family": "IM",
        "category": "HEALTH",
        "code": "IM_DTP1",
        "canonical_label": "Diphtheria-tetanus-pertussis (DTP1) first-dose coverage (%)",
        "alt_synonyms": [
            "DTP1 coverage",
            "DTP first dose",
            "first dose DTP",
        ],
        "dimension_hint": None,
        "validated_at": "2026-05-30",
    },
}


# v1.1.1 FIX 6: short-substring matches were structurally too
# permissive in v1.0.0 / v1.1.0. The old rule `q in syn.lower() or
# syn.lower() in q` fired CME_IMR on any query containing the
# 3-letter substring 'imr' (e.g. 'imrish' → contains 'imr'), and
# similarly for 'NMR'/'BCG'/'DPT'. The new gate requires the matched
# substring to be at least 5 characters AND the longer string to
# contain the shorter as a substring. So 'imrish' (6 chars)
# containing 'imr' (3 chars) no longer matches — the 3-char synonym
# fails the 5-char minimum.
_MIN_SUBSTRING_LEN: int = 5


def _substring_match(q: str, syn: str) -> bool:
    """Bidirectional substring match with a min-length gate.

    Returns True iff one of ``q`` or ``syn`` is a substring of the
    other AND the SHORTER of the two is at least ``_MIN_SUBSTRING_LEN``
    characters. The min-length floor applies to the short side because
    the short side is what does the matching (the long string
    'contains' it). This kills the 'imr' → 'imrish' class of false
    positives without breaking long-query matches like
    'DTP3 vaccination coverage' → 'DTP3 coverage'.
    """
    if not q or not syn:
        return False
    if len(q) <= len(syn):
        short, long_ = q, syn
    else:
        short, long_ = syn, q
    if len(short) < _MIN_SUBSTRING_LEN:
        return False
    return short in long_


def lookup_preferred(query: str) -> CuratedEntry | None:
    """Find a curated canonical pick for a natural-language query.

    Case-insensitive substring match against each entry's
    ``canonical_label`` and ``alt_synonyms``, gated on a 5-char
    minimum on the shorter side of the comparison (v1.1.1 FIX 6).
    Returns the first matching entry by ``CURATED_PREFERRED``
    insertion order (which front-loads gap families). Returns
    ``None`` when no entry matches.

    The matcher is intentionally permissive — a query like "school
    attendance" should hit ``ED_ANAR_L1``'s synonym list even though
    the resolver's ``_SYNONYMS`` dict has no entry for the bare
    phrase. That is the entire point of the catalog: catch what the
    resolver misses. The 5-char minimum prevents 3-letter
    abbreviation collisions (e.g. 'imr' colliding with 'imrish') but
    multi-word synonyms remain reachable from longer queries.
    """
    if not query or not isinstance(query, str):
        return None
    q = query.strip().lower()
    if not q:
        return None
    for entry in CURATED_PREFERRED.values():
        label_l = entry["canonical_label"].lower()
        if _substring_match(q, label_l):
            return entry
        for syn in entry["alt_synonyms"]:
            if _substring_match(q, syn.lower()):
                return entry
    return None
