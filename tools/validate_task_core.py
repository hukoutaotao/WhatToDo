"""Offline structural checks for the development Task-core contract.

Passing this check does not resolve references, authorize a mutation or create a
Task. Error output contains locations and constraint names, never input values.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "formats/input/task-core.schema.json"
CASES_PATH = ROOT / "tests/fixtures/task_core/cases.json"


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def load_json(path: Path) -> Any:
    """Read strict UTF-8 JSON without silently losing duplicated fields."""
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_object_without_duplicates,
        parse_constant=_reject_constant,
    )


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    constraint: str


@lru_cache(maxsize=16)
def schema_validator(path: Path) -> Draft202012Validator:
    schema = load_json(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_task_core(payload: Any) -> tuple[ValidationIssue, ...]:
    """Return structural issues without modifying the supplied snapshot."""
    return validate_schema(SCHEMA_PATH, payload)


def validate_schema(path: Path, payload: Any) -> tuple[ValidationIssue, ...]:
    """Validate a bundled schema; this helper does not grant write authority."""
    issues = []
    for error in schema_validator(path).iter_errors(payload):
        # JSON Pointer escapes retain unambiguous paths, including array items.
        pointer = "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1")
            for part in error.absolute_path
        )
        issues.append(ValidationIssue(pointer or "/", str(error.validator)))
    return tuple(sorted(set(issues), key=lambda item: (item.path, item.constraint)))


def check_examples() -> bool:
    fixture = load_json(CASES_PATH)
    if fixture.get("synthetic") is not True:
        raise ValueError("Only synthetic examples belong in this check")
    success = True
    for case in fixture["cases"]:
        actual = not validate_task_core(case["payload"])
        matched = actual is case["valid"]
        success = success and matched
        print(f"{'PASS' if matched else 'FAIL'} {case['id']}")
    print(f"Checked {len(fixture['cases'])} synthetic cases.")
    return success


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Task-core JSON snapshots")
    parser.add_argument("--examples", action="store_true", help="Check synthetic regression examples")
    args = parser.parse_args(argv)
    if not args.paths and not args.examples:
        parser.error("Supply --examples or a JSON snapshot path")

    valid = True
    unreadable = False
    if args.examples:
        valid = check_examples()
    for path in args.paths:
        try:
            payload = load_json(path)
        except (OSError, UnicodeError, ValueError):
            print(f"INVALID {path.name}: unreadable or invalid JSON")
            unreadable = True
            continue
        issues = validate_task_core(payload)
        valid = valid and not issues
        print(f"{'INVALID' if issues else 'VALID'} {path.name}")
        for issue in issues:
            print(f"  {issue.path}: violates {issue.constraint}")
    return 2 if unreadable else (0 if valid else 1)


if __name__ == "__main__":
    raise SystemExit(main())
