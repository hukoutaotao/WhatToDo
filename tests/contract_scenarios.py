"""Five cross-contract offline workflows; expected outcomes live in fixtures.

Independent grants/transaction permits are fixture seeds, not an implemented
authority-to-commit service. Fakes do not prove live/persistent acceptance.
"""
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.fakes import FakeClock, FakeNotificationSink, FakeStateStore
from src.application.guided_review import candidate_reply, prepare_response, present_review, task_reply, unchanged_reply
from src.application.ports import AggregateKey, CommitRequest, NotificationRequest, PortResult, RecordWrite, RequestContext, StoredRecord, TransactionPermit
from src.domain.authorization import AuthorityGrant, CallerIdentity, Command, CreationRecord, RuleScope, TaskState, authorize, change
from src.domain.effort import RemainingPrediction, UserEstimate, select_budget, sum_obligations
from src.domain.expiration import ConditionEvidence, DispatchAttempt, DispatchResult, begin_dispatch, detect_expiration, record_dispatch, revalidate_expiration
from src.domain.forecast import PlacementEvidence, RequiredProjection, assess_forecast, forecast_fingerprint
from src.domain.goals import Cadence, GoalConfig, GoalProgress, GoalTarget, Measure, Milestone, assess_onboarding, measured_target_fraction, validate_milestones
from src.domain.plan_output import PlanItem, PlanSnapshot, PlanTask, WorkAllocation
from src.domain.relationships import Endpoint, GenerationOccurrence, RelationshipRule, TaskRelation, check_relationships, literal, resolve_generation
from src.domain.review import ReviewFrame, ReviewTask, assess_review
from src.domain.time_windows import AvailabilityFrame, Interval, forecast_window, normalize_due, today_lock
from tools.check_contract_registry import trusted_schemas

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
USER = CallerIdentity("synthetic-user", "USER_COMMAND", True)


def encode(record):
    return json.dumps(record, ensure_ascii=False, allow_nan=False).encode()


class Wire:
    def __init__(self):
        self.codec = ContractJSONCodec(trusted_schemas())
        self.contracts = set()
        self.records = 0
        self.tasks = {}; self.efforts = {}

    def check(self, contract, record):
        raw = encode(record)
        result = self.codec.admit(contract, raw)
        if result.status != "SUPPORTED_SHAPE": raise AssertionError(contract + ": " + result.reason + " " + repr(result.issues))
        if result.raw_bytes != raw or result.payload != record: raise AssertionError("Wire roundtrip changed payload")
        self.contracts.add(contract); self.records += 1
        if contract == "task-core": self.tasks[record["task_id"]] = record
        if contract == "effort": self.efforts[record["task_id"]] = record
        return result.payload

    def finish(self, **values):
        for task_id in self.tasks.keys() & self.efforts.keys():
            task, estimate_record = self.tasks[task_id], self.efforts[task_id]
            if (task["revision"], task["completion"], task["disposition"]) != (estimate_record["task_revision"], estimate_record["completion"], estimate_record["disposition"]):
                raise AssertionError("Task/effort snapshot scope mismatch")
        return dict(wire_contracts=sorted(self.contracts), validated_records=self.records, **values)


def estimate(task_id, seconds):
    return UserEstimate(seconds, "observation-" + task_id, NOW - timedelta(days=1), NOW - timedelta(days=1))


def core(task_id, *, title="Synthetic work", authority="synthetic-source", requiredness="REQUIRED", condition=None):
    return dict(schema_version="0.1.0-draft", task_id=task_id, revision=1, title=title, domain="study", context=None, task_type_ref=None, acceptance={"state": "ACCEPTED", "authority_ref": authority}, completion="INCOMPLETE", disposition="ACTIVE", requiredness=requiredness, importance=4, difficulty={"thinking_depth": 3, "repetitive_volume": 2, "new_learning_load": 2}, expiration={"condition_ref": condition, "notice_ref": None} if condition else None, metadata={"trust": "TRUSTED", "overdue": "UNKNOWN"})


def effort(task_id, user):
    u = asdict(user);u["observed_at"] = user.observed_at.isoformat();u["verified_at"] = user.verified_at.isoformat()
    return dict(schema_version="0.1.0-draft", task_id=task_id, task_revision=1, completion="INCOMPLETE", disposition="ACTIVE", user_remaining=u, prediction=None, stages=[])


def fake_write(writes, *, records=(), caller=USER, fault=None, at=NOW):
    context = RequestContext("synthetic-request", "synthetic-correlation")
    request = CommitRequest(context, caller.principal_id, 1, tuple(writes), "synthetic-audit", "synthetic-reviewed-source")
    permit = TransactionPermit("fixture-permit", caller.principal_id, caller.origin, request.fingerprint, at, at + timedelta(hours=2))
    store = FakeStateStore(clock=FakeClock(at), records=tuple(records), permits=(permit,), fault=fault)
    result = store.commit(request, caller=caller, permit_ref=permit.permit_ref)
    return result, store, request, permit


def morning(inputs):
    wire = Wire(); user = estimate("work", inputs["user_seconds"])
    task = wire.check("task-core", core("work")); wire.check("effort", effort("work", user))
    prediction = RemainingPrediction(inputs["model_seconds"], "prediction", "model", "1", 1, NOW, NOW + timedelta(hours=2), True, True)
    budget = select_budget(task_id="work", task_revision=1, snapshot_at=NOW, user_estimate=user, prediction=prediction)
    lock = today_lock("lock", "work", 1, "ADVANCE", "synthetic-today-instruction", created_at=NOW)
    wire.check("today-lock", lock.as_record())
    horizons = []
    for days in (1, 3, 7):
        window = forecast_window(NOW, days); wire.check("forecast-window", window.as_record())
        available = AvailabilityFrame("snapshot", NOW, window.cutoff, (Interval(NOW, NOW + timedelta(seconds=inputs["capacity_seconds"])),), (), "READY")
        wire.check("availability", available.as_record())
        projections = (RequiredProjection(budget, "REQUIRED", budget.seconds, "FULL_DUE", "scope"),)
        fingerprint = forecast_fingerprint(window, snapshot_ref="snapshot", availability=available, projections=projections, hard_constraints_ref="fixture-proof")
        proof = PlacementEvidence(fingerprint, "synthetic-bounded-proof", "1", "FEASIBLE", NOW, "fixture-proof")
        horizons.append(assess_forecast(window, snapshot_ref="snapshot", availability=available, projections=projections, hard_constraints_ref="fixture-proof", placement=proof, assessed_at=NOW))
    plan = PlanSnapshot("plan", "snapshot", 1, "synthetic-config", NOW, tuple(horizons), (PlanTask(budget, task["title"], "REQUIRED"),), (WorkAllocation("allocation", "work", 1, None, budget.seconds, "Advance synthetic work", "FRAGMENTABLE"),), (PlanItem("item", "allocation", "ADVANCE"),))
    wire.check("plan", plan.as_record())
    result, store, _, _ = fake_write((RecordWrite(AggregateKey("TODAY_LOCK", lock.lock_id), None, json.dumps(lock.as_record())), RecordWrite(AggregateKey("PLAN", plan.plan_id), None, json.dumps(plan.as_record()))), records=(StoredRecord(AggregateKey("TASK", "work"), 1, json.dumps(task)), StoredRecord(AggregateKey("EFFORT", "work"), 1, json.dumps(effort("work", user)))))
    snapshot = store.snapshot(RequestContext("read", "read")).value
    kept = next(r.body for r in snapshot.records if r.key.kind == "EFFORT")
    return wire.finish(commit_status=result.status, model_budget=budget.seconds, canonical_user_seconds=kept["user_remaining"]["seconds"], intent=lock.intent, audit_entries=len(snapshot.audit), horizon_risks=[h.risk for h in horizons])


def evening(inputs):
    wire = Wire(); users = (estimate("worked", inputs["original_seconds"]), estimate("untouched", inputs["unchanged_seconds"]))
    tasks = tuple(ReviewTask(name, 1, importance, "INCOMPLETE", "ACTIVE", True, user, status, "CURRENT") for name, importance, user, status in [("worked", 5, users[0], "WORKED"), ("untouched", 4, users[1], "UNTOUCHED")])
    frame = ReviewFrame("review", 1, "queue", NOW, tasks, ("candidate",));view = present_review(frame)
    parsed = task_reply(view, 1, completion="未完成", remaining=str(inputs["remaining_seconds"])+"秒", worked="做过", actual=str(inputs["actual_seconds"])+"秒", actual_measure="本次新增")
    batch = unchanged_reply(view, (2,), batch_id="unchanged", confirm_estimate="确认", confirm_completion="确认", no_work="没做")
    reply, issues = prepare_response(view, current_frame=frame, submitted=True, statement_ref="captured-user-source", task_replies=(parsed,), batches=(batch,), candidate_replies=(candidate_reply(view, 1, "拒绝"),))
    if issues: raise AssertionError(issues)
    wire.check("review-response", reply.as_record());coverage = assess_review(frame, reply, caller=USER, response_at=NOW + timedelta(minutes=1))
    new_remaining = coverage.task_effects[0].user_estimate.seconds
    writes = [RecordWrite(AggregateKey("REVIEW_RESPONSE", "review"), None, json.dumps(reply.as_record()))]
    for effect in coverage.task_effects:
        prior_task = next(t for t in tasks if t.task_id == effect.task_id)
        original = dict(core(effect.task_id), importance=prior_task.importance)
        changed = effect.user_estimate.observation_id != prior_task.user_estimate.observation_id
        current = dict(original, revision=2 if changed else 1)
        wire.check("task-core", current)
        record = dict(effort(effect.task_id, effect.user_estimate), task_revision=current["revision"]);wire.check("effort", record)
        writes.append(RecordWrite(AggregateKey("EFFORT", effect.task_id), 1, json.dumps(record)))
        if changed: writes.append(RecordWrite(AggregateKey("TASK", effect.task_id), 1, json.dumps(current)))
    seeds = tuple(record for t in tasks for record in (StoredRecord(AggregateKey("EFFORT", t.task_id), 1, json.dumps(effort(t.task_id, t.user_estimate))), StoredRecord(AggregateKey("TASK", t.task_id), 1, json.dumps(dict(core(t.task_id), importance=t.importance)))))
    result, store, _, _ = fake_write(writes, records=seeds, at=NOW + timedelta(minutes=1))
    snapshot = store.snapshot(RequestContext("read", "read")).value
    return wire.finish(responses_complete=coverage.responses_complete, remaining_seconds=new_remaining, actual_increment=coverage.task_effects[0].actual_report.seconds, unchanged_seconds=coverage.verifications[0].verified_estimate.seconds, original_observation_retained=coverage.verifications[0].verified_estimate.observation_id == users[1].observation_id, candidate_resolution=coverage.candidate_effects[0].resolution, commit_status=result.status, audit_entries=len(snapshot.audit))


def generation(inputs):
    wire = Wire(); source, target = Endpoint("TASK", "source"), Endpoint("TASK", "preparation")
    rule = RelationshipRule("rule", "1", True, "accepted-rule", "CANONICAL_CREATION", "source-type", "target-type", "template", "1", "preparation", "SEPARATE_TASK", ("title", "completion", "disposition", "requiredness"), (literal("title", "Synthetic preparation"), literal("completion", "INCOMPLETE"), literal("disposition", "ACTIVE"), literal("requiredness", "REQUIRED")))
    scope = RuleScope("rule", "1", "source", "creation", "occurrence", "preparation");creation = CreationRecord("creation", "source", "occurrence", True)
    link = TaskRelation("before", 1, "COMPLETION_ORDER", target, source, "accepted-order")
    wire.check("relationship-rule", rule.as_record());wire.check("task-relation", link.as_record())
    graph_issues = check_relationships((rule,), (link,), endpoints=frozenset((source, target)))
    options = dict(creation=creation, source_type_ref="source-type", source_fields={}, template_ref="template", template_version="1", defaults={})
    resolution = resolve_generation(rule, scope, occurrences={}, **options)
    changes = (change("preparation", None, "CREATE_TASK", resolution.fields),)
    command = Command("generate", "engine", "RELATIONSHIP_RULE", "grant", changes, rule_scope=scope);wire.check("command", command.as_record())
    grant = AuthorityGrant("grant", "engine", "RELATIONSHIP_RULE", "generate", changes, "accepted-rule", NOW, rule_scope=scope, essential_fields=frozenset(rule.essential_fields))
    caller = CallerIdentity("engine", "RELATIONSHIP_RULE", True)
    allowed = authorize(command, caller=caller, grants={"grant": grant}, tasks={"source": TaskState("source", 1)}, creations={"creation": creation}, now=NOW).allowed
    if not allowed: raise AssertionError("Synthetic resolved generation not authorized")
    target_record = core("preparation", title=resolution.fields["title"], authority="grant");wire.check("task-core", target_record)
    occurrence = GenerationOccurrence(scope, "SEPARATE_TASK", "CREATED", "preparation");wire.check("generation-occurrence", occurrence.as_record())
    result, store, request, permit = fake_write((RecordWrite(AggregateKey("TASK", "preparation"), None, json.dumps(target_record)), RecordWrite(AggregateKey("GENERATION", scope.generation_key), None, json.dumps(occurrence.as_record()))), records=(StoredRecord(AggregateKey("TASK", "source"), 1, json.dumps(core("source"))),), caller=caller)
    replay = store.commit(request, caller=caller, permit_ref=permit.permit_ref)
    resolution_replay = resolve_generation(rule, scope, occurrences={scope.generation_key: occurrence}, **options)
    budgets = [select_budget(task_id=name, task_revision=1, snapshot_at=NOW, user_estimate=estimate(name, seconds), prediction=None) for name, seconds in [("source", inputs["source_seconds"]), ("preparation", inputs["preparation_seconds"])]]
    snapshot = store.snapshot(RequestContext("read", "read")).value
    return wire.finish(graph_issues=len(graph_issues), authorized=allowed, total_seconds=sum_obligations(tuple(budgets + [budgets[1]])).seconds, generation_replay=resolution_replay.state, commit_status=result.status, replay_status=replay.status, audit_entries=len(snapshot.audit))


def expiration(inputs):
    wire = Wire(); task = TaskState("preview", 1, "EXPIRING", expiration_condition_ref="class-start");u = estimate("preview", inputs["user_seconds"])
    condition = ConditionEvidence("condition", "class-start", True, NOW)
    notice = detect_expiration(task, condition, now=NOW).notice
    notice = begin_dispatch(notice, attempt_id="attempt", started_at=NOW, correlation_ref="correlation")
    request = NotificationRequest(RequestContext("send", "correlation"), notice.notice_id, "fixture-channel", "fixture-content", notice.attempts[0])
    result = DispatchResult(notice.notice_id, DispatchAttempt("attempt", NOW, "DELIVERED", NOW + timedelta(seconds=2), NOW + timedelta(seconds=1), "fixture-receipt", "correlation"))
    wire.check("dispatch-result", result.as_record())
    sink = FakeNotificationSink(send_replies=((request, PortResult("SUCCESS", "FIXTURE_RECEIPT", "correlation", result)),))
    notice = record_dispatch(notice, sink.send(request).value);wire.check("expiration-notice", notice.as_record())
    checked_at = NOW + timedelta(seconds=3);ready = revalidate_expiration(notice, task, replace(condition, observed_at=checked_at), checked_at=checked_at)
    changes = (change("preview", 1, "EXPIRE_TASK", {"disposition": "EXPIRED", "expiration_notice_ref": notice.notice_id}),)
    command = Command("expire", "expiration-engine", "EXPIRATION_PROCESS", "expiry-grant", changes);wire.check("command", command.as_record())
    grant = AuthorityGrant("expiry-grant", "expiration-engine", "EXPIRATION_PROCESS", "expire", changes, "accepted-expiry-policy", checked_at)
    caller = CallerIdentity("expiration-engine", "EXPIRATION_PROCESS", True)
    allowed = authorize(command, caller=caller, grants={grant.grant_id: grant}, tasks={"preview": task}, notices={notice.notice_id: ready.notice_evidence}, now=checked_at).allowed
    if not allowed: raise AssertionError("Delivered/current expiry not authorized")
    before = core("preview", requiredness="EXPIRING", condition="class-start")
    after = dict(before, revision=2, disposition="EXPIRED", expiration={"condition_ref": "class-start", "notice_ref": notice.notice_id});wire.check("task-core", after)
    after_effort = dict(effort("preview", u), task_revision=2, disposition="EXPIRED");wire.check("effort", after_effort)
    committed, store, _, _ = fake_write((RecordWrite(AggregateKey("TASK", "preview"), 1, json.dumps(after)), RecordWrite(AggregateKey("EFFORT", "preview"), 1, json.dumps(after_effort))), records=(StoredRecord(AggregateKey("TASK", "preview"), 1, json.dumps(before)), StoredRecord(AggregateKey("EFFORT", "preview"), 1, json.dumps(effort("preview", u)))), caller=caller, at=checked_at)
    snapshot = store.snapshot(RequestContext("read", "read")).value
    kept = next(r.body for r in snapshot.records if r.key.kind == "EFFORT")
    return wire.finish(delivery=notice.delivery_state, ready=ready.ready, authorized=allowed, completion=after["completion"], disposition=after["disposition"], canonical_user_seconds=kept["user_remaining"]["seconds"], commit_status=committed.status, sends=sink.send_count)


def goal(inputs):
    wire = Wire();target_amount = Decimal(inputs["target"])
    config = GoalConfig("goal", 1, "Synthetic measured goal", "ACCEPTED", "accepted-goal", GoalTarget("Read a synthetic corpus", Measure(target_amount, "pages")), None, "QUANTITY", "pages", True, normalize_due(date(2026, 6, 1), source_ref="synthetic-date"), Cadence("WEEKLY", "Synthetic cadence", 2), (), ())
    progress = GoalProgress("goal", 1, "progress", NOW, "synthetic-progress", Measure(Decimal(inputs["reported"]), "pages"), "INCOMPLETE")
    milestone = Milestone("milestone", "goal", 1, "Checkpoint", 1, None, Measure(target_amount / 2, "pages"), None)
    readiness = assess_onboarding(config)
    for name, record in [("goal", config.as_record()), ("goal-progress", progress.as_record()), ("goal-onboarding", readiness.as_record()), ("milestone", milestone.as_record()), ("normalized-due", config.target_due.as_record())]:wire.check(name, record)
    user = estimate("work", inputs["task_seconds"]);before = effort("work", user);wire.check("effort", before)
    committed, store, _, _ = fake_write((RecordWrite(AggregateKey("GOAL", "goal"), None, json.dumps(config.as_record())), RecordWrite(AggregateKey("GOAL_PROGRESS", "progress"), None, json.dumps(progress.as_record()))), records=(StoredRecord(AggregateKey("EFFORT", "work"), 1, json.dumps(before)),))
    snapshot = store.snapshot(RequestContext("read", "read")).value
    remaining = next(r.body["user_remaining"]["seconds"] for r in snapshot.records if r.key.kind == "EFFORT")
    return wire.finish(ready=readiness.configuration_ready, generation_state=readiness.generation_state, target_fraction=str(measured_target_fraction(config, progress)), completion=progress.completion, milestone_issues=list(validate_milestones(config, (milestone,))), task_seconds=remaining, commit_status=committed.status)


RUNNERS = {"morning": morning, "evening": evening, "generation": generation, "expiration": expiration, "goal": goal}


def run_scenario(case):
    return RUNNERS[case["kind"]](case["inputs"])
