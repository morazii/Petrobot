"""Tool schemas for flat CSV-style backend mode."""

FLAT_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_wells",
            "description": (
                "Find flat well rows from the CSV-style schema using Mongo-style filters. "
                "Use flat field names such as operator, field_name, current_status, well_name, "
                "drillers_td_m, spud_date, latitude, longitude."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": (
                            "MongoDB-style filter on flat fields. Examples: "
                            '{"operator": "ADNOC"} '
                            '{"field_name": "Delta", "current_status": "Drilling"}'
                        ),
                    },
                    "projection": {
                        "type": "object",
                        "description": "Optional projection document.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max documents to return. Default 100, max 1000.",
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
            "description": (
                "Run a MongoDB aggregation pipeline on flat well rows. "
                "Use fields like operator, field_name, current_status, well_objective, bore_type."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "array",
                        "description": (
                            "Aggregation pipeline stage array. Example: "
                            '[{"$group": {"_id": "$field_name", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]'
                        ),
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
            "description": "Retrieve one flat row by well_name (or close fuzzy match).",
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
            "description": (
                "Return map rows with name, field, operator, status, environment, lat, lon "
                "from flat schema columns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "object",
                        "description": "Optional MongoDB-style filter.",
                    },
                },
                "required": [],
            },
        },
    },
]

