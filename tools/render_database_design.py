"""Deterministically render draft PostgreSQL migrations; never connect/apply SQL."""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.check_database_design import DESIGN, OWNERSHIP, validate_design, validate_ownership
from tools.validate_task_core import load_json

MIGRATIONS = ROOT / "database/migrations"


def ident(value):
    return '"' + value + '"'


def qualified(name):
    return '"whattodo".' + ident(name)


def names(columns):
    return ", ".join(ident(c) for c in columns)


def constraint_name(table, kind, suffix):
    value = f"{table}_{kind}_{suffix}"
    return value if len(value) <= 63 else value[:50] + "_" + sha256(value.encode()).hexdigest()[:12]


def render_migrations(model, manifest):
    errors = validate_design(model) + validate_ownership(manifest, model)
    if errors: raise ValueError("Invalid draft model: " + ", ".join(errors))
    table_map = {t["name"]: t for t in model["tables"]}
    result = {}
    for number, batch in enumerate(manifest["migration_batches"], 1):
        lines = ["-- Generated draft 0.1.0: NOT release-frozen or application-migrated.",
                 "-- Review/freeze and run in an isolated database before activation.", "BEGIN;", "SET LOCAL search_path = pg_catalog;", ""]
        if number == 1:
            lines += ['CREATE SCHEMA "whattodo";', 'REVOKE ALL ON SCHEMA "whattodo" FROM PUBLIC;', ""]
            for domain in model["domains"]:
                lines += [f"CREATE DOMAIN {qualified(domain['name'])} AS {domain['type']} CHECK ({domain['check']});"]
            lines += ["", f"CREATE FUNCTION {qualified('reject_history_mutation')}() RETURNS trigger",
                      "LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$", "BEGIN",
                      "  RAISE EXCEPTION 'Historical rows cannot be updated, deleted or truncated' USING ERRCODE = '23514';",
                      "END;", "$guard$;", f"REVOKE ALL ON FUNCTION {qualified('reject_history_mutation')}() FROM PUBLIC;", ""]
        for table in model["tables"]:
            if table["batch"] != number: continue
            name = table["name"]
            columns = []
            for c in table["columns"]:
                typ = qualified(c["type"].split(".")[1]) if c["type"].startswith("whattodo.") else c["type"]
                columns.append(f"  {ident(c['name'])} {typ}" + ("" if c["nullable"] else " NOT NULL"))
            columns.append(f"  CONSTRAINT {ident(constraint_name(name, 'pk', 'identity'))} PRIMARY KEY ({names(table['primary_key'])})")
            for i, key in enumerate(table["unique"], 1):
                mode = " NULLS NOT DISTINCT" if table.get("nulls_not_distinct") else ""
                columns.append(f"  CONSTRAINT {ident(constraint_name(name, 'uq', str(i)))} UNIQUE{mode} ({names(key)})")
            for check in table["checks"]:
                columns.append(f"  CONSTRAINT {ident(constraint_name(name, 'ck', check['name']))} CHECK ({check['expression']})")
            lines += [f"CREATE TABLE {qualified(name)} (", ",\n".join(columns), ");", ""]
            if table["immutable"]:
                lines += [f"CREATE TRIGGER {ident('preserve_history')} BEFORE UPDATE OR DELETE OR TRUNCATE ON {qualified(name)}",
                          f"  FOR EACH STATEMENT EXECUTE FUNCTION {qualified('reject_history_mutation')}();", ""]
            else:
                guard = model["mutable_guards"][name]
                fn = qualified("guard_" + name)
                invalid = [f"NEW.{ident(c)} IS DISTINCT FROM OLD.{ident(c)}" for c in guard["preserve"]]
                invalid += ['NEW."revision" IS DISTINCT FROM OLD."revision" + 1']
                if "transaction_ref" in {c["name"] for c in table["columns"]}:
                    invalid += ['NEW."transaction_ref" IS NOT DISTINCT FROM OLD."transaction_ref"']
                invalid += [f"({condition}) IS NOT TRUE" for condition in guard["conditions"]]
                lines += [f"CREATE FUNCTION {fn}() RETURNS trigger", "LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$", "BEGIN",
                          "  IF " + " OR\n     ".join(invalid) + " THEN",
                          "    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';",
                          "  END IF;", "  RETURN NEW;", "END;", "$guard$;", f"REVOKE ALL ON FUNCTION {fn}() FROM PUBLIC;",
                          f"CREATE TRIGGER {ident('guard_version')} BEFORE UPDATE ON {qualified(name)} FOR EACH ROW EXECUTE FUNCTION {fn}();",
                          f"CREATE TRIGGER {ident('preserve_row')} BEFORE DELETE OR TRUNCATE ON {qualified(name)} FOR EACH STATEMENT EXECUTE FUNCTION {qualified('reject_history_mutation')}();", ""]
        # Foreign keys are added only once both tables have been created. This
        # handles task->notice->task and receipt<->audit without orphan windows
        # in the final schema; no adapter may activate an intermediate batch.
        for table in model["tables"]:
            for i, fk in enumerate(table["foreign_keys"], 1):
                if max(table["batch"], table_map[fk["target"]]["batch"]) != number: continue
                cname = constraint_name(table["name"], "fk", str(i))
                lines += [f"ALTER TABLE {qualified(table['name'])} ADD CONSTRAINT {ident(cname)}",
                          f"  FOREIGN KEY ({names(fk['columns'])}) REFERENCES {qualified(fk['target'])} ({names(fk['target_columns'])})",
                          "  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;", ""]
        for index in model["partial_unique_indexes"]:
            if table_map[index["table"]]["batch"] == number:
                lines += [f"CREATE UNIQUE INDEX {ident(index['name'])} ON {qualified(index['table'])} ({names(index['columns'])}) WHERE {index['predicate']};", ""]
        if number == 1:
            lines += [f"INSERT INTO {qualified('store_epoch')} ({names(['singleton', 'revision', 'last_transaction_ref'])}) VALUES (TRUE, 1, NULL);", ""]
        lines += ['REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;', "COMMIT;", ""]
        result[batch["filename"]] = "\n".join(lines)
    return result


def check_files(rendered, directory=MIGRATIONS):
    return [name for name, text in rendered.items() if not (directory / name).is_file() or (directory / name).read_text(encoding="utf-8") != text] + [p.name for p in directory.glob("*.sql") if p.name not in rendered]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on drift without writing files")
    args = parser.parse_args()
    try:
        rendered = render_migrations(load_json(DESIGN), load_json(OWNERSHIP))
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr); return 1
    if args.check:
        if check_files(rendered):
            print("Draft SQL differs from its checked-in relational design", file=sys.stderr); return 1
    else:
        # Rendering is explicit and never applies SQL or rewrites ownership.
        MIGRATIONS.mkdir(parents=True, exist_ok=True)
        for name, text in rendered.items():
            (MIGRATIONS / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(rendered)} draft SQL batches {'match' if args.check else 'rendered'}; render/check does not execute PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
