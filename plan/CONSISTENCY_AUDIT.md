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

The safety/selection rules remain: one-hour reserve per represented day; SAFE/DANGER/EMERGENCY from REQUIRED feasibility; separate 1/3/7-day reports and worst-horizon mode; protect REQUIRED feasibility/reserve, then use importance for discretionary allocation; leave roughly 40-minute-or-smaller residual gaps in SAFE rather than fill them merely for utilization. Overall EMERGENCY uses a provisional baseline followed by user choices and recalculation. Internal numeric learning may be automatic; behavioral rules require review.

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

The initial audit identified eight gaps/tensions. The user subsequently instructed the AI to resolve internal implementation matters autonomously and ask about user experience. O03 and O06 are now resolved engineering specifications under existing accepted semantics; the six other rows await user-experience answers. Keep their original IDs for traceability. No unanswered experience choice is treated as accepted policy.

| ID | Open question | Known constraints / interim treatment | Resolve by |
| --- | --- | --- | --- |
| O01 | Does approval of a recurring/TaskType/Goal/conditional template preauthorize canonical instances, or must every instance be reviewed? | A0 promises automatic generation/activation but D-029/033/058 require review of Task facts. Automatic candidate generation is safe and accepted; no silent canonical-instance exception exists. Template inheritance alone does not settle this. | M2 authority contract; exercise real Goal examples in M5B |
| O02 | May the system automatically commit EXPIRED at an accepted expiration condition, or does the canonical transition require confirmation? | Expiration is distinct from overdue; clock crossing can be detected and reported. Never infer successful completion or silently change REQUIRED work into expired work. Preserve pending evidence until authority is resolved. | M2 lifecycle/permission contract |
| O03 — RESOLVED | Parent/stage effort and rework consistency. | Parent user budget controls totals; stage budgets are derived allocations. Preserve conflicting accepted values and ask only when material. Explicit confirmed rework of the same obligation reopens stage/parent consistently with audit and remaining effort; ambiguous meaning stays pending. | DATA_MODEL_PLAN §12; conceptual acceptance in TESTING_PLAN §10 |
| O04 | Which remaining-effort value feeds forecasts when user and model disagree, and how report numeric uncertainty without overriding canonical state? | User value remains canonical, prediction advisory, disagreement may warn. Exact conservative forecast/sensitivity method is not accepted yet. | M2 conceptual meaning; Planner implementation with representative fixtures |
| O05 | What are user planning timezone, 1/3/7-day boundaries, partial-day reserve conventions, date-only deadline cutoff, and DST handling? | Use a configured user timezone; server locale is not authority. One-hour/day target and risk inequalities stay fixed. No actual timezone or date-only cutoff is inferred from chat/environment. | M2 semantics and M4 real Calendar fixtures |
| O06 — RESOLVED | Required placement and multi-horizon accounting. | Check deadline/window/dependency/session feasibility. Proven required placement deficit is EMERGENCY; otherwise apply reserve margins. Project necessary early work from one longer-horizon workload model, count once, and distinguish heuristic failure from proof. | PLANNER_PLAN §21; conceptual acceptance in TESTING_PLAN §10 |
| O07 | Does the SAFE ~40-minute residual-gap rule refer to capacity beyond the reserve, individual fragments, or aggregate remainder? | Preserve the one-hour reserve and small-gap rule as separate concepts. Do not double-subtract reserve or consume it merely for optional utilization. | M2 semantic examples; M6 capacity fixtures |
| O08 | How efficiently clear the full queue and obtain remaining effort for every relevant incomplete Task within typical 5–10 minute reviews, including untouched tasks/unanswerable questions? | D-051/065 remain requirements; target duration is not an override. Present all, retain unanswered items, offer estimates/templates, follow up on required missing fields. Do not auto-answer from a model. Carry-forward/reconfirmation UX needs explicit design. | M2 interaction examples; initial MVP review flow |

Other intentionally deferred implementation work remains where it belongs: schemas/DDL, connector/API fields and real credentials, programming language, deployment provider, model-cost/provider policy, notification delivery/repeat mechanics, statistical methods, and optional calendar-writing scope. The accepted human Daily Brief, importance/difficulty scales, reserve, requiredness vocabulary, two-day reminder trigger, and authority distinction are not deferred decisions.

## 5. Verification and Next Handoff

Document-level verification checks the complete file inventory, local Markdown targets, decision references, supersession/obsolete-policy phrases, and propagation of the corrected requirements to dependent documents. Changed files preserve the existing decision IDs and intent sections; additions clarify cross-module invariants and explicitly open questions rather than deleting user requirements.

Local checks passed: 22 Markdown files (21 originals + this report), 12 local Markdown link targets, all 70 decision IDs and 59 A0 numbered sections preserved, 21 finding classes and the original 8 boundary IDs represented (O03/O06 subsequently resolved; 6 experience choices pending), targeted obsolete-policy scan, requirement propagation checks, and whitespace/diff checks. Commit publication also checks the remote base head and resulting file blobs; publication success is established by the GitHub write/read results, not by this local check statement.

No code, database, workflow, connector, Planner, learning algorithm, schema validator, or renderer was run because none exists here. Documentation consistency is not runtime validation or proof that an exact future scheduling algorithm is correct.

Current handoff: collect the six remaining user-experience answers (O01/O02/O04/O05/O07/O08), propagate the accepted rules, then prepare the detailed project plan from these reconciled documents. Map modules and milestones to concrete deliverables, inputs/outputs, user-information checkpoints, dependency gates, meaningful acceptance tests, and operating steps. Keep accepted rules, missing user facts, open semantic boundaries, and technical proposals separate. Then continue M1 → M1B → M2 before implementation. Do not broadly reopen A0 or assume current courses/tasks from previous chat.

---

## 6. Boundary Triage — 2026-10-06 Follow-Up

O03 and O06 are internal accounting/constraint-model specifications and have been resolved without changing the already accepted user-facing fields, confirmation principles, difficulty/importance, or reserve thresholds. This is documentation/design work, not runtime implementation or an assertion that an optimization library has already been tested.

The remaining experience choices are: automatic recurring/template Task acceptance (O01), automatic expiration disposition (O02), user-vs-model estimate used to allocate time (O04), displayed planning day/timezone conventions (O05), what constitutes a SAFE short gap (O07), and whether unchanged remaining estimates are confirmed in bulk during review (O08). The next response asks these in ordinary language, including the timezone fact within O05. Do not choose for the user merely because a recommendation is offered.
