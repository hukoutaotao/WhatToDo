"""Run the Windows toolchain spike against a new isolated synthetic PG cluster.

This is a development harness, not an application migration/state-store adapter.
Every native run owns its new local data directory and stops its server finally.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tools.validate_task_core import load_json


class SpikeFailure(RuntimeError):
    pass


def execute(argv, *, timeout=60, cwd=ROOT, output_path=None):
    options = dict(cwd=cwd, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if output_path is None:
        process = subprocess.run([str(x) for x in argv], capture_output=True, **options)
        output, diagnostic = process.stdout, process.stderr
    else:
        # pg_ctl's child server can inherit a pipe handle on Windows. Wait for
        # pg_ctl itself, not for EOF from that long-lived inherited handle.
        with Path(output_path).open("w", encoding="utf-8") as stream:
            process = subprocess.run([str(x) for x in argv], stdout=stream, stderr=subprocess.STDOUT, **options)
        output = diagnostic = Path(output_path).read_text(encoding="utf-8", errors="replace")
    if process.returncode:
        raise SpikeFailure("Native command failed: " + Path(argv[0]).name + "\n" + diagnostic[-2500:])
    return output.strip()


def require_local_cluster(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / ".local-state/toolchain").resolve()):
        raise SpikeFailure("Cluster directory is outside the owned spike root")
    return path


def verify_server_identity(conn, expected):
    # A reused/racing local port must never direct a probe into another cluster.
    actual = conn.execute("SHOW data_directory").fetchone()[0]
    if Path(actual).resolve() != expected.resolve():
        raise SpikeFailure("Refuse to probe an unrelated PostgreSQL instance")


def native_transactions(conn):
    from psycopg.types.json import Jsonb
    import psycopg
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with conn.transaction():
        conn.execute("INSERT INTO whattodo.source_scope VALUES (%s,%s,%s,%s)", ("spike", "scope", "synthetic", now))
        conn.execute("INSERT INTO whattodo.source_identity VALUES (%s,%s,%s,%s,%s)", ("source", "spike", "scope", "id", "USER"))
        conn.execute("INSERT INTO whattodo.source_record VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", ("record", "source", None, "a" * 64, None, now, "PRESENT", None, "synthetic-raw"))
        conn.execute("INSERT INTO whattodo.authority_record VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", ("authority", "principal", "USER_COMMAND", "record", "b" * 64, Jsonb({"synthetic": True}), now, None))

    def write(request, old_revision, *, omit_audit=False):
        audit = "audit-" + request
        conn.execute("INSERT INTO whattodo.command_transaction VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (request, "c" * 64, "principal", "USER_COMMAND", "authority", old_revision, old_revision + 1, audit, now, Jsonb({"synthetic_request": request})))
        if not omit_audit:
            conn.execute("INSERT INTO whattodo.audit_entry VALUES (%s,%s,%s,%s,%s)", (audit, request, "record", "correlation", now))
            conn.execute("INSERT INTO whattodo.audit_change VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", ("change-" + request, audit, "SPIKE", "state", old_revision, old_revision + 1, Jsonb({"revision": old_revision}), Jsonb({"revision": old_revision + 1}), request))
        cur = conn.execute("UPDATE whattodo.store_epoch SET revision = %s, last_transaction_ref = %s WHERE singleton = TRUE AND revision = %s", (old_revision + 1, request, old_revision))
        if cur.rowcount != 1:
            raise SpikeFailure("Synthetic CAS conflict")

    with conn.transaction(): write("committed", 1)
    if conn.execute("SELECT revision FROM whattodo.store_epoch").fetchone()[0] != 2:
        raise SpikeFailure("Atomic commit did not publish its state")
    checks = ["state_audit_receipt_commit"]
    try:
        with conn.transaction():
            write("rolled-back", 2)
            raise SpikeFailure("injected rollback")
    except SpikeFailure as error:
        if str(error) != "injected rollback": raise
    for relation, column in (("command_transaction", "request_id"), ("audit_entry", "request_id"), ("audit_change", "request_id")):
        # Relation/column identifiers are fixed harness literals, never user data.
        if conn.execute(f"SELECT count(*) FROM whattodo.{relation} WHERE {column} = %s", ("rolled-back",)).fetchone()[0]:
            raise SpikeFailure("Rollback left partial state/history")
    if conn.execute("SELECT revision FROM whattodo.store_epoch").fetchone()[0] != 2:
        raise SpikeFailure("Rollback left the new epoch")
    checks.append("state_audit_receipt_rollback")
    try:
        with conn.transaction(): write("missing-audit", 2, omit_audit=True)
    except psycopg.errors.ForeignKeyViolation:
        checks.append("deferred_receipt_audit_pair_rejects_orphan")
    else: raise SpikeFailure("Missing deferred audit was accepted")
    if conn.execute("SELECT count(*) FROM whattodo.command_transaction WHERE request_id = %s", ("missing-audit",)).fetchone()[0]:
        raise SpikeFailure("Deferred FK failure left a receipt")
    try:
        with conn.transaction(): write("committed", 2)
    except psycopg.errors.UniqueViolation:
        checks.append("duplicate_request_rejected")
    else: raise SpikeFailure("Duplicate request identity was accepted")
    cur = conn.execute("UPDATE whattodo.store_epoch SET revision = 3, last_transaction_ref = 'committed' WHERE singleton = TRUE AND revision = 1")
    if cur.rowcount != 0: raise SpikeFailure("Stale CAS modified the epoch")
    checks.append("stale_epoch_cas_no_write")
    receipt = conn.execute("SELECT receipt FROM whattodo.command_transaction WHERE request_id = %s", ("committed",)).fetchone()[0]
    if receipt != {"synthetic_request": "committed"}: raise SpikeFailure("Receipt reconciliation changed identity")
    checks.append("committed_receipt_reconciliation")
    return checks


def native_postgresql(binary_root, run_root, report):
    import psycopg
    binary = binary_root.resolve() / "bin"
    cluster = require_local_cluster(run_root / "cluster")
    # Never initialize/reuse a preexisting data directory.
    if cluster.exists(): raise SpikeFailure("Refuse to initialize an existing cluster")
    version = execute([binary / "postgres.exe", "--version"])
    if version != "postgres (PostgreSQL) 18.6": raise SpikeFailure("PostgreSQL runtime does not match the pin")
    report["postgresql_version"] = version
    execute([binary / "initdb.exe", "-D", cluster, "-U", "whattodo_spike", "-A", "trust", "--locale=C", "--encoding=UTF8"], timeout=60)
    # Only loopback listening; a fresh own data directory and identity check
    # are mandatory even when another application races for the ephemeral port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    started = False
    try:
        execute([binary / "pg_ctl.exe", "-D", cluster, "-l", run_root / "postgresql.log", "-w", "-t", "30", "-o", f"-h 127.0.0.1 -p {port} -c max_connections=10", "start"], timeout=45, output_path=run_root / "pg_ctl_start.log")
        started = True
        with psycopg.connect(host="127.0.0.1", port=port, dbname="postgres", user="whattodo_spike", connect_timeout=5, autocommit=True, application_name="WhatToDoToolchainSpike") as conn:
            verify_server_identity(conn, cluster)
            conn.execute("SET statement_timeout = '15s'")
            report["server_version"] = conn.execute("SHOW server_version").fetchone()[0]
            for path in sorted((ROOT / "database/migrations").glob("*.sql")):
                content = path.read_text(encoding="utf-8")
                content_hash = sha256(content.encode()).hexdigest()
                if not content.endswith("COMMIT;\n"): raise SpikeFailure("Migration transaction suffix mismatch")
                # Record this synthetic application in the SAME SQL transaction.
                record = f"INSERT INTO whattodo.schema_migration VALUES ('{path.stem}', '{content_hash}', '0.1.0-draft', CURRENT_TIMESTAMP);\n"
                conn.execute(content.removesuffix("COMMIT;\n") + record + "COMMIT;\n", prepare=False)
                report["migrations"].append({"file": path.name, "sha256": content_hash})
            report["native_tables"] = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'whattodo'").fetchone()[0]
            report["native_foreign_keys"] = conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'whattodo' AND c.contype = 'f'").fetchone()[0]
            model = load_json(ROOT / "database/design/relational.json")
            if report["native_tables"] != len(model["tables"]) or report["native_foreign_keys"] != sum(len(t["foreign_keys"]) for t in model["tables"]): raise SpikeFailure("Native schema count mismatch")
            conn.execute((ROOT / "database/probes/001_foundation.sql").read_text(encoding="utf-8"), prepare=False)
            report["native_checks"].append("foundation_sql_probes")
            report["native_checks"] += native_transactions(conn)
            from tools.native_task_aggregate import verify_task_aggregate
            report["native_checks"] += verify_task_aggregate(conn)
    finally:
        # A failed start may still have created a live postmaster. Its own
        # postmaster.pid is the only identity considered for cleanup.
        if started or (cluster / "postmaster.pid").exists():
            execute([binary / "pg_ctl.exe", "-D", cluster, "-w", "-t", "30", "-m", "fast", "stop"], timeout=45)
        report["server_stopped"] = not (cluster / "postmaster.pid").exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-root", type=Path, default=ROOT / ".dev-tools/postgresql-18.6/pgsql")
    args = parser.parse_args()
    manifest = load_json(ROOT / "toolchain/manifest.json")
    if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
        print("This spike lock targets Windows x64", file=sys.stderr); return 1
    if platform.python_version() != manifest["python_version"]:
        print("Python runtime does not match the spike pin", file=sys.stderr); return 1
    run_root = require_local_cluster(ROOT / ".local-state/toolchain" / uuid4().hex)
    run_root.mkdir(parents=True, exist_ok=False)
    report = {"status": "IN_PROGRESS", "python_version": platform.python_version(), "packages": {}, "migrations": [], "native_checks": [], "server_stopped": None, "limitations": ["Synthetic isolated development spike only", "Not a production migration runner, trusted command handler or full StateStore adapter", "No live channels, personal intake, crash/restore or deployed operating evidence"]}
    try:
        for package in manifest["python_packages"]:
            version = importlib.metadata.version(package["name"])
            if version != package["version"]: raise SpikeFailure("Dependency version mismatch")
            report["packages"][package["name"]] = version
        report["regression_methods"] = unittest.TestLoader().discover(str(ROOT / "tests")).countTestCases()
        for command, args_list in [("database_design", ["tools/check_database_design.py"]), ("sql_drift", ["tools/render_database_design.py", "--check"]), ("regression_suite", ["-m", "unittest", "discover", "-s", "tests", "-q"])]:
            execute([sys.executable, *args_list], timeout=90)
            report[command] = "PASS"
            print(command + " PASS", flush=True)
        native_postgresql(args.postgres_root, run_root, report)
        if not report["server_stopped"]: raise SpikeFailure("Synthetic PostgreSQL instance was not stopped")
        report["status"] = "PASS"
    except Exception as error:
        report["status"] = "FAIL"
        report["failure_type"] = type(error).__name__
        # All SQL/logs in this harness are synthetic; it never reads private data.
        report["diagnostic"] = str(error)[-2500:]
        print(report["diagnostic"], file=sys.stderr)
    finally:
        (run_root / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Toolchain report: " + str(run_root / "report.json"), flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
