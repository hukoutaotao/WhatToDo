"""Developer-only offline validation of the bundled development contracts."""

import argparse
from pathlib import Path

from tools.validate_task_core import ROOT, load_json, validate_schema


SCHEMAS = {
    "task-aggregate": ROOT / "formats/input/task-aggregate.schema.json",
    "ai-job": ROOT / "formats/input/ai-job.schema.json",
    "ai-export": ROOT / "formats/input/ai-export.schema.json",
    "ai-result": ROOT / "formats/input/ai-result.schema.json",
    "remaining-prediction": ROOT / "formats/input/remaining-prediction.schema.json",
    "behavior-candidate": ROOT / "formats/input/behavior-candidate.schema.json",
    "ai-import-record": ROOT / "formats/input/ai-import-record.schema.json",
    "task-core": ROOT / "formats/input/task-core.schema.json",
    "effort": ROOT / "formats/input/effort.schema.json",
    "work-observation": ROOT / "formats/input/work-observation.schema.json",
    "source": ROOT / "formats/input/source.schema.json",
    "candidate": ROOT / "formats/input/candidate.schema.json",
    "command": ROOT / "formats/input/command.schema.json",
    "review-response": ROOT / "formats/input/review-response.schema.json",
    "relationship-rule": ROOT / "formats/input/relationship-rule.schema.json",
    "task-relation": ROOT / "formats/input/task-relation.schema.json",
    "generation-occurrence": ROOT / "formats/input/generation-occurrence.schema.json",
    "expiration-notice": ROOT / "formats/input/expiration-notice.schema.json",
    "dispatch-result": ROOT / "formats/input/dispatch-result.schema.json",
    "normalized-due": ROOT / "formats/input/normalized-due.schema.json",
    "forecast-window": ROOT / "formats/input/forecast-window.schema.json",
    "today-lock": ROOT / "formats/input/today-lock.schema.json",
    "calendar-event": ROOT / "formats/input/calendar-event.schema.json",
    "availability": ROOT / "formats/input/availability.schema.json",
    "goal": ROOT / "formats/input/goal.schema.json",
    "milestone": ROOT / "formats/input/milestone.schema.json",
    "exam": ROOT / "formats/input/exam.schema.json",
    "goal-progress": ROOT / "formats/input/goal-progress.schema.json",
    "goal-onboarding": ROOT / "formats/input/goal-onboarding.schema.json",
    "plan": ROOT / "formats/output/plan.schema.json",
}


def validate_contract(name, payload):
    return validate_schema(SCHEMAS[name], payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", choices=SCHEMAS)
    parser.add_argument("--examples", type=Path, help="Explicitly synthetic expectation bundle")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    if args.paths and not args.contract:
        parser.error("--contract is required for snapshots")
    if not args.paths and not args.examples:
        parser.error("Supply snapshot paths or --examples")
    success = True
    try:
        if args.examples:
            fixture = load_json(args.examples)
            if fixture.get("synthetic") is not True:
                raise ValueError("Not a synthetic expectation bundle")
            for case in fixture["cases"]:
                matched = (not validate_contract(case["contract"], case["payload"])) is case["valid"]
                success = success and matched
                print(f"{'PASS' if matched else 'FAIL'} {case['id']}")
            print(f"Checked {len(fixture['cases'])} synthetic cases.")
        for path in args.paths:
            issues = validate_contract(args.contract, load_json(path))
            success = success and not issues
            print(f"{'INVALID' if issues else 'VALID'} {path.name}")
            for issue in issues:
                print(f"  {issue.path}: violates {issue.constraint}")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("INVALID: unreadable or malformed input/expectation bundle")
        return 2
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
