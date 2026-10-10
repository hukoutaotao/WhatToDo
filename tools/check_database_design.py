"""Check the draft relational design; this does not parse or execute PostgreSQL.

The guardrails below are independently stated contract requirements, not inferred
from generated SQL. Database/application acceptance remains a separate gate.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.validate_task_core import load_json

DESIGN = ROOT / "database/design/relational.json"
OWNERSHIP = ROOT / "database/design/ownership.json"
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
BASE_TYPES = {"text", "bigint", "numeric", "jsonb", "timestamptz", "date", "boolean", "smallint"}
MUTABLE = {"store_epoch", "task_head", "generation_occurrence", "outbox_entry", "collector_checkpoint"}


def expression_ok(value):
    # Local checked-in expression DSL only; not a general SQL parser/sandbox.
    return isinstance(value, str) and bool(value.strip()) and not any(
        token in value for token in (";", "--", "/*", "*/", "\x00")
    ) and not re.search(r"\$[a-zA-Z_0-9]*\$", value) and not re.search(r"\b(select|insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", value, re.I)


def validate_design(model):
    errors = []
    def need(condition, code):
        if not condition:
            errors.append(code)
    if not isinstance(model, dict):
        return ["model.object"]
    need(model.get("schema") == "whattodo", "model.schema")
    need(model.get("design_version") == "0.1.0-draft", "model.version")
    need(model.get("evidence_level") == "DRAFT_NOT_RELEASE_FROZEN", "model.evidence")
    domains, tables = model.get("domains"), model.get("tables")
    if not isinstance(domains, list) or not isinstance(tables, list) or not tables:
        return errors + ["model.collections"]
    domain_names = set()
    for domain in domains:
        if not isinstance(domain, dict):
            errors.append("domain.object"); continue
        name = domain.get("name")
        need(isinstance(name, str) and bool(IDENTIFIER.fullmatch(name)), "domain.identifier")
        need(isinstance(name, str) and name not in domain_names, "domain.unique")
        if isinstance(name, str): domain_names.add(name)
        need(domain.get("type") in BASE_TYPES, "domain.type")
        need(expression_ok(domain.get("check")), "domain.expression")
    table_map = {}
    for table in tables:
        if not isinstance(table, dict):
            errors.append("table.object"); continue
        name = table.get("name")
        need(isinstance(name, str) and bool(IDENTIFIER.fullmatch(name)), "table.identifier")
        need(isinstance(name, str) and name not in table_map, "table.unique")
        if isinstance(name, str): table_map[name] = table
        need(type(table.get("batch")) is int and 1 <= table["batch"] <= 5, "table.batch")
        need(type(table.get("immutable")) is bool, "table.immutability")
        columns = table.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append("table.columns"); continue
        cmap = {}
        for column in columns:
            if not isinstance(column, dict):
                errors.append("column.object"); continue
            cname = column.get("name")
            need(isinstance(cname, str) and bool(IDENTIFIER.fullmatch(cname)), "column.identifier")
            need(isinstance(cname, str) and cname not in cmap, "column.unique")
            if isinstance(cname, str): cmap[cname] = column
            need(column.get("type") in BASE_TYPES | {"whattodo." + d for d in domain_names}, "column.type")
            need(type(column.get("nullable")) is bool, "column.nullability")
        def key_ok(key):
            return isinstance(key, list) and bool(key) and all(isinstance(c, str) and c in cmap for c in key) and len(key) == len(set(key))
        primary = table.get("primary_key")
        need(key_ok(primary), "table.primary_key")
        if key_ok(primary):
            need(all(cmap[c].get("nullable") is False for c in primary), "table.primary_not_null")
        unique, checks, fks = table.get("unique"), table.get("checks"), table.get("foreign_keys")
        if not all(isinstance(x, list) for x in (unique, checks, fks)):
            errors.append("table.constraints"); continue
        need(all(key_ok(key) for key in unique), "table.unique_key")
        if all(key_ok(key) for key in unique):
            need(len({tuple(key) for key in unique}) == len(unique), "table.duplicate_unique")
        cnames = set()
        for check in checks:
            if not isinstance(check, dict): errors.append("check.object"); continue
            cname = check.get("name")
            need(isinstance(cname, str) and bool(IDENTIFIER.fullmatch(cname)) and cname not in cnames, "check.identifier")
            if isinstance(cname, str): cnames.add(cname)
            need(expression_ok(check.get("expression")), "check.expression")
        for fk in fks:
            if not isinstance(fk, dict): errors.append("foreign_key.object"); continue
            need(key_ok(fk.get("columns")), "foreign_key.columns")
            need(isinstance(fk.get("target"), str), "foreign_key.target")
            need(isinstance(fk.get("target_columns"), list) and all(isinstance(x, str) for x in fk["target_columns"]), "foreign_key.target_columns")
            need(fk.get("deferrable") is True, "foreign_key.deferred")
    if errors:
        return sorted(set(errors))
    for table in tables:
        cmap = {c["name"]: c for c in table["columns"]}
        for fk in table["foreign_keys"]:
            target = table_map.get(fk["target"])
            need(target is not None, "foreign_key.missing_target")
            if target is None: continue
            tmap = {c["name"]: c for c in target["columns"]}
            need(len(fk["columns"]) == len(fk["target_columns"]), "foreign_key.arity")
            need(all(c in tmap for c in fk["target_columns"]), "foreign_key.missing_column")
            need(fk["target_columns"] in [target["primary_key"], *target["unique"]], "foreign_key.target_unique")
            if len(fk["columns"]) == len(fk["target_columns"]) and all(c in tmap for c in fk["target_columns"]):
                need(all(cmap[a]["type"] == tmap[b]["type"] for a, b in zip(fk["columns"], fk["target_columns"])), "foreign_key.type")
    if errors: return sorted(set(errors))
    # Critical semantics. Additions are allowed; required scopes cannot narrow.
    def has_unique(table, key):
        return table in table_map and key in [table_map[table]["primary_key"], *table_map[table]["unique"]]
    def has_fk(table, columns, target, target_columns):
        return table in table_map and any(f["columns"] == columns and f["target"] == target and f["target_columns"] == target_columns for f in table_map[table]["foreign_keys"])
    def has_check(table, name, fragments):
        checks = {c["name"]: c["expression"] for c in table_map.get(table, {}).get("checks", [])}
        return name in checks and all(fragment in checks[name] for fragment in fragments)
    required_unique = {
        "source_identity": ["provider", "scope_ref", "external_id"],
        "source_record": ["source_id", "content_hash", "external_revision"],
        "generation_occurrence": ["rule_id", "source_task_id", "occurrence_key", "target_role"],
        "command_transaction": ["request_id", "audit_id"],
        "audit_entry": ["request_id", "audit_id"],
        "model_lifecycle_event": ["model_id", "model_version", "sequence"],
        "source_lifecycle_event": ["record_id", "sequence"],
        "ai_job_event": ["job_id", "job_revision", "sequence"],
        "ai_import_record": ["job_id", "result_id"],
        "outbox_entry": ["idempotency_key"],
    }
    for table, key in required_unique.items():
        need(has_unique(table, key), "semantic.identity." + table)
    bindings = [
        ("task_details_revision", ["task_id", "task_revision", "completion"], "task_revision", ["task_id", "revision", "completion"]),
        ("task_details_revision", ["release_source_record_ref"], "source_record", ["record_id"]),
        ("task_details_revision", ["total_source_record_ref"], "source_record", ["record_id"]),
        ("task_details_revision", ["total_definition_kind", "total_definition_id", "total_definition_version"], "configuration_revision", ["kind", "id", "version"]),
        ("task_field_provenance", ["task_id", "task_revision"], "task_revision", ["task_id", "revision"]),
        ("task_field_provenance", ["source_record_ref"], "source_record", ["record_id"]),
        ("command_transaction", ["request_id", "audit_id"], "audit_entry", ["request_id", "audit_id"]),
        ("audit_entry", ["request_id", "audit_id"], "command_transaction", ["request_id", "audit_id"]),
        ("audit_change", ["audit_id", "request_id"], "audit_entry", ["audit_id", "request_id"]),
        ("task_revision", ["task_id", "estimate_observation_id", "estimate_kind", "user_remaining_seconds"], "effort_observation", ["task_id", "observation_id", "kind", "seconds"]),
        ("estimate_verification", ["task_id", "observation_id", "observation_kind"], "effort_observation", ["task_id", "observation_id", "kind"]),
        ("estimate_verification", ["review_id", "frame_revision", "member_kind", "task_id", "task_revision", "observation_id"], "review_member", ["review_id", "frame_revision", "member_kind", "member_id", "member_revision", "estimate_observation_ref"]),
        ("task_head", ["task_id", "revision", "transaction_ref"], "task_revision", ["task_id", "revision", "transaction_ref"]),
        ("store_epoch", ["last_transaction_ref", "revision"], "command_transaction", ["request_id", "committed_store_revision"]),
        ("task_revision", ["expiration_notice_ref", "task_id", "notice_task_revision", "expiration_condition_ref"], "expiration_notice", ["notice_id", "task_id", "task_revision", "condition_ref"]),
        ("forecast_horizon", ["snapshot_id", "snapshot_at"], "planning_snapshot", ["snapshot_id", "captured_at"]),
        ("dispatch_result", ["notice_id", "attempt_id", "started_at"], "dispatch_attempt", ["notice_id", "attempt_id", "started_at"]),
        ("numeric_eligibility", ["model_state_event_ref", "model_id", "model_version", "model_state"], "model_lifecycle_event", ["event_id", "model_id", "model_version", "state"]),
        ("remaining_prediction", ["eligibility_ref", "task_id", "task_revision", "model_id", "model_version", "context_hash", "snapshot_ref"], "numeric_eligibility", ["eligibility_ref", "task_id", "task_revision", "model_id", "model_version", "context_hash", "snapshot_ref"]),
        ("remaining_prediction", ["job_id", "job_revision", "result_id", "result_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind"], "ai_result", ["job_id", "job_revision", "result_id", "content_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind"]),
        ("remaining_prediction", ["job_id", "job_revision", "context_hash", "snapshot_ref", "output_contract_ref", "kind"], "ai_job_revision", ["job_id", "revision", "context_hash", "snapshot_ref", "output_contract_ref", "expected_kind"]),
    ]
    for table, columns, target, tcolumns in bindings:
        need(has_fk(table, columns, target, tcolumns), "semantic.binding." + table)
    for table, ident in [("task_revision", "task_id"), ("generation_occurrence", "generation_key"), ("outbox_entry", "outbox_id"), ("collector_checkpoint", "aggregate_key")]:
        need(has_fk(table, ["audit_change_ref", "aggregate_kind", ident, "revision", "transaction_ref"], "audit_change", ["change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id"]), "semantic.audit." + table)
    for table in ("remaining_prediction", "numeric_eligibility", "ai_result", "behavior_candidate"):
        need(table in table_map and not any(c["name"] == "user_remaining_seconds" for c in table_map[table]["columns"]), "semantic.derived_not_u." + table)
    need(table_map.get("source_record", {}).get("nulls_not_distinct") is True, "semantic.source_null_identity")
    need(has_check("task_revision", "complete_zero", ["IS NOT NULL", "= 0"]), "semantic.complete_u")
    need(has_check("task_revision", "title_length", ["500", "char_length"]), "semantic.task_title_width")
    need(has_check("task_details_revision", "release_pair", ["IS NULL", "IS NOT NULL", "release_source_record_ref"]), "semantic.release_binding")
    need(has_check("task_details_revision", "total_binding", ["total_estimate_seconds IS NULL", "total_basis IS NOT NULL", "USER_REPORT", "TEMPLATE_DEFAULT", "total_definition_version IS NOT NULL"]), "semantic.total_estimate_binding")
    need(has_check("task_details_revision", "minimum_session", ["IS NULL", "> 0"]), "semantic.session_unknown_positive")
    need(has_check("task_details_revision", "current_completion_time", ["IS NULL", "COMPLETE"]), "semantic.current_completion_time")
    need(has_check("task_revision", "estimate_binding", ["USER_REMAINING", "IS NULL", "IS NOT NULL"]), "semantic.estimate_known_unknown")
    need(has_check("forecast_horizon", "safe_proof", ["FEASIBLE", "IS NOT NULL", "reserve_seconds"]), "semantic.safe_proof")
    need(has_check("plan_allocation", "session_mode", ["'CONTINUOUS'", "'FRAGMENTABLE'", "'EITHER'"]), "semantic.work_styles")
    need(has_check("behavior_candidate", "pending", ["= 'PENDING'"]), "semantic.policy_pending")
    need(has_check("ai_result", "resolved_scope", ["resolved_job_id IS NULL", "resolved_job_revision IS NULL"]), "semantic.rejected_result_history")
    stage = table_map.get("stage_revision", {})
    need(not any(c["name"] == "complete_zero" for c in stage.get("checks", [])), "semantic.stage_not_parent_u")
    need({c["name"] for c in stage.get("columns", [])} >= {"weight_numerator", "weight_denominator"}, "semantic.exact_stage_fraction")
    need(table_map.get("schema_migration", {}).get("batch") == 1, "semantic.migration_bootstrap")
    domain_map = {d["name"]: d for d in domains}
    for name in ("measure", "seconds", "positive_integer"):
        need(name in domain_map and all(v in domain_map[name]["check"] for v in ("NaN", "Infinity", "-Infinity")), "semantic.finite_numeric")
    for name in ("instant", "calendar_date"):
        need(name in domain_map and domain_map[name]["check"] == "isfinite(VALUE)", "semantic.finite_time")
    guards = model.get("mutable_guards")
    need(isinstance(guards, dict) and set(guards) == MUTABLE, "guard.owners")
    need({t["name"] for t in tables if not t["immutable"]} == MUTABLE, "guard.mutable_scope")
    if isinstance(guards, dict):
        for name, guard in guards.items():
            table = table_map.get(name)
            if not isinstance(guard, dict) or table is None:
                errors.append("guard.object"); continue
            preserve, conditions = guard.get("preserve"), guard.get("conditions")
            cmap = {c["name"] for c in table["columns"]}
            need(isinstance(preserve, list) and all(isinstance(c, str) and c in cmap for c in preserve) and set(preserve) >= set(table["primary_key"]), "guard.identity")
            need(isinstance(conditions, list) and all(expression_ok(c) for c in conditions), "guard.condition")
            need(any(c["name"] == "revision" and c["type"] == "whattodo.revision" and c["nullable"] is False for c in table["columns"]), "guard.revision")
            if name in ("generation_occurrence", "outbox_entry"):
                terminal = "CREATED" if name == "generation_occurrence" else "DELIVERED"
                need(isinstance(conditions, list) and any("OLD.state" in c and terminal in c for c in conditions), "guard.terminal")
    for table in tables:
        if table["name"] not in MUTABLE: need(table["immutable"], "semantic.append_only")
    indexes = model.get("partial_unique_indexes")
    need(isinstance(indexes, list), "index.collection")
    if isinstance(indexes, list):
        names = set()
        for index in indexes:
            if not isinstance(index, dict): errors.append("index.object"); continue
            name = index.get("name"); table = table_map.get(index.get("table"))
            need(isinstance(name, str) and bool(IDENTIFIER.fullmatch(name)) and name not in names, "index.identifier")
            if isinstance(name, str): names.add(name)
            need(table is not None and isinstance(index.get("columns"), list) and bool(index["columns"]) and all(c in {x["name"] for x in table["columns"]} for c in index["columns"]), "index.columns")
            need(expression_ok(index.get("predicate")), "index.expression")
        need(any(i.get("table") == "dispatch_result" and i.get("columns") == ["notice_id", "attempt_id"] and i.get("predicate") == "state IN ('DELIVERED','FAILED')" for i in indexes if isinstance(i, dict)), "semantic.one_terminal_delivery")
    return sorted(set(errors))


def validate_ownership(manifest, model):
    if validate_design(model): return ["ownership.invalid_model"]
    errors = []
    if not isinstance(manifest, dict): return ["ownership.object"]
    if manifest.get("runtime_version") is not None or manifest.get("status") != "DRAFT_NOT_APPLICATION_MIGRATED":
        errors.append("ownership.evidence")
    tables = {t["name"]: t for t in model["tables"]}
    owners = manifest.get("tables", [])
    if not isinstance(owners, list) or len(owners) != len(tables) or {t.get("name") for t in owners} != set(tables):
        return errors + ["ownership.tables"]
    for owner in owners:
        if owner.get("primary_key") != tables[owner["name"]]["primary_key"] or not owner.get("ownership") or not owner.get("requirements"):
            errors.append("ownership.table_scope")
    batches = manifest.get("migration_batches", [])
    if not isinstance(batches, list) or [b.get("id") for b in batches] != [f"{n:03d}" for n in range(1, 6)]:
        return errors + ["ownership.batches"]
    for n, batch in enumerate(batches, 1):
        if batch.get("tables") != [t["name"] for t in model["tables"] if t["batch"] == n] or batch.get("status") != "DRAFT_NOT_APPLIED":
            errors.append("ownership.batch_scope")
    contracts = manifest.get("contract_ownership", [])
    expected = {p.name.removesuffix(".schema.json") for directory in (ROOT / "formats/input", ROOT / "formats/output") for p in directory.glob("*.schema.json")}
    if not isinstance(contracts, list) or len(contracts) != len(expected) or {c.get("contract") for c in contracts} != expected:
        errors.append("ownership.contracts")
    elif any(not c.get("tables") or not set(c["tables"]) <= tables.keys() for c in contracts):
        errors.append("ownership.contract_target")
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, default=DESIGN)
    parser.add_argument("--ownership", type=Path, default=OWNERSHIP)
    args = parser.parse_args()
    try:
        model = load_json(args.design)
        errors = validate_design(model)
        if not errors: errors += validate_ownership(load_json(args.ownership), model)
    except (ValueError, OSError, TypeError):
        print("Invalid design/ownership input", file=sys.stderr); return 1
    if errors:
        print("\n".join(errors), file=sys.stderr); return 1
    count = len(load_json(args.ownership)["contract_ownership"])
    print(f"Draft design checks passed: {len(model['tables'])} tables, {sum(len(t['foreign_keys']) for t in model['tables'])} foreign keys, {count} contracts; this check does not execute PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
