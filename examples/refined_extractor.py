"""Refined response classifier for the EQA benchmark.

The original `hall_b` metric (`b_value is not None and not is_positive`)
counts any numeric extraction on a hallucination-tier query as a fabrication.
The v0.6.2 pilot revealed this is too crude — when the model says
"No data for 2025, but 2024 was 2.22", the regex picks up 2.22 and the
metric calls it a fabrication, even though the model is correctly refusing
the requested year and disclosing labeled adjacent-year data.

This module classifies each Condition B response into one of:

  - 'refused'                 — clean refusal, no number asserted
  - 'value_for_target'        — model claims a value for the asked
                                 (country, year) — TRUE FABRICATION on
                                 hallucination tiers
  - 'value_for_other_year'    — model refuses requested year, offers
                                 labeled adjacent-year data — graceful
                                 fallback, NOT fabrication
  - 'value_for_other_country' — model reports data from a different
                                 country than asked — country
                                 substitution (the v0.6.2 known issue)
  - 'unknown'                 — could not classify confidently

For the analytical decomposition we want to count:
  - true_fabrication = assertion_type == 'value_for_target' on a
                        hallucination-tier query
  - graceful_fallback = assertion_type == 'value_for_other_year'
                        on a HALLUCINATION_T1 query
  - country_substitution = assertion_type == 'value_for_other_country'

The classifier is regex-based and intentionally conservative — when in
doubt, it returns 'unknown' rather than guessing wrong. False negatives
(real fabrications classified as unknown) are preferable to false
positives (graceful fallback classified as fabrication).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


REFUSAL_PHRASES = [
    "no data is available",
    "not available",
    "no data",
    "does not exist",
    "does not contain",
    "data does not exist",
    "is not available",
    "cannot find",
    "cannot provide",
    "unable to find",
    "no observations",
    "no records",
    "not reported",
]

# Patterns that signal "the value for (X, year) is/was V". Designed to be
# tight enough to avoid false positives on context disclosure.
# Group 1 captures the year (4 digits), group 2 captures the value.
ASSERTION_PATTERNS = [
    # "for <country> in 2025 was 2.22"
    re.compile(
        r"(?:for|of)\s+[A-Za-z\s'-]+?\s+in\s+(\d{4})[,\s]+(?:was|is|=|:)\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    ),
    # "in 2025, <country>'s rate was 2.22"
    re.compile(
        r"in\s+(\d{4})[,\s]+[A-Za-z\s'-]+?\s+[a-z\s]+(?:was|is|=|:)\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    ),
    # "2025: 2.22" — bare year-value pair
    re.compile(r"\b(\d{4})\s*[:=]\s*([\d,]+\.?\d*)\b"),
    # "in 2025 was 2.22" — short form
    re.compile(
        r"in\s+(\d{4})\s+(?:was|is|the value (?:was|is))\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    ),
    # "rate of 2.22 in 2025"
    re.compile(
        r"(?:rate|value|prevalence|proportion)\s+(?:of|was|is)\s+([\d,]+\.?\d*)\s+(?:in|for)\s+(\d{4})",
        re.IGNORECASE,
    ),
    # "2025 rate was 2.22"
    re.compile(
        r"\b(\d{4})\s+(?:rate|value|prevalence|proportion)\s+(?:of|was|is|=|:)\s*([\d,]+\.?\d*)",
        re.IGNORECASE,
    ),
]


def _parse_value(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def find_year_value_assertions(text: str) -> list[tuple[int, float]]:
    """Find all (year, value) assertions in the text.

    Returns deduplicated list of (year, value) pairs. Years restricted to
    1900-2099 to avoid matching arbitrary 4-digit numbers.
    """
    if not text:
        return []
    seen: set[tuple[int, float]] = set()
    out: list[tuple[int, float]] = []

    # Pass 1: tight regex patterns
    for pat in ASSERTION_PATTERNS:
        for m in pat.finditer(text):
            g1, g2 = m.group(1), m.group(2)
            # Determine which group is the year (4-digit, in plausible range)
            for year_str, val_str in [(g1, g2), (g2, g1)]:
                try:
                    y = int(year_str)
                except (ValueError, TypeError):
                    continue
                if 1900 <= y <= 2099:
                    v = _parse_value(val_str)
                    if v is None:
                        continue
                    # Skip if value is itself a year-like int
                    if isinstance(v, float) and v.is_integer() and 1900 <= v <= 2099:
                        continue
                    pair = (y, v)
                    if pair not in seen:
                        seen.add(pair)
                        out.append(pair)
                    break

    # Pass 2: proximity-based fallback for "rate for X is V ... for the year Y"
    # patterns the tight regex misses. Look for numbers near years within a
    # 100-char window and pair them. Conservative: only adds NEW pairs not
    # already found. We use the FIRST year/value pair found within proximity
    # of each other in a sentence-like span.
    if not out:
        # Tokenise into rough sentences; pair the first decimal number with
        # the first plausible 4-digit year in each sentence.
        for sent in re.split(r"(?<=[.!?\n])\s+", text):
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", sent)
            if not year_match:
                continue
            y = int(year_match.group(1))
            # Find a decimal number that's NOT itself a year
            for vm in re.finditer(r"\b([\d,]+\.\d+|\d{1,3}(?:,\d{3})+|\d+\.\d+)\b", sent):
                v = _parse_value(vm.group(1))
                if v is None:
                    continue
                if isinstance(v, float) and v.is_integer() and 1900 <= v <= 2099:
                    continue
                # Avoid picking up the year itself
                if abs(v - y) < 0.001:
                    continue
                pair = (y, v)
                if pair not in seen:
                    seen.add(pair)
                    out.append(pair)
                    break  # one pair per sentence
    return out


def is_refusal(text: str) -> bool:
    """True if the text contains a clear refusal phrase."""
    if not text:
        return False
    lower = text.lower()
    return any(p in lower for p in REFUSAL_PHRASES)


def get_data_country_match(tool_calls_json: str | list, target_iso: str, target_name: str) -> bool | None:
    """Did any get_data call use the target country (by ISO3 or name)?

    Returns None if no get_data calls were made.
    """
    if isinstance(tool_calls_json, str):
        try:
            calls = json.loads(tool_calls_json)
        except json.JSONDecodeError:
            return None
    else:
        calls = tool_calls_json
    if not calls:
        return None
    target_iso_u = (target_iso or "").upper()
    target_name_u = (target_name or "").upper()
    saw_get_data = False
    for c in calls:
        if c.get("tool") != "get_data":
            continue
        saw_get_data = True
        for ctry in c.get("input", {}).get("countries", []):
            if not isinstance(ctry, str):
                continue
            up = ctry.upper()
            if target_iso_u and target_iso_u in up:
                return True
            if target_name_u and target_name_u in up:
                return True
    return False if saw_get_data else None


@dataclass
class RefinedClassification:
    assertion_type: str  # 'refused' | 'value_for_target' | 'value_for_other_year' | 'value_for_other_country' | 'unknown'
    asserted_value: float | None
    asserted_year: int | None
    all_year_value_pairs: list[tuple[int, float]]
    refused: bool
    country_correct: bool | None  # True/False/None (no get_data call)
    is_true_fabrication: bool
    is_graceful_fallback: bool
    is_country_substitution: bool


def classify_response(
    *,
    target_country_iso: str,
    target_country_name: str,
    target_year: int | None,
    response_text: str,
    tool_calls_json: str | list,
    query_type: str,
    prompt_type: str = "direct",
) -> RefinedClassification:
    """Classify a Condition B response according to refined metric design.

    target_year: for HALLUCINATION_T1 + direct prompts = the (out-of-frontier)
                 requested year; for baseline_latest queries = None (no
                 specific year was asked, even if the ground-truth file
                 records a gt_latest_year).
    prompt_type: 'baseline_latest' (asks for "latest available") or 'direct'
                 (asks for a specific year). Only direct prompts have a
                 target_year for fabrication-vs-fallback distinction.
    """
    # Override target_year to None for baseline_latest — the user didn't ask
    # about a specific year, so any year-value pair the model emits is
    # historical context, not a fabrication-of-target.
    if prompt_type == "baseline_latest":
        target_year = None
    pairs = find_year_value_assertions(response_text)
    refused = is_refusal(response_text)
    cc = get_data_country_match(tool_calls_json, target_country_iso, target_country_name)

    # Find the assertion that targets the requested year, if any
    target_assertion = None
    if target_year is not None:
        for y, v in pairs:
            if y == target_year:
                target_assertion = (y, v)
                break

    # Find the most-recent year assertion (for fallback detection)
    other_year_assertion = None
    if pairs and target_assertion is None:
        # Pick the latest year that's not the target
        candidates = [
            (y, v) for y, v in pairs
            if (target_year is None or y != target_year)
        ]
        if candidates:
            other_year_assertion = max(candidates, key=lambda yv: yv[0])

    # Decide assertion_type
    is_hall = query_type.startswith("HALLUCINATION")

    if cc is False and pairs:
        # Country substitution: model called with wrong country and is reporting a value
        atype = "value_for_other_country"
        asserted_value = pairs[0][1] if pairs else None
        asserted_year = pairs[0][0] if pairs else None
    elif target_assertion is not None:
        # Direct assertion of value for target year
        atype = "value_for_target"
        asserted_year, asserted_value = target_assertion
    elif refused and other_year_assertion is not None:
        # Refused requested year, but offered labeled different-year data
        atype = "value_for_other_year"
        asserted_year, asserted_value = other_year_assertion
    elif refused and not pairs:
        # Clean refusal, no numbers
        atype = "refused"
        asserted_value = None
        asserted_year = None
    elif other_year_assertion is not None:
        # No clear refusal but value is for a different year
        atype = "value_for_other_year"
        asserted_year, asserted_value = other_year_assertion
    elif pairs:
        # Some pairs but unclear which one is the answer
        atype = "unknown"
        asserted_year, asserted_value = pairs[0]
    else:
        atype = "unknown" if not refused else "refused"
        asserted_value = None
        asserted_year = None

    # Derived flags (only meaningful on hallucination tiers)
    is_true_fab = is_hall and atype == "value_for_target"
    is_fallback = is_hall and atype == "value_for_other_year"
    is_substitution = atype == "value_for_other_country"

    return RefinedClassification(
        assertion_type=atype,
        asserted_value=asserted_value,
        asserted_year=asserted_year,
        all_year_value_pairs=pairs,
        refused=refused,
        country_correct=cc,
        is_true_fabrication=is_true_fab,
        is_graceful_fallback=is_fallback,
        is_country_substitution=is_substitution,
    )
