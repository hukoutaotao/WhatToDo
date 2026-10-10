# Task core contract — development draft 0.1.0

Scope: [M2-01.a](../../plan/tasks/M2_CONTRACTS.md#m2-01a), under the user's [development-first instruction](../../plan/DECISIONS.md#d-080--develop-the-system-before-completing-personal-intake). This is an executable development contract, not the frozen full Task schema or a live application.

[Schema](task-core.schema.json) · [Validator](../../tools/validate_task_core.py) · [Synthetic cases](../../tests/fixtures/task_core/cases.json) · [Tests](../../tests/test_task_core_contract.py)

## Meaning and accepted boundaries

| Field | Meaning / authority |
| --- | --- |
| schema_version | Exactly `0.1.0-draft`; unrecognized versions are rejected rather than silently adapted |
| task_id / revision | Stable identity and positive snapshot revision; comparison with stored state is future application work |
| title / domain / context | Concrete work label and generic grouping; no course-specific logic or context importance scalar |
| task_type_ref | Versioned type reference, or null while unresolved; registry validation and preset adoption remain M1B/M2 |
| acceptance | An accepted snapshot carries an authority reference. Candidates are a separate future M2-03 contract; this validator cannot accept a candidate or prove authority |
| completion | `INCOMPLETE` or `COMPLETE` only, per D-025. Partial work will be represented by effort/session/stage contracts |
| disposition | `ACTIVE`, `CANCELLED` or `EXPIRED`, separate from completion. ACTIVE means ordinary non-cancelled/non-expired history, so COMPLETE/ACTIVE is representable |
| requiredness | `REQUIRED`, `OPTIONAL` or `EXPIRING` only, per D-036/044; independent of deadline and importance |
| importance / difficulty | Task importance and each thinking/repetition/new-learning dimension are integers 1–5, per D-035/037/043 |
| expiration | Only EXPIRING tasks carry a condition reference. EXPIRED snapshots retain INCOMPLETE and a notice reference, per D-073. A reference string is not proof of successful delivery |
| metadata | Derived trust/freshness/conflict and overdue metadata, never completion states. UNKNOWN remains explicit; overdue does not cause expiry |

Objects reject unknown fields. New fields require a versioned contract change rather than silent stripping. Null type/context references are unresolved structural placeholders; they do not claim that those facts are unnecessary for real activation.

This core snapshot deliberately does not contain remaining effort, work observations, stages, exact deadlines, calendar times, command authority envelopes or relationships. M2-02 through M2-09 own those contracts. A structurally valid core snapshot is not a complete schedulable Task. Every later mutation still needs resolved references, actual authority, state-version checks and atomic audit; no database or actual personal Task is written by these tools.

All 29 examples are explicitly synthetic. They exercise independent axes, retained cancelled/expired history, completed previews, high-importance optional work, stale derived metadata and generic non-course context, plus 21 rejected cases. None imports the user's course progress or supplies missing personal values.

## Run developer checks

Use a Python environment with [the contract-check dependency](../../requirements-contracts.txt) installed. The current run used Python 3.13.5 and jsonschema 4.23.0; this check harness does not select the final application language/toolchain (M2-16).

```powershell
python -m pip install -r requirements-contracts.txt
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/validate_task_core.py --examples
```

For one developer-authored core snapshot:

```powershell
python tools/validate_task_core.py path/to/snapshot.json
```

Exit codes: 0 for structural success or matching all example expectations; 1 for schema-invalid snapshots or failed expectations; 2 for unreadable/invalid JSON. The parser rejects duplicate keys and non-finite JSON numbers. Diagnostics report JSON Pointer paths and constraint names without including rejected field values. The user-facing system will accept natural language/guided replies; this JSON tool is for developers, not the normal intake flow.

The schema uses [JSON Schema Draft 2020-12 structural validation](https://json-schema.org/draft/2020-12/json-schema-validation) and the library's [Draft202012Validator API](https://python-jsonschema.readthedocs.io/en/stable/validate/). Schema validation alone cannot resolve authority or personal truth.
