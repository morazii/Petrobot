"""
backend/db/seed_mongo.py
------------------------
One-time (idempotent) script to ingest all OSDU well records into local MongoDB.

Storage strategy: Full OSDU envelope stored as-is.
  - _id is set to the OSDU record `id` field
  - No flattening or transformation — data.FieldID, data.WellStatusID etc. retain their URI format
  - A uri_utils module handles URI ↔ plain-value conversion at query time
  - Re-running this script is safe — duplicate _id errors are silently skipped

Run from the project root:
    python -m backend.db.seed_mongo
    # or
    python backend/db/seed_mongo.py
"""

import json
import sys
import time
from pathlib import Path

from pymongo import ASCENDING, IndexModel
from pymongo.errors import BulkWriteError

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]          # project root (Petrobot/)
DATA_FILE = ROOT / "Data" / "osdu_well_records.json"

# Add project root to path so imports work when run directly
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.mongo_client import get_wells_collection   # noqa: E402


# ── Index definitions ──────────────────────────────────────────────────────────
INDEXES = [
    # Well identity
    IndexModel([("data.Name", ASCENDING)],          name="idx_name"),
    IndexModel([("data.NameAliases.AliasName", ASCENDING)], name="idx_alias"),

    # Core query fields (URI-based)
    IndexModel([("data.FieldID", ASCENDING)],        name="idx_field"),
    IndexModel([("data.WellStatusID", ASCENDING)],   name="idx_status"),
    IndexModel([("data.WellObjectiveID", ASCENDING)], name="idx_objective"),
    IndexModel([("data.WellBoreTypeID", ASCENDING)], name="idx_boretype"),
    IndexModel([("data.OperatingEnvironmentID", ASCENDING)], name="idx_environment"),

    # Plain-value fields (no URI wrapping needed)
    IndexModel([("data.OriginalOperator", ASCENDING)], name="idx_operator"),
    IndexModel([("data.Platform", ASCENDING)],        name="idx_platform"),

    # Date fields
    IndexModel([("data.SpudDate", ASCENDING)],       name="idx_spud_date"),
    IndexModel([("data.StatusDate", ASCENDING)],     name="idx_status_date"),

    # OSDU metadata
    IndexModel([("kind", ASCENDING)],                name="idx_kind"),
]


def load_records(path: Path) -> list[dict]:
    """Load and parse the OSDU JSON file."""
    print(f"  Loading {path} …")
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    print(f"  Loaded {len(records):,} records from file.")
    return records


def prepare_documents(records: list[dict]) -> list[dict]:
    """
    Prepare records for MongoDB insertion:
      - Set _id = record["id"]  (OSDU well ID becomes MongoDB _id)
      - Keep all other fields exactly as-is
    """
    docs = []
    for rec in records:
        doc = dict(rec)                  # shallow copy
        doc["_id"] = doc.pop("id")      # promote 'id' to '_id'
        docs.append(doc)
    return docs


def insert_documents(collection, docs: list[dict]) -> tuple[int, int]:
    """
    Insert documents using ordered=False so duplicate _id errors don't abort the batch.
    Returns (inserted_count, duplicate_count).
    """
    inserted = 0
    duplicates = 0
    try:
        result = collection.insert_many(docs, ordered=False)
        inserted = len(result.inserted_ids)
    except BulkWriteError as bwe:
        inserted = bwe.details.get("nInserted", 0)
        duplicates = sum(
            1 for e in bwe.details.get("writeErrors", [])
            if e.get("code") == 11000   # duplicate key
        )
        other_errors = [
            e for e in bwe.details.get("writeErrors", [])
            if e.get("code") != 11000
        ]
        if other_errors:
            print(f"\n  ⚠  {len(other_errors)} unexpected write error(s):")
            for e in other_errors[:5]:
                print(f"     {e}")
    return inserted, duplicates


def create_indexes(collection) -> None:
    """Create all required indexes (skips if already exist)."""
    print("  Creating indexes …")
    existing = {idx["name"] for idx in collection.list_indexes()}
    new_indexes = [idx for idx in INDEXES if idx.document["name"] not in existing]
    if new_indexes:
        collection.create_indexes(new_indexes)
        print(f"  Created {len(new_indexes)} new index(es).")
    else:
        print("  All indexes already exist — skipped.")


def print_validation(collection) -> None:
    """Print a breakdown by field, status, and operator to validate the ingest."""
    total = collection.count_documents({})
    print(f"\n{'-'*60}")
    print(f"  Total documents in collection : {total:,}")

    # -- By field --------------------------------------------------------------
    pipeline_field = [
        {"$group": {"_id": "$data.FieldID", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    fields = list(collection.aggregate(pipeline_field))
    print(f"\n  Wells by field ({len(fields)} fields):")
    for f in fields:
        label = f["_id"].split(":")[-2] if f["_id"] else "unknown"
        print(f"    {label:<20} {f['count']:>4}")

    # -- By status -------------------------------------------------------------
    pipeline_status = [
        {"$group": {"_id": "$data.WellStatusID", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    statuses = list(collection.aggregate(pipeline_status))
    print(f"\n  Wells by current status:")
    for s in statuses:
        label = s["_id"].split(":")[-2] if s["_id"] else "unknown"
        print(f"    {label:<25} {s['count']:>4}")

    # -- By operator -----------------------------------------------------------
    pipeline_op = [
        {"$group": {"_id": "$data.OriginalOperator", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    operators = list(collection.aggregate(pipeline_op))
    print(f"\n  Wells by operator:")
    for o in operators:
        print(f"    {str(o['_id']):<30} {o['count']:>4}")

    # -- Sample document -------------------------------------------------------
    sample = collection.find_one()
    if sample:
        print(f"\n  Sample document (_id): {sample['_id']}")
        print(f"    Name         : {sample.get('data', {}).get('Name')}")
        print(f"    FieldID      : {sample.get('data', {}).get('FieldID')}")
        print(f"    WellStatusID : {sample.get('data', {}).get('WellStatusID')}")
        print(f"    Operator     : {sample.get('data', {}).get('OriginalOperator')}")
        coords = (
            sample.get("data", {})
            .get("SpatialLocation", {})
            .get("Wgs84Coordinates", {})
            .get("features", [{}])
        )
        if coords:
            geom = coords[0].get("geometry", {}).get("coordinates", [])
            if len(geom) >= 2:
                print(f"    Coordinates  : lon={geom[0]}, lat={geom[1]}")
    print(f"{'-'*60}\n")


def main() -> None:
    print("\n" + "=" * 60)
    print("  PetroBot -- MongoDB Seeder")
    print("=" * 60)

    # -- Check data file --------------------------------------------------------
    if not DATA_FILE.exists():
        print(f"\n  [ERR]  Data file not found: {DATA_FILE}")
        sys.exit(1)

    # -- Connect ----------------------------------------------------------------
    print(f"\n[1/4] Connecting to MongoDB ...")
    try:
        collection = get_wells_collection()
        collection.database.client.admin.command("ping")
        print("  [OK]  Connected.")
    except Exception as exc:
        print(f"  [ERR]  Could not connect to MongoDB: {exc}")
        print("         Make sure MongoDB is running (mongod) and MONGO_URI is correct.")
        sys.exit(1)

    # -- Load -------------------------------------------------------------------
    print(f"\n[2/4] Loading OSDU records ...")
    t0 = time.perf_counter()
    records = load_records(DATA_FILE)
    docs = prepare_documents(records)

    # -- Insert -----------------------------------------------------------------
    print(f"\n[3/4] Inserting into MongoDB collection 'wells' ...")
    inserted, duplicates = insert_documents(collection, docs)
    elapsed = time.perf_counter() - t0

    if inserted > 0:
        print(f"  Inserted  : {inserted:,} documents")
    if duplicates > 0:
        print(f"  Skipped   : {duplicates:,} duplicate(s) (already existed)")
    print(f"  Elapsed   : {elapsed:.2f}s")

    # -- Indexes ----------------------------------------------------------------
    print(f"\n[4/4] Ensuring indexes ...")
    create_indexes(collection)

    # -- Validate ---------------------------------------------------------------
    print(f"\n[Validation]")
    print_validation(collection)

    total = collection.count_documents({})
    if total != 2000:
        print(f"  [WARN]  Expected 2,000 documents but found {total:,}. Check for partial ingest.")
    else:
        print("  [OK]  All 2,000 well records confirmed in MongoDB.\n")


if __name__ == "__main__":
    main()
