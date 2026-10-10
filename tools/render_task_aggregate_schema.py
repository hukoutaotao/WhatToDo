"""Bundle existing contracts into a local-reference aggregate without editing them."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "formats/input/task-aggregate.schema.json"


def embed(schema, name):
    result = deepcopy(schema)
    result.pop("$schema", None);result.pop("$id", None)
    def visit(node):
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key == "$ref":
                    if not isinstance(value, str) or not value.startswith("#/"): raise ValueError("Only local pointers may be bundled")
                    node[key] = "#/$defs/" + name + value[1:]
                else: visit(value)
        elif isinstance(node, list):
            for value in node: visit(value)
    visit(result)
    return result


def render():
    reference = {"type": "string", "minLength": 1, "maxLength": 200, "pattern": "\\S"}
    instant = {"type": "string", "format": "date-time", "pattern": "T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$"}
    def obj(props): return {"type": "object", "required": list(props), "properties": props, "additionalProperties": False}
    def nullable(value): return {"anyOf": [value, {"type": "null"}]}
    positive = {"type": "integer", "minimum": 1}
    definition = obj({"kind": {"enum": ["TASKTYPE", "TASK_TEMPLATE"]}, "id": reference, "version": reference})
    total = obj({"seconds": {"type": "integer", "minimum": 0}, "source_ref": reference, "observed_at": instant, "basis": {"enum": ["USER_REPORT", "TEMPLATE_DEFAULT"]}, "definition_ref": nullable(definition)})
    total["allOf"] = [{"if": {"properties": {"basis": {"const": "TEMPLATE_DEFAULT"}}}, "then": {"properties": {"definition_ref": definition}}, "else": {"properties": {"definition_ref": {"type": "null"}}}}]
    timing = obj({"created_at": nullable(instant), "release": nullable(obj({"instant": instant, "original_value": instant, "source_ref": reference})), "deadline": nullable(obj({"due_ref": reference, "value": {"$ref": "#/$defs/due"}})), "completed_at": nullable(instant)})
    work = obj({"total_estimate": nullable(total), "minimum_session_seconds": nullable(positive), "fragmentable": nullable({"type": "boolean"})})
    stage = obj({"stage_id": reference, "revision": positive, "title": {"type": "string", "minLength": 1, "maxLength": 200, "pattern": "\\S"}})
    field = obj({"field": {"type": "string", "pattern": "^/", "maxLength": 500}, "source_ref": reference})
    result = obj({"schema_version": {"const": "0.1.0-draft"}, "core": {"$ref": "#/$defs/core"}, "effort": {"$ref": "#/$defs/effort"}, "timing": timing, "work": work, "stage_details": {"type": "array", "items": stage}, "provenance": {"type": "array", "items": field}})
    result.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:whattodo:task-aggregate:0.1.0-draft", "title": "Generic composed Task snapshot (development contract)", "description": "Shape only; semantic consistency, references, actual caller authority and audited persistence remain required.", "$defs": {name: embed(json.loads((ROOT / ("formats/input/" + filename + ".schema.json")).read_text(encoding="utf-8")), name) for name, filename in (("core", "task-core"), ("effort", "effort"), ("due", "normalized-due"))}})
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def main():
    content = render()
    if sys.argv[1:] == ["--check"]:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != content:
            print("Aggregate bundle drift: regenerate and review", file=sys.stderr);return 1
        print("Task aggregate bundle matches its three unchanged source contracts");return 0
    if sys.argv[1:]: raise ValueError("Use no arguments or --check")
    TARGET.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
