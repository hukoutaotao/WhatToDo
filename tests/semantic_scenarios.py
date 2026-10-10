"""Offline composed test scenarios. Expectations live separately in JSON.

Synthetic trusted registries and fixture proofs do not instantiate a production
application, provider, solver or database. Helpers never read expected output.
"""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json

from src.adapters.fakes import FakeClock, FakeNotificationSink, FakeStateStore
from src.application.ports import AggregateKey, CommitRequest, NotificationRequest, PortResult, RecordWrite, RequestContext, StoredRecord, TransactionPermit
from src.domain.authorization import AuthorityGrant, CallerIdentity, Command, CreationRecord, RuleScope, TaskState, authorize, change
from src.domain.effort import RemainingPrediction, UserEstimate, select_budget, sum_obligations
from src.domain.expiration import ConditionEvidence, DispatchAttempt, DispatchResult, begin_dispatch, detect_expiration, reconcile_dispatch, record_dispatch, revalidate_expiration
from src.domain.forecast import PlacementEvidence, RequiredProjection, assess_forecast, forecast_fingerprint, safe_discretionary_budget
from src.domain.provenance import capture_source, make_candidate
from src.domain.relationships import Endpoint, FieldMapping, GenerationOccurrence, RelationshipRule, TaskRelation, check_relationships, literal, resolve_generation
from src.domain.review import EstimateBinding, ReviewFrame, ReviewResponse, ReviewTask, UnchangedBatch, assess_review
from src.domain.time_windows import AvailabilityFrame, Interval, forecast_window, normalize_due, today_lock


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
USER = CallerIdentity("synthetic-user", "USER_COMMAND", True)


def budget(seconds, task_id="synthetic-task", model_seconds=None):
    user = UserEstimate(seconds, "synthetic-estimate-" + task_id, NOW, NOW)
    model = None if model_seconds is None else RemainingPrediction(model_seconds, "synthetic-prediction", "synthetic-model", "v1", 1, NOW, NOW + timedelta(hours=1), True, True)
    return select_budget(task_id=task_id, task_revision=1, snapshot_at=NOW, user_estimate=user, prediction=model)


def forecast(selected, capacity, outcome="FEASIBLE", proof_ref="synthetic-fixture-proof"):
    window = forecast_window(NOW, 1)
    frame = AvailabilityFrame("synthetic-snapshot", NOW, window.cutoff, (Interval(NOW, NOW + timedelta(seconds=capacity)),), (), "READY")
    projections = (RequiredProjection(selected, "REQUIRED", selected.seconds, "FULL_DUE", "synthetic-projection"),)
    key = forecast_fingerprint(window, snapshot_ref=frame.snapshot_ref, availability=frame, projections=projections, hard_constraints_ref=proof_ref)
    evidence = PlacementEvidence(key, "synthetic-reference-oracle", "v1", outcome, NOW, proof_ref)
    return assess_forecast(window, snapshot_ref=frame.snapshot_ref, availability=frame, projections=projections, hard_constraints_ref=proof_ref, placement=evidence, assessed_at=NOW)


def model_forecast(inputs):
    selected = budget(inputs["user_seconds"], model_seconds=inputs["model_seconds"])
    result = forecast(selected, inputs["capacity_seconds"])
    return dict(budget_seconds=selected.seconds, source=selected.source, canonical_user_seconds=selected.user_seconds, risk=result.risk)


def hard_window(inputs):
    # Exact exhaustive single-task grid oracle, independent of forecast logic.
    # Daily usable slots exceed this Task's hard eligibility window.
    length = inputs["required_slots"]
    eligible = frozenset(inputs["eligible_slots"])
    placements = [start for start in range(inputs["day_slots"] - length + 1) if set(range(start, start + length)) <= eligible]
    capacity = inputs["day_slots"] * inputs["slot_seconds"]
    required = length * inputs["slot_seconds"]
    assessment = forecast(budget(required), capacity, "FEASIBLE" if placements else "INFEASIBLE", "synthetic-single-task-exhaustive-grid")
    return dict(candidate_placements=len(placements), capacity_seconds=capacity, required_seconds=required, positive_margin=assessment.margin_seconds > 0, risk=assessment.risk)


def external_authority(inputs):
    task = TaskState("synthetic-task", 1)
    user = UserEstimate(1800, "synthetic-estimate", NOW, NOW)
    source = capture_source(provider="synthetic-platform", scope_ref="synthetic-scope", external_id="synthetic-upload", raw_bytes=b"synthetic completion claim", captured_at=NOW)
    candidate = make_candidate(source, parser_version="v1", action="COMPLETE_TASK", proposed_fields={"completion": inputs["proposed_completion"]}, confidence=inputs["confidence"], target_task_id=task.task_id, target_revision=1)
    command = Command("synthetic-command", "synthetic-external", "EXTERNAL", "synthetic-no-authority", (change(task.task_id, 1, "UPDATE_TASK", candidate.proposed_fields),))
    decision = authorize(command, caller=CallerIdentity("synthetic-external", "EXTERNAL", True), grants={}, tasks={task.task_id: task}, now=NOW)
    return dict(candidate_state=candidate.review_state, authorized=decision.allowed, completion=task.completion, canonical_user_seconds=user.seconds)


def _fake_commit(writes, records, *, at, principal="synthetic-user", origin="USER_COMMAND"):
    context = RequestContext("synthetic-transaction", "synthetic-correlation")
    request = CommitRequest(context, principal, 1, writes, "synthetic-audit", "synthetic-confirmed-statement")
    # Test setup only: no production command-to-permit resolver is claimed.
    permit = TransactionPermit("synthetic-transaction-permit", principal, origin, request.fingerprint, at, at + timedelta(hours=1))
    store = FakeStateStore(clock=FakeClock(at), records=records, permits=(permit,))
    result = store.commit(request, caller=CallerIdentity(principal, origin, True), permit_ref=permit.permit_ref)
    return result, store.snapshot(context).value


def batch_commit(inputs):
    observed_at = NOW - timedelta(days=1)
    original = UserEstimate(inputs["user_seconds"], "synthetic-original-estimate", observed_at, observed_at)
    untouched = ReviewTask(inputs["untouched_id"], 1, 4, "INCOMPLETE", "ACTIVE", True, original, "UNTOUCHED", "CURRENT")
    worked = replace(untouched, task_id=inputs["worked_id"], work_status="WORKED")
    frame = ReviewFrame("synthetic-review", 1, "synthetic-full-queue", NOW, (untouched, worked), ("synthetic-pending-candidate",))
    selected_members = frame.tasks if inputs["include_worked_in_batch"] else (untouched,)
    members = tuple(EstimateBinding(task.task_id, task.revision, original.observation_id, original.seconds) for task in selected_members)
    response = ReviewResponse(frame.review_id, 1, True, "synthetic-user-batch", batches=(UnchangedBatch("synthetic-batch", True, members, True),))
    coverage = assess_review(frame, response, caller=USER, response_at=NOW + timedelta(minutes=1))
    verified = coverage.verifications
    writes = tuple(RecordWrite(AggregateKey("ESTIMATE_VERIFICATION", item.verification_id), None, json.dumps({"task_id": item.task_id, "batch_id": item.batch_id, "observation_id": item.original_estimate.observation_id, "seconds": item.verified_estimate.seconds, "observed_at": item.verified_estimate.observed_at.isoformat(), "verified_at": item.verified_at.isoformat()})) for item in verified)
    seed = StoredRecord(AggregateKey("USER_ESTIMATE", untouched.task_id), 1, json.dumps({"seconds": original.seconds, "observed_at": observed_at.isoformat()}))
    if not verified:
        # An invalid mixed batch is rejected as a whole, never silently narrowed.
        return dict(verified_task_ids=[], responses_complete=coverage.responses_complete, audit_entries=0, canonical_user_seconds=seed.body["seconds"], commit_code="NOT_COMMITTED")
    result, snapshot = _fake_commit(writes, (seed,), at=NOW + timedelta(minutes=1))
    user_record = next(record for record in snapshot.records if record.key == seed.key)
    return dict(verified_task_ids=[item.task_id for item in verified], responses_complete=coverage.responses_complete, audit_entries=len(snapshot.audit), canonical_user_seconds=user_record.body["seconds"], commit_code=result.code)


def generation_order(inputs):
    source, preparation = Endpoint("TASK", "synthetic-source"), Endpoint("TASK", "synthetic-preparation")
    rule = RelationshipRule("synthetic-rule", "v1", True, "synthetic-accepted-rule", "CANONICAL_CREATION", inputs["source_type"], inputs["target_type"], "synthetic-template", "v1", "preparation", "SEPARATE_TASK", ("title", "completion", "disposition", "requiredness"), (FieldMapping("title", "SOURCE", "preparation_title", None), literal("completion", "INCOMPLETE"), literal("disposition", "ACTIVE"), FieldMapping("requiredness", "DEFAULT", "requiredness", None)))
    scope = RuleScope(rule.rule_id, rule.version, source.id, "synthetic-source-created", "synthetic-occurrence", rule.target_role)
    creation = CreationRecord(scope.creation_event_ref, source.id, scope.occurrence_key, True)
    links = (TaskRelation("synthetic-before", 1, "COMPLETION_ORDER", preparation, source, "synthetic-accepted-order"),)
    issues = check_relationships((rule,), links, endpoints=frozenset((source, preparation)))
    options = dict(creation=creation, source_type_ref=inputs["source_type"], source_fields={"preparation_title": "Synthetic preparation"}, template_ref=rule.target_template_ref, template_version=rule.target_template_version, defaults={"requiredness": "REQUIRED"})
    resolution = resolve_generation(rule, scope, occurrences={}, **options)
    changes = (change(preparation.id, None, "CREATE_TASK", resolution.fields),)
    command = Command("synthetic-generate", "synthetic-rule-engine", "RELATIONSHIP_RULE", "synthetic-rule-authority", changes, rule_scope=scope)
    grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, changes, rule.acceptance_ref, NOW, rule_scope=scope, essential_fields=frozenset(rule.essential_fields))
    decision = authorize(command, caller=CallerIdentity(command.principal_id, command.origin, True), grants={grant.grant_id: grant}, tasks={source.id: TaskState(source.id, 1)}, creations={creation.event_id: creation}, now=NOW)
    occurrence = GenerationOccurrence(scope, "SEPARATE_TASK", "CREATED", preparation.id)
    replay = resolve_generation(rule, scope, occurrences={scope.generation_key: occurrence}, **options)
    source_budget, prep_budget = budget(inputs["source_seconds"], source.id), budget(inputs["preparation_seconds"], preparation.id)
    total = sum_obligations((source_budget, prep_budget, prep_budget))
    return dict(graph_issues=len(issues), resolution=resolution.state, authorized=decision.allowed, replay_state=replay.state, total_seconds=total.seconds)


def notice_expiry(inputs):
    task = TaskState("synthetic-preview", 1, "EXPIRING", expiration_condition_ref="synthetic-class-start")
    condition = ConditionEvidence("synthetic-condition-evidence", task.expiration_condition_ref, True, NOW)
    notice = detect_expiration(task, condition, now=NOW).notice
    queued = begin_dispatch(notice, attempt_id="synthetic-attempt", started_at=NOW + timedelta(seconds=1), correlation_ref="synthetic-correlation")
    request = NotificationRequest(RequestContext("synthetic-send", "synthetic-correlation"), notice.notice_id, "synthetic-channel", "synthetic-notice-content", queued.attempts[0])
    first_attempt = replace(request.attempt, state=inputs["initial_dispatch"], finished_at=NOW + timedelta(seconds=2), evidence_ref="synthetic-first-receipt")
    first_result = DispatchResult(notice.notice_id, first_attempt)
    delivered_attempt = replace(request.attempt, state="DELIVERED", finished_at=NOW + timedelta(seconds=5), delivered_at=NOW + timedelta(seconds=4), evidence_ref="synthetic-confirmed-receipt")
    delivered = DispatchResult(notice.notice_id, delivered_attempt)
    sink = FakeNotificationSink(send_replies=((request, PortResult("SUCCESS", "SYNTHETIC_DISPATCH", "synthetic-correlation", first_result)),), reconcile_replies=((request, PortResult("SUCCESS", "SYNTHETIC_RECEIPT", "synthetic-correlation", delivered)),))
    state = record_dispatch(queued, sink.send(request).value)
    before = revalidate_expiration(state, task, condition, checked_at=NOW + timedelta(seconds=3))
    blocked = False
    try:
        retry = begin_dispatch(state, attempt_id="synthetic-retry", started_at=NOW + timedelta(seconds=3))
    except ValueError:
        blocked = True
    if inputs["initial_dispatch"] == "UNKNOWN":
        # Query the original delivery, with no second send or acknowledgement.
        state = reconcile_dispatch(state, sink.reconcile(request).value)
    else:
        retry_attempt = replace(retry.attempts[-1], state="DELIVERED", finished_at=NOW + timedelta(seconds=5), delivered_at=NOW + timedelta(seconds=4), evidence_ref="synthetic-retry-receipt")
        retry_request = NotificationRequest(RequestContext("synthetic-retry-send", "synthetic-correlation"), notice.notice_id, request.channel_ref, request.content_ref, retry.attempts[-1])
        retry_sink = FakeNotificationSink(send_replies=((retry_request, PortResult("SUCCESS", "SYNTHETIC_RETRY_RECEIPT", "synthetic-correlation", DispatchResult(notice.notice_id, retry_attempt))),))
        state = record_dispatch(retry, retry_sink.send(retry_request).value)
    checked_at = NOW + timedelta(seconds=6)
    current_condition = replace(condition, observed_at=checked_at)
    ready = revalidate_expiration(state, task, current_condition, checked_at=checked_at)
    fields = {"disposition": "EXPIRED", "expiration_notice_ref": notice.notice_id}
    changes = (change(task.task_id, task.revision, "EXPIRE_TASK", fields),)
    command = Command("synthetic-expire", "synthetic-expiration-engine", "EXPIRATION_PROCESS", "synthetic-expiration-authority", changes)
    grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, changes, "synthetic-accepted-expiration-policy", NOW)
    decision = authorize(command, caller=CallerIdentity(command.principal_id, command.origin, True), grants={grant.grant_id: grant}, tasks={task.task_id: task}, notices={notice.notice_id: ready.notice_evidence}, now=checked_at)
    seed = StoredRecord(AggregateKey("TASK", task.task_id), task.revision, json.dumps({"completion": task.completion, "disposition": task.disposition, "user_seconds": inputs["user_seconds"]}))
    # Simulate only the exact authorized fields; no effort/completion rewrite.
    body = {**seed.body, **changes[0].fields}
    if not decision.allowed:
        raise ValueError("Scenario did not establish expiry authority")
    _, snapshot = _fake_commit((RecordWrite(seed.key, seed.revision, json.dumps(body)),), (seed,), at=checked_at, principal=command.principal_id, origin=command.origin)
    stored = snapshot.records[0].body
    return dict(ready_before_receipt=before.ready, resend_blocked=blocked, ready_after_receipt=ready.ready, authorized=decision.allowed, disposition=stored["disposition"], completion=stored["completion"], canonical_user_seconds=stored["user_seconds"], audit_entries=len(snapshot.audit))


def rollover(inputs):
    before, after = (datetime.fromisoformat(inputs[key]) for key in ("before", "after"))
    initial = tuple(forecast_window(before, days) for days in (1, 3, 7))
    next_day = tuple(forecast_window(after, days) for days in (1, 3, 7))
    frame = AvailabilityFrame("synthetic-snapshot", before, initial[0].cutoff, (Interval(before, after),), (), "READY")
    lock = today_lock("synthetic-today-lock", "synthetic-task", 1, "ADVANCE", "synthetic-user-lock", created_at=before)
    due = normalize_due(inputs["date_only"], source_ref="synthetic-user-date")
    return dict(before_cutoffs=[window.cutoff.isoformat() for window in initial], after_cutoffs=[window.cutoff.isoformat() for window in next_day], before_capacity_seconds=int(frame.evaluate().seconds), lock_active_before=lock.active_at(before), lock_active_after=lock.active_at(after), date_only_due=due.instant.isoformat())


def safe_gap(inputs):
    values = [safe_discretionary_budget(capacity_seconds=inputs["required_seconds"] + inputs["reserve_seconds"] + gap, required_seconds=inputs["required_seconds"], reserve_seconds=inputs["reserve_seconds"]) for gap in inputs["gap_seconds"]]
    return dict(discretionary_seconds=[int(value) for value in values], fragments_total_seconds=sum(inputs["fragment_seconds"]))


RUNNERS = {"MODEL_FORECAST": model_forecast, "HARD_WINDOW": hard_window, "EXTERNAL_AUTHORITY": external_authority, "BATCH_COMMIT": batch_commit, "GENERATION_ORDER": generation_order, "NOTICE_EXPIRY": notice_expiry, "ROLLOVER": rollover, "SAFE_GAP": safe_gap}


def run_scenario(case):
    return RUNNERS[case["kind"]](case["inputs"])
