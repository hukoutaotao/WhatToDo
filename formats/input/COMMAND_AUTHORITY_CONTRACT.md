# Command and authority — development draft 0.1.0

Scope: [M2-04.a](../../plan/tasks/M2_CONTRACTS.md#m2-04a). [Command schema](command.schema.json), [pure authorization module](../../src/domain/authorization.py), [synthetic schema cases](../../tests/fixtures/authorization/cases.json) and [regression tests](../../tests/test_authorization.py).

## Independent trust inputs

Command JSON carries a claimed principal/origin and authority reference for traceability. It never constructs CallerIdentity or inserts AuthorityGrant records. A trusted authenticated transport supplies caller context; a trusted instruction/rule/policy resolver supplies registered grants and exact mapped changes. The authorizer compares those independent inputs. A matching string or high external confidence is not authentication/authority. These offline checks do not implement an actual transport/login or a persistent grant store.

An explicit resolved user statement supplies its precise authority without a redundant approval step. Grant bindings cover command ID, concrete targets, expected revisions, actions and exact field values, not just field names. Extra inferred changes, another value for the same field, omitted requested targets or a substituted batch are rejected. Input changes and registered grants retain immutable values; returned field dictionaries are copies.

## Authority matrix

| Trusted origin | Allowed boundary | Required independent evidence |
| --- | --- | --- |
| USER_COMMAND | Exactly resolved creation/update; expiry still follows notice requirements | Registered explicit-statement grant, matched caller/command, exact scope and current state |
| RELATIONSHIP_RULE | Mapped creation only; no completion/cancellation inference | Accepted rule's resolved grant, version/scope, canonical source creation occurrence and essential mapped facts |
| EXPIRATION_PROCESS | EXPIRE_TASK only; no U reset or completion change | Accepted policy grant, latest EXPIRING/INCOMPLETE/ACTIVE state and matching confirmed DELIVERED notice |
| EXTERNAL | Evidence/candidate ingestion only | Cannot authorize a canonical command even if it claims USER or references a known grant |

Rule grants are resolved from an already approved reusable rule; they do not require per-instance user approval. Source creation records come from trusted canonical history, not raw provider discovery. Rule version is retained for scope/audit; the generation occurrence key deliberately excludes version so an edit does not duplicate old targets. Persistent occurrence uniqueness and recursive/typed relation checks remain later work.

Expiration checks require the condition/version/task to match the delivered notice and current state. PENDING/FAILED/UNKNOWN delivery, uncertain conditions, future delivery or a version changed after dispatch cannot authorize EXPIRED. No read acknowledgement is required. Expiry fields are exactly disposition and notice reference; rewriting completion or U is rejected. A normal UPDATE cannot bypass the notice process by setting EXPIRED.

## Handoff and execution

Validate raw JSON with the schema/strict parser, resolve targets and independent authority from trusted ports, then call `authorize` using a current snapshot. The decision includes a deterministic request fingerprint and reason code without submitted values. It does not mutate tasks/grants or prove that a transaction occurred. Persistence must revalidate version/authority and atomically write audit/state; command replay and ambiguous outcomes remain application/database responsibilities.

```powershell
python -m unittest discover -s tests -p 'test_authorization.py' -v
python -m tools.check_contracts --examples tests/fixtures/authorization/cases.json
```

Typed helper inputs require integer ratings/durations and explicit immutable scope. Normal human input remains natural language/guided replies. All caller, grant, creation and notice records in these checks are synthetic; no live identity, actual notification provider or canonical personal Task is exercised.
