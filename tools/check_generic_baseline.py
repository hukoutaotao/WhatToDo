"""Check pinned generic development inputs; never certifies real activation."""
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.check_contract_registry import REGISTRY, validate_registry
from tools.check_contracts import SCHEMAS
from tools.check_database_design import DESIGN, OWNERSHIP, validate_design, validate_ownership
from tools.validate_task_core import load_json

BASELINE = ROOT / "formats/generic-baseline.json"


def text_hash(path):
    # Same normalization used by native migration hashes; portable across Git
    # CRLF/LF checkouts, while all substantive source changes invalidate it.
    return sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def validate_baseline(baseline):
    errors = []
    if not isinstance(baseline,dict): return ["BASELINE_OBJECT_REQUIRED"]
    if baseline.get("baseline_id") != "m2-generic-0.1.0" or baseline.get("scope") != "GENERIC_DEVELOPMENT_ONLY" or baseline.get("status") != "PINNED_FOR_M3_FOUNDATION":
        errors.append("BASELINE_SCOPE")
    if baseline.get("real_activation") != "DEFERRED_REQUIRES_ACTUAL_REVIEW_AUTHORITY_ACCESS": errors.append("BASELINE_ACTIVATION_SCOPE")
    pins = baseline.get("artifacts")
    if not isinstance(pins,list) or not all(isinstance(p,dict) and set(p)=={"path","sha256"} and isinstance(p["path"],str) and isinstance(p["sha256"],str) for p in pins):
        return errors+["BASELINE_PINS_REQUIRED"]
    if len({p["path"] for p in pins})!=len(pins): errors.append("BASELINE_DUPLICATE_PIN")
    required = {p.relative_to(ROOT).as_posix() for p in SCHEMAS.values()} | {"formats/contract-registry.json","database/design/relational.json","database/design/ownership.json","requirements-toolchain.lock","requirements-toolchain.txt","toolchain/manifest.json","src/application/ports.py","src/domain/task_aggregate.py","src/application/task_aggregate.py","reports/acceptance/M2-01b.json"}
    required |= {p.relative_to(ROOT).as_posix() for p in (ROOT/"database/migrations").glob("*.sql")}
    if not required <= {p["path"] for p in pins}: errors.append("BASELINE_OWNERSHIP_GAP")
    for pin in pins:
        target=(ROOT/pin["path"]).resolve()
        if not target.is_relative_to(ROOT): errors.append("BASELINE_PATH_SCOPE");continue
        try:
            if text_hash(target)!=pin["sha256"]: errors.append("BASELINE_ARTIFACT_DRIFT")
        except (OSError,UnicodeError): errors.append("BASELINE_ARTIFACT_UNREADABLE")
    try:
        registry=load_json(REGISTRY);model=load_json(DESIGN);owner=load_json(OWNERSHIP)
        errors.extend(validate_registry(registry));errors.extend(validate_design(model));errors.extend(validate_ownership(owner,model))
        report=load_json(ROOT/"reports/acceptance/M2-01b.json")
        if report.get("status")!="PASS" or report.get("server_stopped") is not True or report.get("native_tables")!=len(model["tables"]) or report.get("native_foreign_keys")!=sum(len(t["foreign_keys"]) for t in model["tables"]): errors.append("BASELINE_NATIVE_SCOPE")
        for migration in report["migrations"]:
            if text_hash(ROOT/"database/migrations"/migration["file"])!=migration["sha256"]: errors.append("BASELINE_NATIVE_MIGRATION_DRIFT")
        covered={m["file"] for m in report["migrations"]}
        if covered!={p.name for p in (ROOT/"database/migrations").glob("*.sql")}: errors.append("BASELINE_NATIVE_MIGRATION_COVERAGE")
    except (ValueError,OSError,KeyError,TypeError): errors.append("BASELINE_EVIDENCE_UNREADABLE")
    return sorted(set(errors))


def main():
    try: errors=validate_baseline(load_json(BASELINE))
    except (ValueError,OSError,UnicodeError): errors=["BASELINE_UNREADABLE"]
    if errors:
        print("\n".join(errors),file=sys.stderr);return 1
    print("Generic baseline pinned: 30 wire contracts / 51 tables / 130 FKs; M3 foundation may proceed; real activation remains deferred")
    return 0


if __name__=="__main__":raise SystemExit(main())
