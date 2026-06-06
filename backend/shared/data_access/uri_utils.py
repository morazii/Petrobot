"""
backend/shared/data_access/uri_utils.py
-----------------------
Conversion helpers between human-readable values and OSDU reference URI format.

OSDU stores entity references as fully-qualified URIs, e.g.:
    "osdu:master-data--Field:delta:"
    "osdu:reference-data--WellboreStatus:DRILLING:"

These helpers let the analytics layer accept plain English from the LLM/user
and convert to the correct URI for MongoDB queries, and back again for display.
"""

# â”€â”€ URI templates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_FIELD_PREFIX      = "osdu:master-data--Field:"
_STATUS_PREFIX     = "osdu:reference-data--WellboreStatus:"
_OBJECTIVE_PREFIX  = "osdu:reference-data--WellPurpose:"
_BORETYPE_PREFIX   = "osdu:reference-data--WellBoreType:"
_ENVIRONMENT_PREFIX = "osdu:reference-data--WellOperatingEnvironment:"
_OPERATOR_PREFIX   = "osdu:master-data--Organisation:"
_BLOCK_PREFIX      = "osdu:master-data--LicenseBlock:"

# â”€â”€ Objective normalisation map (user-friendly â†’ OSDU token) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_OBJECTIVE_MAP = {
    "oil producer":   "OIL_PRODUCER",
    "gas producer":   "GAS_PRODUCER",
    "water injector": "WATER_INJECTOR",
    "gas injector":   "GAS_INJECTOR",
    "appraisal":      "APPRAISAL",
}

# â”€â”€ Bore-type normalisation map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_BORETYPE_MAP = {
    "development": "DEVELOPMENT",
    "exploration": "EXPLORATION",
    "appraisal":   "APPRAISAL",
}

# â”€â”€ Environment normalisation map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_ENVIRONMENT_MAP = {
    "onshore":         "ONSHORE",
    "offshore":        "OFFSHORE",
    "offshore-north":  "OFFSHORE",   # sector-level detail is in data.tags / well name
    "offshore-south":  "OFFSHORE",
    "offshore-east":   "OFFSHORE",
    "offshore-west":   "OFFSHORE",
}


# â”€â”€ To-URI helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def to_field_uri(name: str) -> str:
    """
    Convert a plain field name to its OSDU URI.
    e.g.  "Delta" â†’ "osdu:master-data--Field:delta:"
          "delta" â†’ "osdu:master-data--Field:delta:"
    """
    return f"{_FIELD_PREFIX}{name.strip().lower()}:"


def to_status_uri(status: str) -> str:
    """
    Convert a plain status string to its OSDU WellboreStatus URI.
    e.g.  "Drilling" â†’ "osdu:reference-data--WellboreStatus:DRILLING:"
          "shut-in"  â†’ "osdu:reference-data--WellboreStatus:SHUT-IN:"
    """
    normalised = status.strip().upper().replace(" ", "-")
    return f"{_STATUS_PREFIX}{normalised}:"


def to_objective_uri(objective: str) -> str:
    """
    Convert a plain well objective to its OSDU WellPurpose URI.
    e.g.  "Oil Producer" â†’ "osdu:reference-data--WellPurpose:OIL_PRODUCER:"
    """
    key = objective.strip().lower()
    token = _OBJECTIVE_MAP.get(key, key.upper().replace(" ", "_"))
    return f"{_OBJECTIVE_PREFIX}{token}:"


def to_boretype_uri(bore_type: str) -> str:
    """
    Convert a plain bore type to its OSDU WellBoreType URI.
    e.g.  "Development" â†’ "osdu:reference-data--WellBoreType:DEVELOPMENT:"
    """
    key = bore_type.strip().lower()
    token = _BORETYPE_MAP.get(key, key.upper())
    return f"{_BORETYPE_PREFIX}{token}:"


def to_environment_uri(environment: str) -> str:
    """
    Convert a plain operating environment to its OSDU URI.
    e.g.  "Onshore"       â†’ "osdu:reference-data--WellOperatingEnvironment:ONSHORE:"
          "Offshore-North" â†’ "osdu:reference-data--WellOperatingEnvironment:OFFSHORE:"
    """
    key = environment.strip().lower()
    token = _ENVIRONMENT_MAP.get(key, key.upper())
    return f"{_ENVIRONMENT_PREFIX}{token}:"


def to_operator_uri(operator: str) -> str:
    """
    Convert an operator name to its OSDU Organisation URI.
    e.g.  "ENI" â†’ "osdu:master-data--Organisation:eni:"
    """
    slug = operator.strip().lower().replace(" ", "-")
    return f"{_OPERATOR_PREFIX}{slug}:"


# â”€â”€ From-URI helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def from_uri(uri: str) -> str:
    """
    Extract the human-readable token from any OSDU reference URI.
    e.g.  "osdu:master-data--Field:delta:"             â†’ "delta"
          "osdu:reference-data--WellboreStatus:DRILLING:" â†’ "DRILLING"
          "osdu:master-data--Organisation:eni:"         â†’ "eni"

    Returns the original string unchanged if it does not look like an OSDU URI.
    """
    if not isinstance(uri, str) or not uri.startswith("osdu:"):
        return uri
    # Split on ":" and return the last non-empty segment
    parts = [p for p in uri.split(":") if p.strip()]
    return parts[-1] if parts else uri


def from_field_uri(uri: str) -> str:
    """Return field name with title-case. e.g. 'delta' â†’ 'Delta'."""
    return from_uri(uri).title()


def from_status_uri(uri: str) -> str:
    """Return status with title-case. e.g. 'DRILLING' â†’ 'Drilling'."""
    raw = from_uri(uri)
    return raw.replace("-", " ").title().replace(" ", "-")


def from_objective_uri(uri: str) -> str:
    """Return objective in readable form. e.g. 'OIL_PRODUCER' â†’ 'Oil Producer'."""
    raw = from_uri(uri)
    return raw.replace("_", " ").title()


def from_boretype_uri(uri: str) -> str:
    """Return bore type in readable form. e.g. 'DEVELOPMENT' â†’ 'Development'."""
    return from_uri(uri).title()


def from_environment_uri(uri: str) -> str:
    """Return environment in readable form. e.g. 'ONSHORE' â†’ 'Onshore'."""
    return from_uri(uri).title()

