"""Offline coverage report over explicit expected IDs and exported execution records.

Run: python -m synth.evaluation.coverage expected-ids.json records.json
Each record: item_id, status (completed/error/pending), name, value, metadata.
Use the exact evaluator version and one experiment/batch per report.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any


def report(expected_ids: list[str], records: list[dict[str, Any]],
           score_name: str = "policy_correctness") -> dict[str, Any]:
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("Expected IDs must be unique")
    expected = set(expected_ids)
    relevant = [r for r in records if r.get("name") == score_name]
    unexpected = sorted({r["item_id"] for r in relevant} - expected)
    rows = [r for r in relevant if r["item_id"] in expected]
    counts = Counter(r["item_id"] for r in rows)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    scored, passed, policy_failed, malformed, errors, pending, invalid = (set() for _ in range(7))
    for row in rows:
        key, status = row["item_id"], row.get("status")
        if status == "error":
            errors.add(key)
        elif status == "pending":
            pending.add(key)
        elif status == "completed" and type(row.get("value")) in (bool, int, float) and row["value"] in (0, 1):
            scored.add(key)
            if row.get("metadata", {}).get("status") == "malformed_output":
                malformed.add(key)
            elif row["value"]:
                passed.add(key)
            else:
                policy_failed.add(key)
        else:
            invalid.add(key)
    missing = expected - scored
    return {"expected_count": len(expected), "scored_count": len(scored),
            "passed_count": len(passed), "policy_failure_count": len(policy_failed),
            "malformed_output_ids": sorted(malformed), "missing_score_ids": sorted(missing),
            "execution_error_ids": sorted(errors), "pending_ids": sorted(pending),
            "invalid_record_ids": sorted(invalid), "duplicate_ids": duplicates,
            "unexpected_ids": unexpected,
            "complete": bool(expected) and not (missing or errors or pending or invalid or duplicates or unexpected)}


if __name__ == "__main__":
    from pathlib import Path
    result = report(json.loads(Path(sys.argv[1]).read_text()), json.loads(Path(sys.argv[2]).read_text()))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["complete"] else 1)
