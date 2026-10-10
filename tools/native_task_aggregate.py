"""Additional synthetic probes for the isolated toolchain cluster only.

The caller verifies the fresh cluster identity and seeds native_transactions.
No application command authorization or production repository is implemented.
"""
from datetime import datetime, timedelta, timezone


def verify_task_aggregate(conn):
    import psycopg
    from psycopg.types.json import Jsonb
    now = datetime(2026,1,1,tzinfo=timezone.utc)
    checks = []
    with conn.transaction():
        conn.execute("INSERT INTO whattodo.configuration_revision VALUES (%s,%s,%s,%s,%s,%s,%s)",("aggregate-type","TASKTYPE","synthetic-aggregate-type","1","d"*64,"synthetic-git-version",now))
        conn.execute("INSERT INTO whattodo.command_transaction VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",("aggregate-create","e"*64,"principal","USER_COMMAND","authority",2,3,"aggregate-audit",now,Jsonb({"synthetic":True})))
        conn.execute("INSERT INTO whattodo.audit_entry VALUES (%s,%s,%s,%s,%s)",("aggregate-audit","aggregate-create","record","aggregate-correlation",now))
        for task_id, unknown in [("aggregate-unknown",True),("aggregate-known",False),("aggregate-template",False),("aggregate-header-only",False)]:
            conn.execute("INSERT INTO whattodo.task_identity VALUES (%s,%s,%s)",(task_id,"aggregate-create",now))
            if not unknown:
                conn.execute("INSERT INTO whattodo.effort_observation VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",("observation-"+task_id,task_id,"USER_REMAINING",2400,now-timedelta(days=1),now,"record","authority",None,"aggregate-create"))
            conn.execute("INSERT INTO whattodo.audit_change VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",("change-"+task_id,"aggregate-audit","TASK",task_id,None,1,None,Jsonb({"synthetic_task":task_id}),"aggregate-create"))
            conn.execute("""INSERT INTO whattodo.task_revision
                (task_id,revision,title,domain,acceptance_ref,completion,disposition,requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,user_remaining_seconds,estimate_observation_id,estimate_kind,audit_change_ref,aggregate_kind,transaction_ref,metadata)
                VALUES (%s,1,%s,'study','authority','INCOMPLETE','ACTIVE','REQUIRED',4,3,2,2,%s,%s,%s,%s,'TASK','aggregate-create',%s)""",(task_id,"x"*300,None if unknown else 2400,None if unknown else "observation-"+task_id,None if unknown else "USER_REMAINING","change-"+task_id,Jsonb({"trust":"TRUSTED","overdue":"UNKNOWN"})))
            conn.execute("INSERT INTO whattodo.task_head VALUES (%s,1,'aggregate-create')",(task_id,))
        conn.execute("INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion) VALUES ('aggregate-unknown',1,'INCOMPLETE')")
        for task_id,basis in [("aggregate-known","USER_REPORT"),("aggregate-template","TEMPLATE_DEFAULT")]:
            conn.execute("""INSERT INTO whattodo.task_details_revision
                (task_id,task_revision,completion,release_at,release_original,release_source_record_ref,total_estimate_seconds,total_source_record_ref,total_observed_at,total_basis,total_definition_kind,total_definition_id,total_definition_version,minimum_session_seconds,fragmentable)
                VALUES (%s,1,'INCOMPLETE',%s,%s,'record',1800,'record',%s,%s,%s,%s,%s,1200,TRUE)""",(task_id,now,now.isoformat(),now-timedelta(days=1),basis,"TASKTYPE" if basis=="TEMPLATE_DEFAULT" else None,"synthetic-aggregate-type" if basis=="TEMPLATE_DEFAULT" else None,"1" if basis=="TEMPLATE_DEFAULT" else None))
            conn.execute("INSERT INTO whattodo.task_field_provenance VALUES (%s,1,'/core/title','record')",(task_id,))
        result = conn.execute("UPDATE whattodo.store_epoch SET revision=3,last_transaction_ref='aggregate-create' WHERE singleton=TRUE AND revision=2")
        if result.rowcount != 1: raise AssertionError("Aggregate fixture CAS failed")
    row = conn.execute("SELECT created_at,minimum_session_seconds,fragmentable,total_estimate_seconds FROM whattodo.task_details_revision WHERE task_id='aggregate-unknown'").fetchone()
    if row != (None,None,None,None): raise AssertionError("Unknown fields were changed")
    if conn.execute("SELECT title FROM whattodo.task_revision WHERE task_id='aggregate-known'").fetchone()[0] != "x"*300:
        raise AssertionError("Accepted 300-character title was changed")
    checks.append("aggregate_unknown_and_long_title_roundtrip")
    for task_id,basis in [("aggregate-known","USER_REPORT"),("aggregate-template","TEMPLATE_DEFAULT")]:
        row = conn.execute("""SELECT t.user_remaining_seconds,d.total_estimate_seconds,d.total_basis,d.minimum_session_seconds,d.fragmentable
            FROM whattodo.task_revision t JOIN whattodo.task_details_revision d ON (t.task_id,t.revision)=(d.task_id,d.task_revision) WHERE t.task_id=%s""",(task_id,)).fetchone()
        if row != (2400,1800,basis,1200,True): raise AssertionError("Original total changed canonical U")
    checks.append("aggregate_user_and_versioned_template_total_keep_u")

    def expect(name,sql,params,state,constraint=None):
        try:
            with conn.transaction(): conn.execute(sql,params)
        except psycopg.Error as exc:
            if exc.sqlstate != state or (constraint is not None and exc.diag.constraint_name != constraint):
                raise AssertionError("Unexpected native aggregate rejection") from exc
        else: raise AssertionError("Expected native aggregate rejection: "+name)
        checks.append(name)

    expect("aggregate_details_parent_fk", "INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion) VALUES (%s,1,'INCOMPLETE')",("missing-parent",),"23503")
    expect("aggregate_details_completion_fk", "INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion) VALUES ('aggregate-header-only',1,'COMPLETE')",(),"23503")
    expect("aggregate_minimum_session_zero_rejected", "INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion,minimum_session_seconds) VALUES ('aggregate-header-only',1,'INCOMPLETE',0)",(),"23514","task_details_revision_ck_minimum_session")
    expect("aggregate_partial_total_rejected", "INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion,total_estimate_seconds) VALUES ('aggregate-header-only',1,'INCOMPLETE',300)",(),"23514","task_details_revision_ck_total_binding")
    expect("aggregate_unregistered_template_version_rejected", """INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion,total_estimate_seconds,total_source_record_ref,total_observed_at,total_basis,total_definition_kind,total_definition_id,total_definition_version)
        VALUES ('aggregate-header-only',1,'INCOMPLETE',300,'record',%s,'TEMPLATE_DEFAULT','TASKTYPE','synthetic-aggregate-type','missing-version')""",(now,),"23503")
    expect("aggregate_provenance_source_fk", "INSERT INTO whattodo.task_field_provenance VALUES ('aggregate-known',1,'/core/importance','missing-record')",(),"23503")
    expect("aggregate_provenance_revision_fk", "INSERT INTO whattodo.task_field_provenance VALUES ('aggregate-known',99,'/core/importance','record')",(),"23503")
    expect("aggregate_duplicate_field_provenance_rejected", "INSERT INTO whattodo.task_field_provenance VALUES ('aggregate-known',1,'/core/title','record')",(),"23505")
    expect("aggregate_details_history_immutable", "UPDATE whattodo.task_details_revision SET fragmentable=FALSE WHERE task_id='aggregate-known'",(),"23514")
    expect("aggregate_provenance_history_immutable", "DELETE FROM whattodo.task_field_provenance WHERE task_id='aggregate-known'",(),"23514")
    expect("aggregate_title_above_contract_rejected", """INSERT INTO whattodo.task_revision
        (task_id,revision,title,domain,acceptance_ref,completion,disposition,requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,audit_change_ref,aggregate_kind,transaction_ref,metadata)
        VALUES ('missing-title-parent',1,%s,'study','authority','INCOMPLETE','ACTIVE','REQUIRED',4,3,2,2,'missing-change','TASK','aggregate-create',%s)""",("x"*501,Jsonb({})),"23514","task_revision_ck_title_length")
    class InjectedRollback(Exception): pass
    try:
        with conn.transaction():
            conn.execute("INSERT INTO whattodo.task_details_revision(task_id,task_revision,completion) VALUES ('aggregate-header-only',1,'INCOMPLETE')")
            conn.execute("INSERT INTO whattodo.task_field_provenance VALUES ('aggregate-header-only',1,'/core/title','record')")
            raise InjectedRollback()
    except InjectedRollback: pass
    for table in ("task_details_revision","task_field_provenance"):
        if conn.execute("SELECT count(*) FROM whattodo."+table+" WHERE task_id='aggregate-header-only'").fetchone()[0] != 0:
            raise AssertionError("Failed transaction retained partial Task facts")
    checks.append("aggregate_details_provenance_rollback")
    return checks
