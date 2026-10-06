# WhatToDo — Full-Document Consistency Audit

> Date: 2026-10-06
> Scope: all 21 pre-existing Markdown files; no implementation files existed.
> Source snapshot: `c1ce632e26c2a7b497e1a87074dc39bacd7af04f` on `main`.
> Requested work: fully review the project, correct inconsistent documentation, then prepare detailed project planning in the next step.
> Status: document reconciliation complete. This report is an audit/handoff, not a new source of user-approved policy.

## 1. Product Understanding

WhatToDo reduces the cognitive burden of remembering heterogeneous obligations and arranging realistic work. It maintains trusted Tasks, workload, availability, course context, long-term structures, evidence, and effort history. Normal operation is a guided morning update/plan and consolidated evening review, roughly 5–10 minutes each. Automatic collection continues between interactions; uncertain or external personal Task facts await review. It recommends work and suitable session styles rather than assigning exact clock times by default.

Task is the shared planning unit across academics, exercise, life administration, and other. Course/Activity/Goal/Exam layers provide context, templates, generation, and horizons; they do not create separate task worlds. Requiredness, importance, three-dimensional difficulty, effort, session suitability, and completion belong to Tasks/TaskType defaults. Parent obligations own deadlines; stages support concrete daily action. User-confirmed remaining effort remains canonical; numeric predictions are separate.

Architecture direction remains n8n-only orchestration, PostgreSQL dynamic state, Git-backed stable declarative profiles/config, Calendar occupancy, deterministic-first Planner, replaceable AI, structured proposals, authorized validation, and an eventual always-on runtime. Google Calendar is preferred; email provider, implementation language, hosting, machine schemas, real adapters, and statistical algorithms are not selected.

The safety/selection rules remain: one-hour reserve per represented day; SAFE/DANGER/EMERGENCY from REQUIRED feasibility; separate 1/3/7-day reports and worst-horizon mode; protect REQUIRED feasibility/reserve, then use importance for discretionary allocation. D-076 resolves the earlier short-gap ambiguity: leave aggregate whole-day discretionary remainder at most 40 minutes free in SAFE, rather than applying a per-window minimum. Overall EMERGENCY uses a provisional baseline followed by user choices and recalculation. Internal numeric learning may be automatic; behavioral rules require review.

## 2. Findings and Repairs

| ID | Original problem | Reconciled treatment | Main locations |
| --- | --- | --- | --- |
| C01 | A0 allowed unambiguous published facts to establish operational truth while later sections prohibited unreviewed Task changes. Architecture/email also allowed confidence-based acceptance. | External sources establish what they published, not accepted personal Task facts. Confidence affects recommended interpretation, not write authority. Clear resolved user commands can authorize their exact update. | A0 §15/23/25/57–58; DECISIONS D-033/064; PROJECT, IO, INTEGRATION, AI |
| C02 | Early accepted decisions still said difficulty/importance/risk scales were undecided. | Difficulty and importance use 1–5; risk inequalities and one-hour reserve are fixed. Only encoding/calibration/partial-day mechanics remain deferred. Earlier IDs point to their refinements. | A0 §7/22/24/30/49; DECISIONS D-017/030/040/037/043/059 |
| C03 | A0 still deferred inactivity threshold after fixing it at two days. | Two consecutive days is the accepted reminder trigger; channel/repeat behavior remain open. | A0 §24/55; OPERATIONS; DECISIONS D-055 |
| C04 | Course examples and F2 treated Course importance as a main Planner variable. | Course is context. TaskType initializes Task importance/requiredness and three difficulty dimensions; Course has no primary priority scalar. | ALIGNMENT worked table; DEVELOPMENT F2; PROJECT Planner inputs; USER_MODEL |
| C05 | Profile collection still requested generic lead time and reopened already accepted preferences/output. | Remove generic start-N-days-early inputs; retain feasibility-driven work distribution and explicit exam phases. Collect concrete values/exceptions, not repeated A0 decisions. | USER_MODEL; PLANNER inputs; DEVELOPMENT |
| C06 | Roadmap mixed candidate/confirmed/in-progress/completed/overdue/stale into one lifecycle. | Separate acceptance, binary parent completion, lifecycle/disposition, and derived trust/risk. Partial work uses effort/stages. Overdue REQUIRED work is not automatically cancelled/expired. | DEVELOPMENT foundational artifacts; DATA_MODEL §3/11 |
| C07 | Learning example required approval for a numeric duration multiplier despite permitting automatic numeric learning. | Automatic internal numeric calibration is distinct from reviewed behavioral/config changes. Neither overwrites user-canonical estimates. | LEARNING §1/7–9/13; AI; A0 §40/54/58; DECISIONS D-041/054/066 |
| C08 | Reconciliation asked only high-impact questions, conflicting with full-queue review. | Present the whole queue, high-impact first. Retain unanswered items; do not fabricate facts to meet the 5–10 minute target. Missing remaining effort still triggers follow-up. | PROJECT recovery; DEVELOPMENT F8; IO §10; TESTING |
| C09 | General Planner lacked the required two-round emergency protocol; A0 described only the day's mode. | Overall worst-horizon EMERGENCY triggers provisional baseline → user sacrifices/additional time → recompute. Show residual infeasibility. Daily removal is not Task cancellation. | A0 §38; PLANNER §18; IO §10; template; TESTING |
| C10 | Removing optional work could be read as solving an R-only capacity deficit. | OPTIONAL removal alone cannot lower REQUIRED R. Final output must retain unresolved deficit and respect deadlines/windows. | PROJECT §26; PLANNER §18; IO; template; TESTING |
| C11 | Parent remaining effort, child estimates, and fragment sections had no shared accounting constraint. | Count the obligation and selected daily allocation once. Require parent/stage estimate reconciliation before schema freeze. Repeated rendering references add no workload. | DATA_MODEL §11; PLANNER §19; template; TESTING |
| C12 | Daily template's optional/fragment work omitted fields mandated for every recommended item; fragment work could duplicate other sections. | Every new recommendation has parent remaining effort, selected stage/chunk estimate, work style, and relevant deadline. Prefer labels or references for fragmentability. Distinguish plan role from requiredness. | template; IO; formats READMEs |
| C13 | Architecture deferred the whole Daily Brief despite an accepted template; input directory gave no accepted context. | Preserve accepted human semantics; defer only machine encoding/rendering refinements. Add links and handoff guidance to both format directories. | PROJECT; IO; formats READMEs |
| C14 | Generic Goal contracts were required before persistence but deferred in roadmap to M5B. | Define generic onboarding/approval/generation semantics in M2 before Goal persistence; M5B refines real examples and runtime activation. Milestone order otherwise remains. | DEVELOPMENT Phase 1/M2/M5B; DATA_MODEL/IO |
| C15 | Confirmation/validator/audit/staleness/recovery/history appeared to begin only in late AI/resilience phases. | Minimal safeguards belong to persistence/first ingestion/MVP. Phase 6 extends AI validation; Phase 7 extends recovery and learning. | DEVELOPMENT Phase 2/4/5/6/7; AI; OPERATIONS; TESTING |
| C16 | Collection before full AI Router and natural-language prototypes had ambiguous prerequisites; architecture looked like AI was required for every plan. | Early deterministic/reviewed/optional narrowly validated extraction is possible without full Router. Basic write validation and ordinary planning do not depend on AI. | PROJECT §14/26; INTEGRATION §11; DEVELOPMENT §13; AI §10 |
| C17 | Tests retained the superseded REQUIRED-first discretionary rule, conflated DANGER with EMERGENCY, and placed full Weekly output in Daily MVP gate. | Align tests with importance-based discretionary work, exact risk categories, and later full Weekly acceptance; keep required history in earlier phases. | TESTING §3/7/9 |
| C18 | Authority hierarchy omitted A0, treated status/sequence as stronger than semantics, and root README was empty. | Use subject-specific authority and explicit refinement relationships; root/control READMEs provide a complete entry point. | root README; plan README §2–3; DECISIONS reading rules |
| C19 | M1 immediate handoff would bypass the user's current request to audit, then prepare detailed planning. | Audit complete; detailed planning next. M1 remains the next incomplete semantic milestone. No current profiles or runtime are claimed complete. | PROGRESS; DEVELOPMENT §12–13; ALIGNMENT closure; root/control READMEs |
| C20 | Raw-content deletion could be confused with deletion of normal historical outcomes. | Minimize unnecessary raw content while retaining semantic Task outcomes/estimates/rework/audit, except explicit privacy/error/duplicate removal. | SECURITY §11; DATA_MODEL; LEARNING |
| C21 | Forecast descriptions omitted deadline-prefix/window bottlenecks, beyond-7-day necessary work, timezone, and staleness limits. | Add constraints to avoid false feasibility, duplicate reserve subtraction, forgotten long-horizon work, or server-time assumptions. Exact algorithms remain open. | PLANNER §19–20; DATA_MODEL; OPERATIONS; TESTING |

Repairs reconcile accepted statements or add explicit conceptual engineering constraints derived from those statements. They do not claim the user accepted a specific database design, forecast algorithm, provider, permission exception, or current-semester fact.

## 3. Requirement Coverage and Document Inventory

All pre-existing files were read in full. No source content from outside the repository was used to invent current project facts.

| File | Role and inspected dependencies |
| --- | --- |
| `README.md` | Repository entry point; links intent, decisions, status, roadmap, and audit |
| `plan/README.md` | Authority by subject, dependency propagation, truthful status conventions |
| `plan/A0_USER_INTENT.md` | Accepted product semantics across all A0 rounds; reconciled earlier wording |
| `plan/DECISIONS.md` | D-001–D-070 retained; refinements explicit; superseded records preserved |
| `plan/ALIGNMENT_PLAN.md` | Completed A0, semantic modeling method, corrected Course worked example |
| `plan/PROJECT_PLAN.md` | Architecture, storage/Calendar/AI boundaries, corrected pipelines |
| `plan/DEVELOPMENT_PLAN.md` | Provisional milestone order, earlier safety foundations, M2/M5B dependency repair |
| `plan/PROGRESS.md` | Actual document-only status; detailed planning next; M1/M1B/M2 incomplete |
| `plan/USER_MODEL_PLAN.md` | M1/M1B profile collection; accepted defaults vs missing user-specific facts |
| `plan/DATA_MODEL_PLAN.md` | TaskType/templates, acceptance/completion/lifecycle/trust separation, effort/history/authority |
| `plan/IO_CONTRACT_PLAN.md` | Human review/direct authority, candidate flows, brief/review/emergency semantics |
| `plan/INTEGRATION_PLAN.md` | Source authority vs Task truth, Calendar occupancy, dedup/replay and deferred providers |
| `plan/PLANNER_PLAN.md` | Feasibility, reserve, discretionary order, horizons, emergency protocol, workload accounting |
| `plan/LEARNING_PLAN.md` | Automatic numeric calibration vs approved behavioral rules, history/estimate provenance |
| `plan/AI_EXECUTION_PLAN.md` | Replaceable models, Plus/manual boundary, validation plus write authority |
| `plan/OPERATIONS_PLAN.md` | Always-on direction, safe failure, reminders/timezone/observability and staged safeguards |
| `plan/SECURITY_PRIVACY_PLAN.md` | Secrets/minimization, personal-state protection, raw vs semantic retention |
| `plan/TESTING_PLAN.md` | Conceptual quality gates and cross-rule regression scenarios, no runtime claims |
| `formats/input/README.md` | Accepted input semantics; M2 concrete schema deliverables still pending |
| `formats/output/README.md` | Output authority, conceptual template vs machine renderer |
| `formats/output/DAILY_BRIEF_TEMPLATE.md` | Required item fields, nonduplicated sections, risk and provisional/final emergency output |

The core propagation paths are intent/decisions → profile/data/I-O → integrations/Planner/learning/AI → operations/security/testing → concrete formats. Status/roadmap reflect their actual readiness. This audit is an additional handoff file, not a replacement for that structure.

## 4. Boundary Register — Updated 2026-10-06

The initial audit identified eight gaps/tensions. The user subsequently instructed the AI to resolve internal implementation matters autonomously and ask about user experience. O03/O06 are resolved engineering specifications. The latest six user answers now resolve O01/O02/O04/O07/O08 and the timezone/cutoff part of O05. Only O05 horizon scope remains unanswered; see Section 7. Keep their original IDs for traceability. No unanswered experience choice is treated as accepted policy.

| ID | Open question | Known constraints / interim treatment | Resolve by |
| --- | --- | --- | --- |
| O01 — RESOLVED | Add a Task relationship system for counterpart generation and required completion order. | Explicit accepted generation rules preauthorize their exact mapped instances; no repeated per-instance confirmation. Defaults alone are not blanket authority; unknown external facts still use review. Generation/order/stages remain distinct. | D-071/D-072; TASK_RELATIONSHIP_PLAN |
| O02 — RESOLVED | Inform before recording EXPIRED under a confirmed expiration condition. | Notify first, then record; no extra acknowledgement was requested. Failed notice/uncertain condition stays pending. Preserve history; overdue REQUIRED work never auto-expires. | D-073; DATA_MODEL/IO/OPERATIONS |
| O03 — RESOLVED; REFINED BY D-074 | Parent/stage effort and rework consistency. | Retain canonical user U separately; use one effective model-first parent budget B to allocate stages and count forecast work once. Preserve conflicting accepted values. Confirmed same-obligation rework updates stage/parent consistently with audit; ambiguous meaning stays pending. | DATA_MODEL_PLAN §12; TESTING_PLAN §10/11 |
| O04 — RESOLVED | Model-first remaining-effort allocation/risk prediction. | Use valid model B, retain user U as canonical state; fallback to U when no valid prediction. Do not substitute max(U,B), conflate total/remaining effort, or sum U+B. | D-074; DATA_MODEL §12; PLANNER/LEARNING/IO |
| O05 — PARTIAL | Beijing timezone and date-only 23:59 accepted; natural-day vs rolling 1/3/7-day scope unanswered. | Asia/Shanghai, preserve explicit times, separate next-midnight override expiry. Do not claim the user chose calendar windows or 24/72/168-hour windows. Partial-day reserve accounting follows the scope once selected. | D-075; one user subquestion before exact horizon fixtures |
| O06 — RESOLVED | Required placement and multi-horizon accounting. | Check deadline/window/dependency/session feasibility. Proven required placement deficit is EMERGENCY; otherwise apply reserve margins. Project necessary early work from one longer-horizon workload model, count once, and distinguish heuristic failure from proof. | PLANNER_PLAN §21; conceptual acceptance in TESTING_PLAN §10 |
| O07 — RESOLVED | SAFE 40-minute rule concerns aggregate whole-day discretionary remainder. | Protect required work/reserve first; total <=40 minutes stays free. Individual short windows may still be used when aggregate is greater and work fits. No double reserve subtraction. | D-076; PLANNER; template; TESTING |
| O08 — RESOLVED | Worked-on Tasks updated individually; untouched unchanged estimates explicitly confirmed together. | Scoped batch preserves prior values and original observation time with per-Task verification provenance. No silent acceptance or coverage of missing/changed/ambiguous facts. | D-077; IO/DATA_MODEL/LEARNING/TESTING |

Other intentionally deferred implementation work remains where it belongs: schemas/DDL, connector/API fields and real credentials, programming language, deployment provider, model-cost/provider policy, notification delivery/repeat mechanics, statistical methods, and optional calendar-writing scope. The accepted human Daily Brief, importance/difficulty scales, reserve, requiredness vocabulary, two-day reminder trigger, and authority distinction are not deferred decisions.

## 5. Verification and Next Handoff

Document-level verification checks the complete file inventory, local Markdown targets, decision references, supersession/obsolete-policy phrases, and propagation of the corrected requirements to dependent documents. Changed files preserve the existing decision IDs and intent sections; additions clarify cross-module invariants and explicitly open questions rather than deleting user requirements.

Historical initial-audit checks passed for 22 Markdown files (21 originals + this report), 12 local Markdown link targets, 70 decision IDs, 59 A0 numbered sections, 21 finding classes, and all 8 boundary IDs. The later answer synchronization adds one document, D-071–D-077, and A0 Section 60; current verification checks all 23 documents and preserves the earlier IDs/sections and findings. O05 alone retains an unanswered horizon-scope subquestion; the initial pending list is superseded. Commit publication also checks the remote base head and resulting file blobs; publication success is established by the GitHub write/read results, not by this local check statement.

No code, database, workflow, connector, Planner, learning algorithm, schema validator, or renderer was run because none exists here. Documentation consistency is not runtime validation or proof that an exact future scheduling algorithm is correct.

Current handoff: accepted answers are synchronized; clarify only O05 natural-day versus rolling-hour horizon scope, then prepare the detailed project plan from these reconciled documents. Map modules and milestones to concrete deliverables, inputs/outputs, user-information checkpoints, dependency gates, meaningful acceptance tests, and operating steps. Keep accepted rules, missing user facts, open semantic boundaries, and technical proposals separate. Then continue M1 → M1B → M2 before implementation. Do not broadly reopen A0 or assume current courses/tasks from previous chat.

---

## 6. Initial Boundary Triage — Historical Follow-Up (Superseded by Section 7)

O03 and O06 are internal accounting/constraint-model specifications and have been resolved without changing the already accepted user-facing fields, confirmation principles, difficulty/importance, or reserve thresholds. This is documentation/design work, not runtime implementation or an assertion that an optimization library has already been tested.

At that earlier point, the experience choices awaiting answers were: automatic recurring/template Task acceptance (O01), automatic expiration disposition (O02), user-vs-model estimate used to allocate time (O04), displayed planning day/timezone conventions (O05), what constitutes a SAFE short gap (O07), and whether unchanged remaining estimates are confirmed in bulk during review (O08). These were asked together. Section 7 records the subsequent user answers; this historical paragraph is not current pending status.

---

## 7. Accepted Answer Synchronization — 2026-10-06

Source: direct user response to the six questions, not inference from old chat. D-071–D-077 and A0_USER_INTENT §60 record the answers. A dedicated TASK_RELATIONSHIP_PLAN.md defines the new requested subsystem; all affected architecture/data/input/output/Planner/learning/integration/AI/operations/security/testing/roadmap/control files are synchronized.

O01 adds accepted relationship-driven generation and completion ordering rather than blanket template auto-acceptance. O02 is notification before expiration record, without an unrequested second confirmation. O04 selects model prediction for planning even when it differs from user-reported remaining effort; canonical facts stay separate. O05 accepts Beijing time and 23:59 but omits the natural-day/rolling-hour choice. O07 is whole-day aggregate <=40 minutes after reserve, not each fragment. O08 is explicit bulk confirmation of untouched unchanged estimates.

Earlier O03 accounting is refined to use effective model-first parent budget B for stage allocation while retaining U separately. O06 feasibility checks consume that same B and distinct hard ordering semantics. No parent/stage/user/model double counting is introduced. Generation graph direction can reverse temporal order without a false combined-graph cycle.

Current status: seven original boundaries resolved, O05 partially resolved with one unanswered horizon-scope subquestion; no other original experience answer remains pending. Concrete schema encoding, implementation libraries, actual rule mappings, provider adapters, delivery channels, and profiles remain normal later milestone work. This synchronization adds accepted documentation/specifications only, not implementation.

Current local verification passed: all 23 Markdown files, 14 local link targets, sequential D-001–D-077, A0 Sections 1–60, the preserved 21 finding classes and 8 boundary IDs, dependent requirement propagation, obsolete-policy checks, unique numbered sections, and whitespace/diff checks. These are document checks; Section 5's runtime limitation still applies.
