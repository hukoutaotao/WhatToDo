"""Conservative schema-evolution decisions; no persistence or write authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
from jsonschema import Draft202012Validator


ANNOTATIONS = frozenset(("title", "description", "$comment", "examples"))
SIMPLE_KEYS = frozenset(("$schema", "$id", "type", "properties", "required", "additionalProperties"))


def _has_reference(value):
    if isinstance(value, dict):
        return any(key in ("$ref", "$dynamicRef", "$recursiveRef") or _has_reference(item) for key, item in value.items())
    if isinstance(value, list): return any(_has_reference(item) for item in value)
    return False


def _plain_object(schema):
    # This restricted language has satisfiable properties and no reference,
    # cross-field, or nested constraints. It permits actual inclusion proofs.
    props = schema.get("properties", {})
    return (set(schema) <= SIMPLE_KEYS and schema.get("type") == "object"
            and schema.get("additionalProperties") is False
            and isinstance(props, dict)
            and set(schema.get("required", [])) <= set(props)
            and all(isinstance(child, dict) and set(child) == {"type"}
                    and child["type"] in ("string", "integer", "number", "boolean", "null")
                    for child in props.values()))


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def semantic_schema(value):
    if isinstance(value, dict):
        # Property/definition names can themselves be "description" etc.
        # Annotation filtering applies to schema nodes, not arbitrary maps.
        result = {}
        for key, item in value.items():
            if key in ANNOTATIONS: continue
            if key in ("properties", "$defs", "definitions", "patternProperties", "dependentSchemas"):
                result[key] = {name: semantic_schema(child) for name, child in item.items()}
            elif key in ("allOf", "anyOf", "oneOf", "prefixItems"):
                result[key] = [semantic_schema(child) for child in item]
            elif key in ("additionalProperties", "unevaluatedProperties", "items", "contains", "propertyNames", "not", "if", "then", "else", "additionalItems", "unevaluatedItems", "contentSchema"):
                result[key] = semantic_schema(item)
            else:
                # const/enum/default/dependentRequired and custom data maps are
                # instance/keyword data; annotation-like keys there are data.
                result[key] = item
        return result
    if isinstance(value, list): return [semantic_schema(item) for item in value]
    return value


@dataclass(frozen=True)
class EvolutionAssessment:
    classification: str
    old_input_accepted_by_new: bool | None
    new_input_accepted_by_old: bool | None
    version_bump_required: bool
    invalidated_consumers: tuple[str, ...]


def assess_evolution(old, new, *, consumers):
    if not isinstance(old, dict) or not isinstance(new, dict) or not isinstance(consumers, tuple) or not consumers or not all(isinstance(c, str) and c.strip() for c in consumers):
        raise ValueError("Schemas and affected consumers must be explicit")
    Draft202012Validator.check_schema(old)
    Draft202012Validator.check_schema(new)
    if old != new and (_has_reference(old) or _has_reference(new)):
        return EvolutionAssessment("REVIEW_REQUIRED", None, None, True, consumers)
    dialect = "https://json-schema.org/draft/2020-12/schema"
    if old.get("$schema", dialect) != dialect or new.get("$schema", dialect) != dialect:
        return EvolutionAssessment("REVIEW_REQUIRED", None, None, True, consumers)
    before, after = semantic_schema(old), semantic_schema(new)
    if before == after:
        return EvolutionAssessment("UNCHANGED_VALIDATION", True, True, False, ())
    # This is a deliberately bounded structural analysis, not a general JSON
    # Schema subsumption prover. Complex conditions/references need review.
    comparable_before, comparable_after = dict(before), dict(after)
    comparable_before.pop("$id", None); comparable_after.pop("$id", None)
    if comparable_before == comparable_after:
        return EvolutionAssessment("IDENTITY_CHANGED", True, True, True, consumers)
    if _plain_object(before) and _plain_object(after):
        old_props, new_props = before.get("properties", {}), after.get("properties", {})
        if isinstance(old_props, dict) and isinstance(new_props, dict):
            added = set(new_props) - set(old_props)
            equal_existing = all(new_props.get(key) == value for key, value in old_props.items())
            old_required, new_required = set(before.get("required", [])), set(after.get("required", []))
            common_before = {k: v for k, v in before.items() if k not in ("$id", "properties", "required")}
            common_after = {k: v for k, v in after.items() if k not in ("$id", "properties", "required")}
            if added and equal_existing and common_before == common_after and old_required == new_required:
                return EvolutionAssessment("OPTIONAL_FIELD_ADDED_STRICT_CONSUMER_BREAK", True, False, True, consumers)
            if common_before == common_after and old_props == new_props and new_required > old_required:
                return EvolutionAssessment("REQUIRED_FIELD_ADDED", False, True, True, consumers)
    return EvolutionAssessment("REVIEW_REQUIRED", None, None, True, consumers)
