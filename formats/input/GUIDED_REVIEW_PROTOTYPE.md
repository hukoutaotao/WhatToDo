# Offline Guided Review Prototype

M2-15.a provides provider-independent [presentation/input helpers](../../src/application/guided_review.py) and a [synthetic console demo](../../tools/review_demo.py). This is an offline development surface, not the user's selected real channel, an authenticated session or a persistent response handler. It builds on the [review contract](REVIEW_BATCH_CONTRACT.md) and [authority boundary](COMMAND_AUTHORITY_CONTRACT.md).

Run in the selected local toolchain:

```powershell
.\.venv\Scripts\python.exe tools/review_demo.py
.\.venv\Scripts\python.exe tools/review_demo.py --batch-demo
.\.venv\Scripts\python.exe tools/review_demo.py --interactive
```

The demo displays every Task and pending candidate before input. Higher importance changes order, not membership. Human prompts accept completion words, a single remaining estimate with seconds/minutes/hours, a worked/untouched answer, and optional actual time with an explicit “本次新增” or “累计” measure. Users do not write JSON. Approximate text such as “约40分钟” remains a user estimate; a range or missing unit requires clarification. Blank/unknown fields do not inherit displayed values. Explicit completion becomes canonical remaining zero only in the existing domain assessment, without inventing actual work.

Batch input first selects exact displayed task numbers, then separately asks whether remaining estimates are unchanged, completion states are unchanged and the user did no work. Members bind frame/task revisions and original estimate identity/value. Missing estimates do not cause scope narrowing; known worked/stale/conflicting members invalidate the whole batch during domain assessment. Candidate confirm/reject choices are proposed review decisions, never a direct Task mutation.

`present_review` captures full membership and a scope fingerprint; `prepare_response` rejects a changed current frame, preserves explicit submission and emits the existing review-response contract. A fingerprint is an identity check, not an authorization grant. A transport must capture the raw user statement separately, independently bind caller identity, run domain assessment/current-state checks and commit effects transactionally. Invalid or ambiguous guided fields keep the response unsubmitted for clarification; valid partial explicit submissions remain incomplete until all required answers resolve. Raw input is never a serialized authority grant.

The console uses UTF-8 and renders external title controls as visible escapes. It does not execute source text or hide other rows. Duration parsing is deliberately bounded to short guided fields and whole seconds; unsupported wording stays unresolved. This is not a general natural-language interpreter. Domain code/ports remain provider-independent; no provider or login is chosen by this prototype.

Verification:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_guided_review -q
```

Twelve methods cover full membership, partial/default silence, explicit completion without fabricated actual work, separate remaining/incremental/cumulative meaning, ambiguity/conflicts, exact batch observations, missing/worked members, stale frames, external callers and display controls. Scripted and actual stdin-driven individual/batch runs have [demo](../../reports/acceptance/M2-15a-demo.txt), [batch demo](../../reports/acceptance/M2-15a-batch-demo.txt), [interactive](../../reports/acceptance/M2-15a-interactive-demo.txt) and [interactive batch](../../reports/acceptance/M2-15a-interactive-batch-demo.txt) transcripts. Input fixtures contain only synthetic statements.

The full offline suite passed 260 methods at this development checkpoint. The prior [native toolchain report](../../reports/acceptance/M2-16a.json) retains its earlier 248-method/native migration checkpoint rather than being relabeled by these UI-only checks. No real user/profile/source/Task/Calendar, authenticated HTTP endpoint, canonical/database mutation or operating transport was activated.
