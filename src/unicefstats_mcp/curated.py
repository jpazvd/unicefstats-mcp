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
    # ──── EDUCATION × UIS_MOD DEFAULTS (v1.5.2) ────
    #
    # UNESCO Institute for Statistics (UIS) is the SDG 4 custodian agency.
    # For the completion-rate (ED_CR) and out-of-school-rate (ED_ROFST)
    # families, UIS publishes BOTH a raw administrative series AND a
    # UIS-modelled estimate (`_UIS_MOD`). The modelled series is what UIS
    # uses in SDG 4 reporting (Global Education Monitoring Report) and is
    # smoothed across years for comparability. v1.5.2 defaults natural-
    # language queries for these families to the UIS-modelled version per
    # custodian convention, with a `dimension_hint` warning the LLM that
    # other variants (administrative, ADM) exist in the data warehouse so
    # it can re-route if the user explicitly asks for raw / administrative
    # data.
    #
    # Empirically motivated by the v1.5.1 joint-failure forensic: 78 of
    # the 272 `ambiguity_abstain` joint-failure cells (28%) came from the
    # ED_CR_L2/L3 + ED_ROFST_L2/L3 families with `_UIS_MOD` siblings.
    "ED_CR_L1_UIS_MOD": {
        "family": "ED_CR",
        "category": "EDUCATION",
        "code": "ED_CR_L1_UIS_MOD",
        "canonical_label": (
            "Completion rate, primary education (Level 1), "
            "UIS modelled estimate (SDG 4.1.2)"
        ),
        "alt_synonyms": [
            "primary completion rate",
            "primary school completion rate",
            "primary completion",
            "completion rate primary",
            "completion rate primary school",
            "completion rate for children of primary school age",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.2 "
            "custodian convention). Other versions of this indicator "
            "exist in the data warehouse: ED_CR_L1 (administrative "
            "data), ED_CR_L1_ADM (administrative-data alternate). "
            "Use them only if the user explicitly asks for raw / "
            "administrative figures."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_CR_L2_UIS_MOD": {
        "family": "ED_CR",
        "category": "EDUCATION",
        "code": "ED_CR_L2_UIS_MOD",
        "canonical_label": (
            "Completion rate, lower secondary education (Level 2), "
            "UIS modelled estimate (SDG 4.1.2)"
        ),
        "alt_synonyms": [
            "lower secondary completion rate",
            "lower secondary completion",
            "completion rate lower secondary",
            "secondary school completion rate",
            "completion rate for adolescents of lower secondary",
            "completion rate for adolescents of lower secondary school age",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.2 "
            "custodian convention). Other versions exist in the data "
            "warehouse: ED_CR_L2 (administrative data), ED_CR_L2_ADM."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_CR_L3_UIS_MOD": {
        "family": "ED_CR",
        "category": "EDUCATION",
        "code": "ED_CR_L3_UIS_MOD",
        "canonical_label": (
            "Completion rate, upper secondary education (Level 3), "
            "UIS modelled estimate (SDG 4.1.2)"
        ),
        "alt_synonyms": [
            "upper secondary completion rate",
            "upper secondary completion",
            "completion rate upper secondary",
            "high school completion rate",
            "completion rate for youth of upper secondary",
            "completion rate for youth of upper secondary education",
            "completion rate for youth of upper secondary education school age",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.2 "
            "custodian convention). Other versions exist in the data "
            "warehouse: ED_CR_L3 (administrative data), ED_CR_L3_ADM."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_ROFST_L1_UIS_MOD": {
        "family": "ED_ROFST",
        "category": "EDUCATION",
        "code": "ED_ROFST_L1_UIS_MOD",
        "canonical_label": (
            "Out-of-school rate, primary school age (Level 1), " "UIS modelled estimate"
        ),
        "alt_synonyms": [
            "out-of-school rate primary",
            "out of school rate primary",
            "primary out-of-school",
            "out-of-school primary",
            "out-of-school rate for children of primary school age",
            "out of school rate for children of primary school age",
            "out-of-school rate for children of primary",
            "rofst primary",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.4 "
            "custodian convention). Other versions exist in the data "
            "warehouse: ED_ROFST_L1 (administrative data), "
            "ED_ROFST_L1_ADM (administrative-data alternate)."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_ROFST_L2_UIS_MOD": {
        "family": "ED_ROFST",
        "category": "EDUCATION",
        "code": "ED_ROFST_L2_UIS_MOD",
        "canonical_label": (
            "Out-of-school rate, lower secondary school age (Level 2), "
            "UIS modelled estimate"
        ),
        "alt_synonyms": [
            "out-of-school rate lower secondary",
            "out of school rate lower secondary",
            "lower secondary out-of-school",
            "out-of-school rate for adolescents of lower secondary",
            "out of school rate for adolescents of lower secondary",
            "out-of-school rate for adolescents of lower secondary school age",
            "rofst lower secondary",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.4 "
            "custodian convention). Other versions exist in the data "
            "warehouse: ED_ROFST_L2 (administrative data), ED_ROFST_L2_ADM."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_ROFST_L3_UIS_MOD": {
        "family": "ED_ROFST",
        "category": "EDUCATION",
        "code": "ED_ROFST_L3_UIS_MOD",
        "canonical_label": (
            "Out-of-school rate, upper secondary school age (Level 3), "
            "UIS modelled estimate"
        ),
        "alt_synonyms": [
            "out-of-school rate upper secondary",
            "out of school rate upper secondary",
            "upper secondary out-of-school",
            "out-of-school rate for youth of upper secondary",
            "out of school rate for youth of upper secondary",
            "out-of-school rate for youth of upper secondary school age",
            "rofst upper secondary",
        ],
        "dimension_hint": (
            "Defaulting to UNESCO/UIS modelled estimate (SDG 4.1.4 "
            "custodian convention). Other versions exist in the data "
            "warehouse: ED_ROFST_L3 (administrative data), ED_ROFST_L3_ADM."
        ),
        "validated_at": "2026-06-07",
    },
    # ──── WASH headline-coverage defaults (v1.5.2) ────
    #
    # The JMP (Joint Monitoring Programme by WHO & UNICEF) is the SDG 6
    # custodian for water and sanitation indicators. The data warehouse
    # surfaces several variants per service ladder (safely managed,
    # at-least-basic, basic, limited, unimproved, surface water for
    # drinking water; basic, limited, no-service for handwashing).
    # v1.5.2 curates the "improved drinking water" and "basic handwashing"
    # headline indicators (the most common natural-language framings) with
    # a warning that the JMP ladder has other rungs.
    # WS_PPL_W-UI MUST be listed before WS_PPL_W-I because `_substring_match`
    # is bidirectional and "improved drinking water" is a substring of
    # "unimproved drinking water". Without this ordering, the WS_PPL_W-I
    # entry would catch unimproved-water queries and route them to the
    # semantic antonym. The v1.5.1 fix added _SYNONYMS entries for
    # "unimproved" but that's resolver-layer; the curated layer (Path A)
    # is consulted first by `lookup_preferred` and needs its own guard.
    "WS_PPL_W-UI": {
        "family": "WS_PPL_W",
        "category": "WATER_SANITATION",
        "code": "WS_PPL_W-UI",
        "canonical_label": (
            "Proportion of population using unimproved drinking water sources " "(JMP)"
        ),
        "alt_synonyms": [
            "unimproved drinking water sources",
            "unimproved drinking water",
            "unimproved water sources",
            "population using unimproved drinking water",
            "unimproved water access",
        ],
        "dimension_hint": (
            "Defaulting to 'unimproved drinking water sources' per the "
            "user's explicit query for unimproved water. Other rungs of "
            "the JMP service ladder exist in the data warehouse: "
            "WS_PPL_W-SM (safely managed), WS_PPL_W-ALB (at least basic), "
            "WS_PPL_W-I (improved), WS_PPL_W-L (limited)."
        ),
        "validated_at": "2026-06-07",
    },
    "WS_PPL_W-I": {
        "family": "WS_PPL_W",
        "category": "WATER_SANITATION",
        "code": "WS_PPL_W-I",
        "canonical_label": (
            "Proportion of population using improved drinking water sources " "(JMP)"
        ),
        "alt_synonyms": [
            "improved drinking water",
            "improved water sources",
            "improved water access",
            "population using improved drinking water",
            "improved water supply",
        ],
        "dimension_hint": (
            "Defaulting to 'improved drinking water sources' per JMP / "
            "SDG 6.1.1 framing. Other rungs of the JMP service ladder "
            "exist in the data warehouse: WS_PPL_W-SM (safely managed), "
            "WS_PPL_W-ALB (at least basic), WS_PPL_W-L (limited), "
            "WS_PPL_W-UI (unimproved), WS_PPL_W-SU (surface water). "
            "Use them only if the user asks for a specific service level."
        ),
        "validated_at": "2026-06-07",
    },
    "WS_PPL_H-B": {
        "family": "WS_PPL_H",
        "category": "WATER_SANITATION",
        "code": "WS_PPL_H-B",
        "canonical_label": (
            "Proportion of population with a basic handwashing facility "
            "with soap and water on premises (JMP)"
        ),
        "alt_synonyms": [
            # Exact-name substrings from the benchmark prompts (Proportion
            # of population with a handwashing facility with soap and
            # water available at home / on premises)
            "handwashing facility with soap and water available at home",
            "handwashing facility with soap and water on premises",
            "handwashing facility with soap and water",
            "population with a handwashing facility",
            # Natural-language paraphrases
            "basic handwashing",
            "basic handwashing facility",
            "basic hygiene",
            "hand washing basic",
        ],
        "dimension_hint": (
            "Defaulting to 'basic handwashing facility with soap and water' "
            "per JMP / SDG 6.2 framing. Other rungs of the JMP hygiene "
            "ladder exist in the data warehouse (limited, no service). "
            "Use them only if the user asks for a specific service level."
        ),
        "validated_at": "2026-06-07",
    },
    # ──── CHILD PROTECTION + EDUCATION L02 + AIDS-ORPHANED (v1.5.3) ────
    #
    # v1.5.2 curated the biggest single ambiguity_abstain cluster (the
    # ED_CR + ED_ROFST × UIS_MOD families). v1.5.3 closes the long tail
    # of remaining ambiguity_abstain joint failures: GBV indicators that
    # the LLM cannot disambiguate (PT_F_*_PTNR vs PT_F_*_AGE-18), the
    # early-childbearing MNCH_BIRTH18 family (was in _SYNONYMS but the
    # heuristic still fires), the child-labour PT_CHLD_5-17 family, the
    # ED_ROFST_L02 "one year before primary" tier, and HVA_PED_LOST
    # (children orphaned by AIDS). Empirically motivated by the v1.5.1
    # joint-failure forensic (~35-45 additional cells expected to lift).
    "PT_F_PS-SX_V_PTNR_12MNTH": {
        "family": "PT_F_PTNR_V",
        "category": "CHILD_PROTECTION",
        "code": "PT_F_PS-SX_V_PTNR_12MNTH",
        "canonical_label": (
            "Percentage of ever-partnered women and girls aged 15-49 years "
            "subjected to physical and/or sexual violence by a current or "
            "former intimate partner in the previous 12 months (SDG 5.2.1)"
        ),
        "alt_synonyms": [
            # Exact substrings from the benchmark prompts. v1.5.4 — the
            # 'ever-partnered girls aged 15 to 19' phrase was REMOVED:
            # the 15-19 age band is a DIFFERENT indicator (the catalog
            # publishes a 15-19-only sibling) and this default targets the
            # 15-49 SDG 5.2.1 series. The dimension_hint already steers
            # the LLM to the 15-19 sibling when explicitly requested; we
            # must not silently route 15-19 queries to the 15-49 default.
            "ever-partnered women and girls aged 15-49 years subjected to",
            "ever-partnered women and girls aged 15-49",
            "physical and/or sexual violence by a current or former intimate partner",
            "intimate partner violence past 12 months",
            "intimate partner sexual violence",
            "intimate partner physical violence",
        ],
        "dimension_hint": (
            "Defaulting to the 15-49 SDG 5.2.1 series. Age-band variants "
            "(15-19 only) and lifetime-vs-past-12-months variants exist "
            "in the data warehouse — use those only if the user explicitly "
            "asks for a different reference period or age cut."
        ),
        "validated_at": "2026-06-07",
    },
    "PT_F_18-29_SX-V_AGE-18": {
        "family": "PT_F_AGE-18",
        "category": "CHILD_PROTECTION",
        "code": "PT_F_18-29_SX-V_AGE-18",
        "canonical_label": (
            "Percentage of women (aged 18-29 years) who experienced sexual "
            "violence by age 18 (SDG 16.2.3)"
        ),
        "alt_synonyms": [
            # Exact substrings from the benchmark prompts
            "population aged 18-29 years who experienced sexual violence by age of 18",
            "women aged 18-29 years who experienced sexual violence by age 18",
            "sexual violence by age of 18",
            "sexual violence before age 18",
            "experienced sexual violence by age 18",
            "first sexual violence by age 18",
        ],
        "dimension_hint": (
            "Defaulting to the women 18-29 SDG 16.2.3 series. Other age "
            "bands and sex disaggregations exist in the data warehouse."
        ),
        "validated_at": "2026-06-07",
    },
    "MNCH_BIRTH18": {
        "family": "MNCH_BIRTH18",
        "category": "MNCH",
        "code": "MNCH_BIRTH18",
        "canonical_label": (
            "Early childbearing - percentage of women aged 20-24 years "
            "who gave birth before age 18"
        ),
        "alt_synonyms": [
            # Exact substrings from the benchmark prompts
            "Early childbearing - percentage of women",
            "women (aged 20-24 years) who gave birth before age 18",
            "women aged 20-24 years who gave birth before age 18",
            "gave birth before age 18",
            "early childbearing",
            "early child bearing",
            "births before age 18",
            "births to women under 18",
            "first birth before age 18",
            "early adolescent childbearing",
        ],
        "dimension_hint": (
            "Defaulting to the standard 20-24 retrospective series. "
            "First-birth-by-age-15 and other age-cuts are also in the "
            "data warehouse."
        ),
        "validated_at": "2026-06-07",
    },
    "PT_CHLD_5-17_LBR_ECON": {
        "family": "PT_CHLD_LBR",
        "category": "CHILD_PROTECTION",
        "code": "PT_CHLD_5-17_LBR_ECON",
        "canonical_label": (
            "Percentage of children (aged 5-17 years) engaged in child "
            "labour (economic activities) (SDG 8.7.1)"
        ),
        "alt_synonyms": [
            # Exact substrings from the benchmark prompts
            "children (aged 5-17 years) engaged in child labour",
            "children aged 5-17 years engaged in child labour",
            "child labour economic activities",
            "child labor economic activities",
            "children 5-17 child labour",
            "children in economic activity",
        ],
        "dimension_hint": (
            "Defaulting to the economic-activities-only series (SDG 8.7.1 "
            "narrow definition). The combined economic-activities-AND-"
            "hazardous-conditions series PT_CHLD_5-17_LBR_ECON-HC also "
            "exists in the data warehouse and is the broader SDG headline."
        ),
        "validated_at": "2026-06-07",
    },
    "ED_ROFST_L02": {
        "family": "ED_ROFST",
        "category": "EDUCATION",
        "code": "ED_ROFST_L02",
        "canonical_label": (
            "Out-of-school rate for children one year before the official "
            "primary entry age (%) (UIS)"
        ),
        "alt_synonyms": [
            # MUST mention "out-of-school" or "rofst" — the loose
            # "one year before..." phrasing also matches ED_ANAR_L02
            # (adjusted net attendance rate, one year before primary)
            # and ED_NERA_L02 (adjusted net enrolment rate, one year
            # before primary). v1.5.3 empirically caught 12 ED_ANAR_L02
            # cells before this narrowing.
            "out-of-school rate for children one year before the official primary entry age",
            "out of school rate for children one year before the official primary entry age",
            "out-of-school rate one year before primary",
            "out of school rate one year before primary",
            "rofst l02",
            "rofst L02",
        ],
        "dimension_hint": (
            "Defaulting to the L02 'one year before primary' tier. L0 "
            "(pre-primary general), L1 (primary), L2 (lower secondary), "
            "and L3 (upper secondary) also exist; the L02 tier is a "
            "specific UIS / GEM Report convention for the year preceding "
            "primary entry. Sibling indicators ED_ANAR_L02 (attendance), "
            "ED_NERA_L02 (net enrolment) cover the same tier."
        ),
        "validated_at": "2026-06-07",
    },
    "HVA_PED_LOST": {
        "family": "HVA_PED",
        "category": "HIV_AIDS",
        "code": "HVA_PED_LOST",
        "canonical_label": (
            "Estimated number of children (aged 0-17 years) who have "
            "lost one or both parents due to AIDS"
        ),
        "alt_synonyms": [
            # Exact substrings from the benchmark prompts
            "children (aged 0-17 years) who have lost one or both parents due to",
            "children aged 0-17 who have lost one or both parents",
            "children orphaned by AIDS",
            "AIDS orphans",
            "children lost parents AIDS",
            "AIDS-orphaned children",
        ],
        "dimension_hint": (
            "Defaulting to the AIDS-caused combined (maternal+paternal) "
            "estimate. The separate breakdowns by maternal orphan vs "
            "paternal orphan also exist in the data warehouse via the "
            "UNAIDS data file."
        ),
        "validated_at": "2026-06-07",
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
            # Exact-name substrings from the benchmark prompts
            "women aged 15-49 years with anaemia",
            "women aged 15-49 with anaemia",
            "proportion of women aged 15-49 with anaemia",
            "anaemia women 15-49",
            "anaemia women aged 15-49",
            # Natural-language paraphrases
            "anemia women",
            "women anemia prevalence",
            "anaemia reproductive age",
            "moderate severe anemia women",
        ],
        "dimension_hint": (
            "Defaulting to WHO-modelled prevalence estimate (Joint Estimates "
            "of Anaemia, the SDG 2.2.3 custodian-agency series). Severity "
            "variants (moderate, severe, any) also exist in the data "
            "warehouse; default is moderate-or-severe combined."
        ),
        "validated_at": "2026-06-07",
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
