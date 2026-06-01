"""Dimension awareness for unicefstats-mcp.

Reads the per-dataflow YAML and indicator-metadata YAML shipped by the
`unicefdata` package, then exposes helpers that:

- Return the primary dataflow for an indicator (coercing string-vs-list).
- List which SDMX dimensions an indicator's dataflow exposes (with values).
- Validate (dim, value) pairs against the codelist before SDMX calls.
- Build the `disaggregation_filters` envelope from real metadata, not from
  the hardcoded `{sex, wealth_quintile, residence}` triple v1.1.x shipped.
- Post-fetch filter a pandas DataFrame by dim values (the `raw=True` path
  in `get_data` for non-first-class dims).
- Invert the metadata to find indicators supporting a given dim/value
  (foundation for the v1.3.0 `dimension_mismatch` sibling search).

Cost model: every read is local YAML; cached on first call. The indicator
metadata file is pre-warmed at module import (~50 ms one-shot during MCP
startup, not on the first user request). Per-dataflow YAMLs load lazily on
first reference.

fragile-upstream: `unicefdata` 2.4.x exposes only SEX as a first-class
`unicefData()` kwarg. When 2.5.0 ships with first-class `age=`, move AGE
into `FIRST_CLASS_UD_DIMS` below and drop the `raw_filtered` route for
AGE-only queries. Other dims (WEALTH_QUINTILE, RESIDENCE, ...) stay
raw-filtered indefinitely — upstream has no plans to make them
first-class.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping
from functools import cache, lru_cache
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import pandas as pd


FIRST_CLASS_UD_DIMS: frozenset[str] = frozenset({"SEX"})

POST_FILTERABLE_DIMS: frozenset[str] = frozenset(
    {
        "AGE",
        "WEALTH_QUINTILE",
        "RESIDENCE",
        "MATERNAL_EDU_LVL",
        "EDUCATION_LEVEL",
        "DISABILITY_STATUS",
        "HEAD_OF_HOUSE",
        "SDG_INDICATOR",
        "SKILL_TYPE",
        "DATA_SOURCE",
    }
)

# Routing dimensions are part of the SDMX request envelope, not
# disaggregations the caller filters on.
_ROUTING_DIMS: frozenset[str] = frozenset({"REF_AREA", "INDICATOR", "TIME_PERIOD"})


def _ud_metadata_root() -> str:
    """Locate the metadata directory shipped with the installed unicefdata."""
    import unicefdata

    return os.path.join(
        os.path.dirname(unicefdata.__file__), "metadata", "current"
    )


def _startup_self_test(indicators: dict[str, dict[str, Any]]) -> None:
    """Fail fast on YAML schema drift.

    Asserts the shape we depend on. If upstream renames `dataflows`, drops
    `tier`, or otherwise reshapes the metadata, this raises at MCP startup
    instead of producing a NoneType crash deep inside `get_data` later.
    """
    if not indicators:
        return
    sample = indicators.get("HVA_EPI_INF_RT") or next(iter(indicators.values()))
    required = {"code", "name", "tier"}
    missing = required - sample.keys()
    if missing:
        raise RuntimeError(
            "unicefstats_mcp.dimensions: upstream unicefdata metadata schema "
            f"drift; missing required fields {sorted(missing)!r} on sample "
            f"indicator {sample.get('code')!r}. Check that unicefdata is "
            "installed and >= 2.4."
        )


@lru_cache(maxsize=1)
def load_indicator_metadata() -> dict[str, dict[str, Any]]:
    """Return the per-indicator metadata dict (738 indicators in 2.4.x).

    Prefers the ``INDICATORS_METADATA`` module-level dict that the
    ``unicefdata`` package already loads at its own import time — that
    constant is the authoritative process-wide cache and avoids a second
    parse of the 1+ MB YAML (~700 ms saved per MCP startup, in token
    terms: shorter cold-start latency for the first user turn).

    Falls back to a direct YAML read if the upstream constant is absent
    (defensive for future renames or trimmed releases). The fallback
    path also runs the schema self-test; the cache-reuse path trusts
    upstream-side validation.
    """
    # Path A — reuse upstream's already-loaded dict. The module-level
    # `INDICATORS_METADATA` constant is populated once by unicefdata at
    # its import time (see unicefdata.unicefdata:_load_indicators_metadata).
    import sys

    try:
        import unicefdata  # noqa: F401 — ensures the file-module is in sys.modules
    except ImportError:
        return {}
    udx_mod = sys.modules.get("unicefdata.unicefdata")
    upstream = getattr(udx_mod, "INDICATORS_METADATA", None) if udx_mod else None
    if isinstance(upstream, dict) and upstream:
        typed = cast("dict[str, dict[str, Any]]", upstream)
        _startup_self_test(typed)
        return typed

    # Path B — fallback YAML read (defensive against upstream rename).
    import yaml  # type: ignore[import-untyped]

    yaml_path = os.path.join(
        _ud_metadata_root(), "_unicefdata_indicators_metadata.yaml"
    )
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    indicators = doc.get("indicators") or {}
    if not isinstance(indicators, dict):
        return {}
    typed = cast("dict[str, dict[str, Any]]", indicators)
    _startup_self_test(typed)
    return typed


@cache
def load_dataflow_yaml(dataflow_id: str) -> dict[str, Any] | None:
    """Lazy-load a single dataflow YAML by ID.

    Returns the parsed YAML (with ``dimensions`` list, ``attributes`` list,
    etc.) or ``None`` if the file does not exist (rare — tier-2 indicators
    fall through this path).
    """
    import yaml

    yaml_path = os.path.join(
        _ud_metadata_root(), "dataflows", f"{dataflow_id}.yaml"
    )
    if not os.path.exists(yaml_path):
        return None
    with open(yaml_path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    if not isinstance(loaded, dict):
        return None
    return cast("dict[str, Any]", loaded)


def primary_dataflow(code: str) -> str | None:
    """Return the primary (first) dataflow ID for an indicator.

    Coerces the ``dataflows`` field that 122 tier-1 indicators store as a
    bare string (e.g. ``'HIV_AIDS'``) rather than a list. Without
    coercion, ``dataflows[0]`` returns the first character (``'H'``) and
    silently routes SDMX calls to a non-existent dataflow.

    Returns ``None`` for tier-2 indicators (no ``dataflows`` field).
    """
    meta = load_indicator_metadata().get(code)
    if not meta:
        return None
    df = meta.get("dataflows")
    if not df:
        return None
    if isinstance(df, str):
        return df
    if isinstance(df, list) and df:
        first = df[0]
        return first if isinstance(first, str) else None
    return None


def indicator_disaggregations(code: str) -> list[str]:
    """Return the indicator's own disaggregations list (from metadata YAML).

    Empty for tier-2 indicators or unknown codes.
    """
    meta = load_indicator_metadata().get(code) or {}
    val = meta.get("disaggregations") or []
    return [x for x in val if isinstance(x, str)]


def dataflow_dimension_values(
    dataflow_id: str, dim_id: str
) -> list[str] | None:
    """Return the codelist values for a ``(dataflow, dimension)`` pair.

    Returns ``None`` if the dataflow YAML cannot be loaded or the dim is
    not in the dataflow's ``dimensions`` list. When ``is_exhaustive`` is
    ``False`` upstream, the list is a partial snapshot — callers reading
    the raw dataflow YAML can consult ``total_values_count`` for the real
    count; this helper exposes only what the YAML actually carries.
    """
    flow = load_dataflow_yaml(dataflow_id)
    if not flow:
        return None
    dims = flow.get("dimensions") or []
    for dim in dims:
        if isinstance(dim, dict) and dim.get("id") == dim_id:
            vals = dim.get("values") or []
            return [v for v in vals if isinstance(v, str)]
    return None


def dimensions_for_indicator(code: str) -> dict[str, list[str]]:
    """Return ``{dim_id: [values]}`` for the indicator's primary dataflow.

    Excludes routing dims (REF_AREA, INDICATOR, TIME_PERIOD). Restricts to
    the dims the indicator's own metadata names in ``disaggregations`` when
    that list is non-empty (some indicators carry only a subset of the
    parent dataflow's dimensions).

    Returns ``{}`` for tier-2 indicators (no dataflow metadata) — callers
    should branch on ``dimensions_for_indicator(code) == {}`` as the
    structured tier-2 signal.
    """
    df_id = primary_dataflow(code)
    if not df_id:
        return {}
    flow = load_dataflow_yaml(df_id)
    if not flow:
        return {}
    out: dict[str, list[str]] = {}
    indicator_dims = set(indicator_disaggregations(code))
    for dim in flow.get("dimensions") or []:
        if not isinstance(dim, dict):
            continue
        dim_id = dim.get("id")
        if not isinstance(dim_id, str):
            continue
        if dim_id in _ROUTING_DIMS:
            continue
        if indicator_dims and dim_id not in indicator_dims:
            # Indicator's own metadata says this dim doesn't apply.
            continue
        vals = dim.get("values") or []
        out[dim_id] = [v for v in vals if isinstance(v, str)]
    return out


def dimension_supported(
    code: str, dim_id: str, value: str | None = None
) -> bool:
    """Check whether ``(code, dim_id)`` is supported, optionally checking value.

    Returns ``True`` if the indicator's primary dataflow exposes ``dim_id``
    and (if ``value`` given) the value is in the codelist for that dim.
    Returns ``False`` for tier-2 indicators (no dataflow metadata).

    Used by ``get_data`` pre-flight validation to refuse with a structured
    ``failed_validation`` envelope before any SDMX call.

    v1.2.0 Commit 11 (Copilot #3328906531) — value comparison is
    case-insensitive. The YAML codelist values are SDMX uppercase
    (``Q1`` / ``Y15T19`` / ``_T``), but ``filter_by_dimensions``
    uppercases both sides before comparing — without normalising here,
    the two layers disagree and ``filters={'WEALTH_QUINTILE': 'q1'}``
    is refused at pre-flight even though the post-filter would have
    accepted it.
    """
    dims = dimensions_for_indicator(code)
    if dim_id not in dims:
        return False
    if value is None:
        return True
    return value.upper() in {str(v).upper() for v in dims[dim_id]}


def is_first_class_dim(dim_id: str) -> bool:
    """Return True if ``dim_id`` is a first-class ``unicefData()`` kwarg.

    In ``unicefdata`` 2.4.x, only SEX qualifies. When 2.5.0 ships with
    first-class ``age=``, AGE moves into ``FIRST_CLASS_UD_DIMS``.
    """
    return dim_id in FIRST_CLASS_UD_DIMS


def build_disaggregation_filters(code: str) -> dict[str, Any]:
    """Build the ``disaggregation_filters`` envelope.

    Returns ``{dim_id: [codelist values]}`` keyed by SDMX dim id (uppercase,
    matching the YAML). Routing dims are excluded. Consumed by
    ``get_indicator_info`` and ``lookup_by_code`` envelope construction.

    For tier-2 indicators (no dataflow metadata):
    ``{"_source": "fallback_unknown", "dimensions": None}``.
    """
    dims = dimensions_for_indicator(code)
    if not dims:
        return {"_source": "fallback_unknown", "dimensions": None}
    return dims


def _find_column(df: pd.DataFrame, dim_id: str) -> str | None:
    """Find the actual column name in ``df`` matching ``dim_id`` (case-insensitive)."""
    if df is None:
        return None
    target = dim_id.upper()
    for c in df.columns:
        if isinstance(c, str) and c.upper() == target:
            return c
    return None


def filter_by_dimensions(
    df: pd.DataFrame,
    filters: Mapping[str, str | list[str] | None],
) -> pd.DataFrame:
    """Post-fetch DataFrame filter on ``(dim, value)`` pairs.

    Used by the ``raw=True`` + post-filter path in ``get_data``. Each
    ``filters`` entry maps an SDMX dim id (e.g. ``'WEALTH_QUINTILE'``) to a
    single value or list of values. Column lookup is case-insensitive
    (``unicefdata`` sometimes returns lowercase columns when downstream
    consumers normalise).

    v1.2.0 Commit 8 — ``'_T'`` is treated as a REAL filter value, not a
    no-op. The raw payload contains rows for EVERY value of each dim
    including ``'_T'`` (the SDMX totals code); filtering to ``'_T'`` is
    how you actually request totals on the raw path. Earlier drafts
    skipped ``'_T'`` on the misconception that raw already meant
    "totals only" — empirically the raw payload mixes ``F``/``M``/``_T``
    on SEX, all AGE bands, all WEALTH_QUINTILE codes, etc.

    Filters with value ``None`` are no-ops (use the dim's full set).
    Unknown dims are skipped silently — the caller is expected to
    validate first via ``dimension_supported``.
    """
    if df is None or len(df) == 0 or not filters:
        return df
    out = df
    for dim_id, val in filters.items():
        if val is None:
            continue
        col = _find_column(out, dim_id)
        if col is None:
            continue
        if isinstance(val, list):
            wanted = {str(v).upper() for v in val if v is not None}
        else:
            wanted = {str(val).upper()}
        if not wanted:
            continue
        mask = out[col].astype(str).str.upper().isin(wanted)
        out = out[mask]
    return out


@lru_cache(maxsize=1)
def indicators_supporting_index() -> dict[str, set[str]]:
    """Inverted index ``dim_id → {indicator codes}``.

    Foundation for the v1.3.0 ``dimension_mismatch`` sibling search.
    Cheap to build (~3.7 k operations) and cached for the process
    lifetime.

    v1.2.0 Commit 11 (Copilot #3328906525) — the index uses
    ``dimensions_for_indicator(code)`` rather than the indicator's raw
    ``disaggregations`` field. The latter was a hard filter that
    silently excluded tier-1 indicators whose own metadata didn't
    enumerate the dim explicitly even though the primary dataflow's
    codelist exposes it — the same restriction-vs-hard-filter
    inconsistency the higher-level ``dimensions_for_indicator``
    explicitly avoids. Build cost: roughly one per-dataflow YAML
    parse per unique dataflow (~50 YAMLs total, cached).
    """
    out: dict[str, set[str]] = {}
    for code, meta in load_indicator_metadata().items():
        if meta.get("tier") != 1:
            continue
        for dim_id in dimensions_for_indicator(code):
            out.setdefault(dim_id, set()).add(code)
    return out


def indicators_supporting(
    dim_id: str, value: str | None = None
) -> list[str]:
    """Return indicators whose primary dataflow exposes ``dim_id``.

    With ``value`` given, additionally restricts to indicators whose
    dataflow codelist includes that value (e.g. ``dim_id='AGE'``,
    ``value='Y15T19'`` → only indicators whose AGE codelist contains
    ``Y15T19``). Case-insensitive on the value comparison (matches
    ``dimension_supported``).
    """
    candidates = list(indicators_supporting_index().get(dim_id, ()))
    if value is None:
        return sorted(candidates)
    value_u = value.upper()
    out: list[str] = []
    for code in candidates:
        df_id = primary_dataflow(code) or ""
        vals = dataflow_dimension_values(df_id, dim_id)
        if vals and value_u in {str(v).upper() for v in vals}:
            out.append(code)
    return sorted(out)


# ---------------------------------------------------------------------------
# Issue #77 — unit information (UNIT_MEASURE + UNIT_MULTIPLIER) for the
# `units` envelope field on `get_data`. The simplified path used by
# v1.1.x and v1.2.0 first_class mode strips these out, so a value like
# `0.188` for DM_POP_U5 NIU 2001 surfaces with no context — Haiku
# interpreted it as 188 (thousands path) on v1.0.0 and 188,000 (millions
# path) on v1.1.0. Source: PR #82 issue triage, 2026-05-30.
# ---------------------------------------------------------------------------

# SDMX unit multiplier is a power of 10. The codelist doesn't have
# human names so we hardcode the conventional plain-English labels for
# the range UNICEF DW actually uses (-3 through 9). Outside that, fall
# back to "10^N".
_UNIT_MULTIPLIER_NAMES: dict[int, str] = {
    -3: "thousandths",
    -2: "hundredths",
    -1: "tenths",
    0: "absolute (no multiplier)",
    1: "tens",
    2: "hundreds",
    3: "thousands",
    4: "ten thousands",
    5: "hundred thousands",
    6: "millions",
    7: "ten millions",
    8: "hundred millions",
    9: "billions",
}


def _unit_multiplier_name(multiplier: int | None) -> str | None:
    if multiplier is None:
        return None
    return _UNIT_MULTIPLIER_NAMES.get(multiplier, f"10^{multiplier}")


@lru_cache(maxsize=1)
def _load_unit_measure_codelist() -> dict[str, str]:
    """Load CL_UNIT_MEASURE from the shipped codelists YAML.

    Maps SDMX measure code (`'PS'`) → human name (`'Persons'`). Cached.
    """
    import yaml

    yaml_path = os.path.join(
        _ud_metadata_root(), "_unicefdata_codelists.yaml"
    )
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    codelists = doc.get("codelists") or {}
    cl = codelists.get("CL_UNIT_MEASURE") or {}
    codes = cl.get("codes") or {}
    return {k: v for k, v in codes.items() if isinstance(k, str) and isinstance(v, str)}


def unit_measure_name(measure_code: str) -> str | None:
    """Resolve `UNIT_MEASURE` SDMX code to its human name via the codelist."""
    if not isinstance(measure_code, str):
        return None
    return _load_unit_measure_codelist().get(measure_code)


@cache
def _fetch_unit_info_via_sdmx(
    indicator: str, dataflow: str | None
) -> tuple[str | None, int | None]:
    """Fetch (UNIT_MEASURE, UNIT_MULTIPLIER) for an indicator via a tiny
    raw=True call. Cached per (indicator, dataflow) — one SDMX round-trip
    per unique indicator per process lifetime.

    Used by the first_class path of `get_data` where the simplified
    response strips unit columns. Returns ``(None, None)`` on any
    failure (the envelope omits `units` in that case rather than guess).
    """
    try:
        import unicefdata as ud  # local import to keep module load cheap
    except ImportError:
        return None, None
    ud_kwargs: dict[str, Any] = {
        "indicator": indicator,
        "tidy": True,
        "raw": True,
    }
    if dataflow:
        ud_kwargs["dataflow"] = dataflow
    try:
        df = ud.unicefData(**ud_kwargs)
    except Exception:
        return None, None
    if df is None or len(df) == 0:
        return None, None
    measure = None
    multiplier = None
    if "UNIT_MEASURE" in df.columns:
        vals = df["UNIT_MEASURE"].dropna().unique()
        if len(vals) > 0 and isinstance(vals[0], str):
            measure = vals[0]
    if "UNIT_MULTIPLIER" in df.columns:
        vals = df["UNIT_MULTIPLIER"].dropna().unique()
        if len(vals) > 0:
            try:
                multiplier = int(vals[0])
            except (TypeError, ValueError):
                multiplier = None
    return measure, multiplier


def units_from_dataframe(df: pd.DataFrame) -> dict[str, Any] | None:
    """Extract unit info from a DataFrame that already carries the
    unit columns (the raw=True / raw_filtered path after
    ``normalize_columns`` renames them to lowercase).

    Returns ``None`` if the columns are absent or empty. Otherwise
    returns the envelope `units` dict:

        {"measure": "PS", "measure_name": "Persons",
         "multiplier": 3, "multiplier_name": "thousands",
         "interpretation": "values × 10^3 Persons"}

    When unit_measure or unit_multiplier varies across rows (rare;
    usually constant per indicator), the FIRST distinct value wins
    and a `varies: true` flag is added.
    """
    if df is None or len(df) == 0:
        return None
    measure_col = "unit_measure" if "unit_measure" in df.columns else (
        "UNIT_MEASURE" if "UNIT_MEASURE" in df.columns else None
    )
    multiplier_col = "unit_multiplier" if "unit_multiplier" in df.columns else (
        "UNIT_MULTIPLIER" if "UNIT_MULTIPLIER" in df.columns else None
    )
    if measure_col is None and multiplier_col is None:
        return None
    out: dict[str, Any] = {}
    if measure_col is not None:
        vals = df[measure_col].dropna().unique()
        if len(vals) > 0 and isinstance(vals[0], str):
            out["measure"] = vals[0]
            name = unit_measure_name(vals[0])
            if name:
                out["measure_name"] = name
            if len(vals) > 1:
                out["varies"] = True
    if multiplier_col is not None:
        vals = df[multiplier_col].dropna().unique()
        if len(vals) > 0:
            try:
                m = int(vals[0])
                out["multiplier"] = m
                mn = _unit_multiplier_name(m)
                if mn:
                    out["multiplier_name"] = mn
            except (TypeError, ValueError):
                pass
            if len(vals) > 1:
                out["varies"] = True
    if out.get("measure") and "multiplier" in out:
        measure_label = out.get("measure_name") or out["measure"]
        out["interpretation"] = (
            f"values × 10^{out['multiplier']} {measure_label}"
        )
    return out or None


def unit_info_for(
    indicator: str, dataflow: str | None = None
) -> dict[str, Any] | None:
    """Resolve unit info for an indicator. Cheap: one cached SDMX
    round-trip per (indicator, dataflow) per process.

    Used by the first_class path of ``get_data`` where the simplified
    response strips unit columns. The raw_filtered / totals_fallback
    paths should use ``units_from_dataframe(df)`` directly off the
    already-fetched DataFrame instead.
    """
    df_id = dataflow if dataflow is not None else primary_dataflow(indicator)
    measure, multiplier = _fetch_unit_info_via_sdmx(indicator, df_id)
    if measure is None and multiplier is None:
        return None
    out: dict[str, Any] = {}
    if measure is not None:
        out["measure"] = measure
        name = unit_measure_name(measure)
        if name:
            out["measure_name"] = name
    if multiplier is not None:
        out["multiplier"] = multiplier
        mn = _unit_multiplier_name(multiplier)
        if mn:
            out["multiplier_name"] = mn
    if "measure" in out and "multiplier" in out:
        measure_label = out.get("measure_name") or out["measure"]
        out["interpretation"] = (
            f"values × 10^{out['multiplier']} {measure_label}"
        )
    return out or None


# Pre-warm the metadata cache at module import (~50 ms one-shot).
# All helpers above must already be defined before this fires. The
# suppress is best-effort: the module still loads if metadata isn't
# reachable; helpers return conservative empty results until
# unicefdata is installed and the YAMLs are available.
with contextlib.suppress(Exception):
    load_indicator_metadata()
