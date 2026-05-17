"""Tool schemas for OSDU backend mode."""

OSDU_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_wells",
            "description": (
                "Find OSDU well documents from MongoDB using a filter. "
                "Use OSDU dot-notation fields (for example data.FieldID, data.WellStatusID)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": (
                            "MongoDB filter using OSDU dot-notation. Example: "
                            '{"data.OriginalOperator": "ENI"}'
                        ),
                    },
                    "projection": {
                        "type": "object",
                        "description": "Optional projection document.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max documents to return. Default 100, max 500.",
                        "default": 100,
                    },
                },
                "required": ["filter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate_wells",
            "description": "Run a MongoDB aggregation pipeline against OSDU wells data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "array",
                        "description": "Aggregation pipeline stage array.",
                        "items": {"type": "object"},
                    },
                },
                "required": ["pipeline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_well",
            "description": "Retrieve one OSDU well by name, with fuzzy matching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Well name, for example Delta-15",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_map_data",
            "description": "Return map-friendly OSDU well records with lat/lon.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": "Optional MongoDB filter.",
                    },
                },
                "required": [],
            },
        },
    },
]

