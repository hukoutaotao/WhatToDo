# Review and unchanged estimates — development draft 0.1.0

Scope: [M2-05.a](../../plan/tasks/M2_CONTRACTS.md#m2-05a). [Response schema](review-response.schema.json), [pure review module](../../src/domain/review.py), [synthetic cases](../../tests/fixtures/review/cases.json) and [tests](../../tests/test_review.py).

## Full frame and explicit responses

A trusted state adapter supplies an immutable `ReviewFrame` containing the entire current pending-candidate queue and relevant tasks, with a queue snapshot reference, frame revision and presentation time. `questionnaire` preserves every item; task importance changes presentation order only. Suggested completion values are separate from unanswered fields. This module cannot certify that an adapter supplied the entire database queue; that is an integration responsibility.

`ReviewResponse` binds the frame and each task revision. Submission requires a user-statement reference and independently authenticated USER_COMMAND caller context. JSON flags and reference strings do not establish transport identity. Silence, unsubmitted suggestions, omitted answers and stale versions retain pending items. Candidate confirmation supplies a proposed decision, not an authorized canonical mutation by itself.

`assess_review` returns coverage, pending identities, issues and proposed effects without modifying the frame. `responses_complete` means all frame answers are accounted for; it does not mean a normal review has been committed. The application must resolve statement authority, apply accepted candidate changes, revalidate current state and atomically persist the complete review before recording success. A partial reply remains partial even when some effects are valid.

## Unchanged-estimate batches

Each confirmed batch explicitly identifies task ID, task revision, original observation ID and seconds for every member. Only current, future-relevant, ACTIVE/INCOMPLETE tasks with an existing reliable estimate qualify. Worked-on, missing, changed or uncertain estimates are excluded. Unknown work status needs an explicit no-work statement; a positive new-work increment cannot be hidden in a batch. An invalid member rejects the whole batch, and overlapping confirmed batches are rejected.

Verification preserves original U, its observation ID and observation time. It records a separate verification time and deterministic verification identity bound to the review/frame, statement, batch and task. Replay of the same assessment yields the same identity; persistent deduplication remains the state adapter's responsibility. Verifying an estimate does not invent a completion answer: confirming the listed completion state is a separate explicit batch field. No actual-work observation of zero is inferred from unchanged U or an untouched task.

Worked-on, future-relevant incomplete tasks need an individual current U. An explicit COMPLETE answer has remaining U zero; an INCOMPLETE answer with U zero stays INCOMPLETE. Actual work reports retain INCREMENT versus CUMULATIVE meaning. Cumulative reports are held as reported data, not silently appended as increments or subtracted from U; later source/application resolution must establish their baseline and scope.

## Execution and remaining handoff

```powershell
python -m unittest discover -s tests -p 'test_review.py' -v
python -m tools.check_contracts --examples tests/fixtures/review/cases.json
```

The closed response schema checks structure. Typed helpers check immutable membership and response semantics. Neither layer implements a real review UI, trusted queue retrieval, durable response replay, authority resolution, PostgreSQL transactions or notification transport. All examples are synthetic; no personal tasks or real reviews are imported.
