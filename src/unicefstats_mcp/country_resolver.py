"""Country-name → ISO3 resolver for `get_data`.

Added in v0.6.2 to address the country-substitution failure mode (the model
calls `get_data(countries=['BEL'])` when the user asked about Burundi). With
this resolver, `get_data` accepts either ISO3 codes or country names, so the
model can pass the human-readable name from the user's query directly and
the server does the canonical mapping.

The resolver loads the 450+ country code → name map shipped by unicefdata
(SDMX CL_COUNTRY codelist) and builds a normalized reverse index. It also
ships a small SYNONYMS table for common alternate spellings and informal
names ("USA", "UK", "Ivory Coast", "South Korea", etc.).
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

# Common alternate names that don't appear in the CL_COUNTRY list verbatim.
# Map from normalized lowercase form → canonical ISO3.
_SYNONYMS: dict[str, str] = {
    # Anglophone shortenings
    "usa": "USA",
    "us": "USA",
    "united states of america": "USA",
    "uk": "GBR",
    "great britain": "GBR",
    "britain": "GBR",
    "england": "GBR",  # imprecise but common
    # Ivory Coast / Cote d'Ivoire variants
    "ivory coast": "CIV",
    # Koreas
    "south korea": "KOR",
    "north korea": "PRK",
    # Russia
    "russia": "RUS",
    # Congos — canonical names are confusing
    "congo brazzaville": "COG",
    "congo kinshasa": "COD",
    "drc": "COD",
    "dr congo": "COD",
    # Czechia
    "czech republic": "CZE",
    # Burma / Myanmar
    "burma": "MMR",
    # East Timor
    "east timor": "TLS",
    # Cape Verde
    "cape verde": "CPV",
    # Eswatini / Swaziland
    "swaziland": "SWZ",
    # Macedonia
    "macedonia": "MKD",
    # Vatican
    "vatican": "VAT",
    "vatican city": "VAT",
    # Palestine
    "palestine": "PSE",
    # Taiwan (note: not in UN M.49 but commonly referenced)
    "taiwan": "TWN",
    # Iran
    "iran": "IRN",
    # Syria
    "syria": "SYR",
    # Laos
    "laos": "LAO",
    # Vietnam
    "vietnam": "VNM",
    # Brunei
    "brunei": "BRN",
}


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics, squash apostrophes/punctuation, collapse whitespace.

    "Côte d'Ivoire" → "cote divoire"
    "Lao People's Democratic Republic" → "lao peoples democratic republic"
    """
    if not isinstance(s, str):
        return ""
    # Decompose unicode and strip combining marks
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Replace separators with space; drop apostrophes/quotes
    out = []
    prev_space = False
    for c in s:
        if c.isalnum():
            out.append(c)
            prev_space = False
        elif c in " -_/.,()":
            if not prev_space:
                out.append(" ")
                prev_space = True
        # else: drop apostrophes, quotes, etc.
    return "".join(out).strip()


@lru_cache(maxsize=1)
def _load_country_index() -> tuple[dict[str, str], dict[str, str]]:
    """Load the unicefdata country YAML and build code-set + name-index.

    Returns (valid_codes_dict, name_to_code_index).
      - valid_codes_dict: ISO3 → canonical name from CL_COUNTRY
      - name_to_code_index: normalized name → ISO3
    """
    import os

    import unicefdata
    import yaml  # type: ignore[import-untyped]

    yaml_path = os.path.join(
        os.path.dirname(unicefdata.__file__),
        "metadata", "current", "_unicefdata_countries.yaml",
    )
    if not os.path.exists(yaml_path):
        return {}, {}

    with open(yaml_path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    code_to_name = doc.get("countries", {}) or {}
    code_to_name = {
        k.upper(): v
        for k, v in code_to_name.items()
        if isinstance(k, str) and isinstance(v, str)
    }

    name_index: dict[str, str] = {}
    for code, name in code_to_name.items():
        name_index[_normalize(name)] = code
        # Also index the code itself (case-insensitive ISO3 input)
        name_index[code.lower()] = code
    # Layer synonyms on top
    for synonym, code in _SYNONYMS.items():
        if code in code_to_name:
            name_index[_normalize(synonym)] = code
    return code_to_name, name_index


def resolve_country(input_str: str) -> str | None:
    """Resolve a single user input (ISO3 or name) to a canonical ISO3 code.

    Returns the ISO3 code on success, None if it can't be resolved.
    """
    if not isinstance(input_str, str):
        return None
    s = input_str.strip()
    if not s:
        return None
    valid_codes, name_index = _load_country_index()
    # Fast path: already a valid 3-letter ISO3
    if len(s) == 3 and s.isalpha() and s.upper() in valid_codes:
        return s.upper()
    # Normalized lookup
    return name_index.get(_normalize(s))


def resolve_countries(
    inputs: list[str],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Resolve a list of country inputs (ISO3 codes or names) to canonical ISO3.

    Returns:
      - resolved: list of ISO3 codes (same length as inputs that resolved successfully)
      - resolutions: dict mapping original input → resolved ISO3, only for inputs
                     that needed name → code resolution (i.e., not already ISO3)
      - unresolved: list of inputs that could not be resolved

    The resolutions map is what `get_data` echoes back so the model can see
    "Burundi → BDI" and confirm the intent matched.
    """
    resolved: list[str] = []
    resolutions: dict[str, str] = {}
    unresolved: list[str] = []
    for raw in inputs:
        code = resolve_country(raw)
        if code is None:
            unresolved.append(raw)
            continue
        resolved.append(code)
        # If the original input was a name (not already ISO3), record the resolution
        if not (isinstance(raw, str) and len(raw.strip()) == 3 and raw.strip().upper() == code):
            resolutions[raw] = code
    return resolved, resolutions, unresolved
