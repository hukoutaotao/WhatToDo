# Application Ports and Adapter Ownership

M2-12.a implements [typed internal ports](../../src/application/ports.py) and [no-I/O test adapters](../../src/adapters/fakes.py). [Architecture](../../plan/PROJECT_PLAN.md), [data ownership](../../plan/DATA_MODEL_PLAN.md), [operations](../../plan/OPERATIONS_PLAN.md) and the existing domain contracts remain authoritative. These are Python development interfaces, not frozen transport schemas or live integrations.

## Eight Ports

| Port | Request / result | Ownership and boundary |
| --- | --- | --- |
| StateStore | Coherent snapshot; exact CommitRequest / CommitReceipt; receipt lookup | Canonical aggregate versions, atomic full before/after audit and idempotent receipt. Internal service boundary, never a public arbitrary JSON write endpoint. |
| Clock | `now()` / aware datetime | Trusted injected time; no caller-supplied timestamp grants validity. |
| CalendarSource | SourceReadRequest / CalendarBatch | Scoped events, finite read window, quality, pagination and coverage. No Task completion or personal capacity inference. |
| EvidenceSource | SourceReadRequest / EvidenceBatch | Immutable source records with data-only role. No instructions or canonical mutation authority. |
| NotificationSink | NotificationRequest / DispatchResult; separate receipt reconciliation | One scoped pending attempt; observed delivery/failure/ambiguity. Sending does not itself commit expiration. |
| Predictor | PredictionRequest / untrusted AIResult | Numeric remaining-work job transport; importer and independent eligibility still required. No U/default/policy write. |
| Solver | SolverRequest / PlacementEvidence | Exact input fingerprint; a timeout/unknown outcome is not infeasibility or a SAFE proof. |
| Renderer | RenderRequest / RenderedDocument | Bound Plan identity/snapshot/phase/template/time; renders a document only. Publication is a separate operation. |

Runtime-checkable protocols permit interchangeable test/live adapters. Domain modules do not import these ports, adapter code, SDKs, credentials or n8n. Real implementations must validate raw provider data before creating domain records; the fakes' canned replies are explicit synthetic fixtures, not authentication or live evidence.

## Error Taxonomy

`PortResult` requires an explicit status, redacted diagnostic code and correlation reference. Only `SUCCESS` carries a typed value. Its truth value deliberately raises an error to prevent treating unknown/failed results as ordinary success.

| Status | Next action | Meaning |
| --- | --- | --- |
| SUCCESS | NONE at transport level | A response was obtained. Its domain quality/outcome still matters. |
| RETRYABLE | RETRY_LATER | Adapter establishes a retryable failure; use bounded retry and the same idempotency semantics. |
| PERMANENT | CORRECT_REQUEST | Invalid/untrusted input or incompatible scoped response; no automatic unchanged retry. |
| CONFLICT | RESOLVE_CONFLICT | Stale revision, reused identity with changed meaning, or mismatched scope. |
| UNKNOWN | RECONCILE | Outcome/coverage is unresolved. Do not assume success, absence, zero or safe repetition. |

Transport success can contain a failed/unknown dispatch result, stale or incomplete source page, or solver timeout. Consumers must inspect those domain fields before continuing. Success is not canonical acceptance.

## StateStore Transaction Contract

Storage receives immutable aggregate keys, expected global/aggregate revisions and copied strict JSON object bodies. JSON is opaque at this layer: a valid object is not a valid Task or a user instruction. Schema, references, invariants and exact domain-command scope must be resolved in the application. A real persistent implementation must load/revalidate applicable authority/current state inside its transaction before it writes.

An independently trusted `TransactionPermit` binds authenticated principal/origin, exact concrete request fingerprint and validity interval. Neither an input JSON flag nor a standalone `AuthorizationDecision` fingerprint supplies such a permit. The application owns permit issuance from resolved scoped authority, and must bind the authorized command's full effects to the precise aggregate writes. That issuance/resolution is later application work. The fake seeds registry entries only through trusted test setup and verifies caller, registry membership, exact values and injected-clock validity.

Expected store revision closes the interval between a coherent read/authorization and commit. Each write also checks absent/present aggregate revision. Live adapters may later narrow this conservative whole-store CAS only with equivalent transactional reference/version checks and regression evidence. Creates start at revision 1; updates increment exactly once. Duplicate targets in a batch are invalid.

The fake stages records, immutable before/after audit changes and receipt together, then publishes one state object under one lock. Its fault fixtures distinguish known precommit/audit failure (neither records nor audit nor receipt changed) from lost acknowledgement after commit (all changed, caller sees UNKNOWN). Receipt lookup resolves the original request, and identical retry returns the original receipt without rewriting state/history. Same request ID with changed semantics conflicts. Authenticated original principal/origin is required to inspect/replay a receipt, even after its permit expires. An unobserved receipt is UNKNOWN rather than proof that no commit occurred.

Outbox or other aggregate writes can share this batch with Task records; a pending outbox body is not delivered notice evidence. The fake demonstrates atomic membership only, not an implemented outbox dispatcher or complete Task transition pipeline. Audit timestamps come from the injected trusted clock. Correlation ID changes do not change the semantic write fingerprint.

## Source, Delivery and Derived Output Boundaries

Known-empty complete Calendar data is distinct from an unconfigured/failed read. Scope/window mismatches and duplicate source identities fail validation. Incomplete pages require a continuation cursor; completed pages cannot claim one. Stale/unresolved data retains gap references. The application must finish pagination, enforce actual source freshness and evaluate unresolved occupancy before using capacity; these ports do not silently turn a partial page into a full snapshot.

Evidence batches retain immutable source records and `DATA_NOT_INSTRUCTIONS`. Neither source deletion nor arbitrary content generates authority. Source mappings and collector checkpoints remain future work.

Notification identity binds channel, notice and attempt. Identical sends are replayed without invoking the fake sink again; changed content under the same attempt conflicts. Unknown delivery must be reconciled through the separate receipt method. A mismatched receipt after invoking a send is UNKNOWN, because it cannot establish absence of delivery. Confirmed failed delivery remains failed; actual subsequent retry uses a separately registered domain attempt under the expiration lifecycle. Fakes do not expire Tasks or send user messages.

Predictor replies remain external results; [AI-result import](AI_RESULT_CONTRACT.md) independently validates remaining-only payload, Task/context/model revisions, time and eligibility. Solver replies must match the existing forecast input fingerprint, and [forecast](../output/PLAN_FORECAST_CONTRACT.md) still validates proof/time/quality. FakeSolver returns configured evidence and is not a feasibility algorithm. Rendered documents retain the Plan phase, so a provisional/unverified request cannot be relabeled NORMAL or final. FakeRenderer validates configured metadata and does not implement Daily Brief prose or publication.

## Verification and Remaining Work

[Focused tests](../../tests/test_ports.py) exercise all eight protocol shapes; immutable bodies; strict duplicate/nonfinite JSON; independent permit/caller/exact-value/expiry checks; aggregate/store CAS; atomic multi-record/outbox/audit/receipt writes; failed writes; lost acknowledgements; same-ID conflicts; concurrent same/different requests; known-empty versus unknown source coverage; pagination/scope/staleness; ambiguous/failed notification; no-effect reconciliation; untrusted model output; solver timeout; and Plan phase preservation.

The fake store is linearizable in one process only. No crash durability, PostgreSQL schema/transaction, backup/restore, persisted permit lifecycle, source credentials, actual notification channel, n8n workflow, model, solver, renderer or deployment is claimed. [Live progress](../../plan/PROGRESS.md) separates this bounded development child from those remaining gates.
