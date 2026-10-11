# Typed relationship storage

M3B-01 adds [immutable storage values](../src/application/relationship_storage.py),
an [owner-only PostgreSQL port](../src/adapters/postgres_relationships.py) and
[forward migration 013](runtime-migrations/013_relationship_storage.sql).
The fourteen-step schema is `0.9.0-relationships`: 73 domain tables, 178 foreign
keys and the existing three migration metadata tables. The thirteen previous SQL
hashes remain unchanged. Existing rows retain NULL runtime metadata; the new port
does not infer that those legacy rows satisfy typed admission.

Accepted generation rules retain the complete typed rule, explicit field bindings,
essential facts, target obligation kind, source/target TaskType versions, template
version and acceptance reference. Registration requires an exactly matching cached
immutable Git definition envelope. Its body is the rule storage payload with the
three explicit definition references. Template defaults never supply acceptance.

The independently resolved `authority_record` must match the authenticated USER
principal, registered provider/scope/account, USER source evidence and exact
`relationship_storage` kind/payload hash. Its stored scope hash must match too;
expired grants cannot authorize new writes. The repository neither accepts
authority registrations from request JSON nor exposes a public setup endpoint.
This internal authority annotation does not change any frozen M2 contract.

Concrete links retain typed endpoints, exact Task/stage revisions, relationship
revision and optional exact originating rule version. Completion order, start
prerequisite, soft sequence and parent/stage membership remain separate kinds.
Generation direction comes from the rule's source/target types. A generation rule
from lab to preparation can coexist with preparation-before-lab ordering. No
generation occurrence or counterpart Task is created by either storage method.

`register_rule` is an owner-only configuration/cache registration operation.
`append_relation_in_transaction` is an internal participant in the caller's
schema-checked transaction. The enclosing trusted coordinator must resolve the
accepted effect, create its matching receipt and exact TASK_RELATION audit change,
publish the store epoch and commit or roll everything back together. This port
requires the owner role, current migration history, source-backed scope, matching
receipt/audit and existing owned endpoint revisions; it never independently
publishes a receipt or epoch. Command transport support for relationship mutations
is not supplied by this card.

Relation revisions must advance by one. History is append-only; reads may select
an exact revision or the latest, with principal and account-scope checks. Rule
registration is idempotent for identical bytes. Editing or disabling a new rule
version does not rewrite old instances or automatically recreate counterparts.
The enclosing transaction remains responsible for command replay handling.

Run the synthetic checks:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_relationship_storage.py -v
.venv/Scripts/python.exe tools/verify_relationship_storage.py
```

The native verifier uses only its own loopback PostgreSQL database and synthetic
Git objects. It checks prefix upgrade, reverse directions, exact authorization,
invalid targets, history, revisions and rollback. All databases and server
processes are cleaned up. [M3B-02 graph validation](RELATIONSHIP_GRAPH_VALIDATION.md)
provides a portable structural gate. Active-rule selection/retroactive edit
policy, outbox, counterpart generation, cascades and Planner enforcement are later
cards. No personal rules are activated.
