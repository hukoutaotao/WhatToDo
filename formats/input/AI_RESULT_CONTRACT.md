# AI Job and Result Development Contract

M2-11.a implements an offline, versioned handoff. [Accepted AI execution](../../plan/AI_EXECUTION_PLAN.md), [learning](../../plan/LEARNING_PLAN.md), [authority](COMMAND_AUTHORITY_CONTRACT.md) and [effort](EFFORT_CONTRACT.md) remain authoritative. This slice does not select a provider, train a model, send personal data or persist changes.

## Records and Ownership

| Contract | Meaning |
| --- | --- |
| [AI job](ai-job.schema.json) | Trusted scoped job, executor class, context hash/reference, snapshot and resolved target revisions. |
| [Export](ai-export.schema.json) | Reference-only handoff with stable export identity and explicit external-data role. |
| [Result](ai-result.schema.json) | Untrusted numeric remaining-work output or behavioral proposal, executor reference and exact/unknown usage. |
| [Remaining prediction](remaining-prediction.schema.json) | Validated derived prediction with result fingerprint and independently supplied eligibility reference. |
| [Behavior candidate](behavior-candidate.schema.json) | Pending proposed configuration/policy data; never an accepted preference or authority grant. |
| [Import history](ai-import-record.schema.json) | Immutable validation outcome and timestamp bound to the submitted result's source identity. |

All six are `0.1.0-draft` development contracts. Their control fields are closed. Proposed policy values are opaque structured data, which require later policy-specific validation and scoped user authorization. The domain's typed records have copied JSON payloads and immutable histories. Strict raw JSON loading and schema validation must precede construction; domain checks supplement shape validation.

## Export and Import

[Pure helpers](../../src/domain/ai_results.py) export only pending/already exported jobs, retaining the original export timestamp and stable identity on replay. Artifacts carry context references and hashes, not raw history or credentials. Resolving references into explicitly minimized real context, file transfer and model execution are future adapter work. A valid export is not proof of dispatch or provider identity.

Fresh imports must match trusted job ID/revision, context hash, snapshot, output contract, result kind and every target's current registry revision. Cancelled, rejected or undispatched pending jobs cannot activate an output. Result times must follow the applicable dispatch/export boundary and cannot be future-dated. Executor metadata is evidence, not authentication.

Numeric imports require a current active incomplete Task and independently trusted model eligibility bound to Task revision, model/version, context, snapshot and validity interval. Model-declared confidence or validity does not supply that eligibility. Only `REMAINING` quantities are accepted; original total effort cannot stand in for remaining work. Computation time must precede result time; prediction validity must cover validation time and stay within independent eligibility. The caller must not build trusted eligibility from the same untrusted result. Resolving and persisting that trusted registry is later application work.

Valid numeric outputs feed the existing model-first budget selector. B may be below, above or zero relative to U. Canonical user effort, Task completion/disposition and observations are never rewritten. A zero prediction does not complete a Task, and missing U still requires review. Derived identity is scoped to job version/result content/target, retaining the external prediction ID as provenance.

Preference, TaskType-default, relationship-rule and decomposition proposals always produce `PENDING_REVIEW` candidates, even at confidence 1. Their payload cannot self-accept or declare authority. Later policy adoption must use the separate user-command/authority path; these helpers do not execute proposed values.

## Replay, History and Unknowns

Import history uses `(submitted job ID, result ID)` identity and a canonical semantic result fingerprint. Identical retries return no new prediction/candidate and preserve the original validation outcome/time. Changed content under the same identity returns a conflict and does not replace history. Rejected results remain rejected historical records; duplicate ambiguous history requires reconciliation. A historical replay after cancellation or context change remains a no-effect replay, never fresh activation. Raw-byte hashes belong to the separate source/provenance record.

Unknown token counts/cost remain null; zero is an explicitly known measurement. Known cost uses exact nonnegative decimal text plus currency. No currency conversion, provider pricing, quota or cost policy is assumed.

## Executed Checks and Remaining Scope

`python -m unittest tests.test_ai_results -q` exercises 19 methods and [29 synthetic schema cases](../../tests/fixtures/ai_results/cases.json): immutable export/replay; stale and mismatched scope/model/Task; cancellation and completion; timing; total-versus-remaining; B/U preservation; pending policy; duplicate/nonfinite JSON; unknown usage; conflicting results; typed serialization.

The complete AI Router, eligible-model selection/calibration, actual provider identity/cost, context builder, persistent jobs/history and reviewed policy adoption are not implemented. These checks contain no real course data and do not certify live AI readiness. [Live progress](../../plan/PROGRESS.md) records this bounded completion separately from the unfinished M2 milestone.
