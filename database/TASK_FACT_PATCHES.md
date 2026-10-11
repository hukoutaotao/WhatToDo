# Explicit Task fact updates — M3A-13

[Progress](../plan/PROGRESS.md) · [Application](../src/application/fact_patches.py) · [PostgreSQL handler](../src/adapters/postgres_fact_patches.py) · [Atomic publication](ATOMIC_TRANSACTIONS.md)

The handler updates one existing Task from an independently resolved, authenticated user instruction. Its allowlist is title, importance, the three difficulty dimensions, requiredness, expiration condition, user remaining seconds and deadline. Full historical values and per-field user sources remain available. Completion, cancellation, actual work, stage operations, relationships and arbitrary metadata require their own application handlers.

## Contract evolution and consumer impact

The frozen `command 0.1.0-draft` cannot represent deadline updates. Rather than adding unrecognized fields to its payload, this implementation supplies the separate opt-in [task-fact-patch schema](../formats/extensions/task-fact-patch.schema.json), version `0.1.0-task-fact-patch`, and [extension registry](../formats/extension-registry.json). All 30 base schemas, the base registry and 91 generic-baseline pins remain unchanged. Default `load_contract_schemas` continues to load only the base; a caller explicitly chooses [load_supported_schemas](../src/adapters/extension_contracts.py) to enable this extension. Old codecs reject its contract, unknown versions and unknown fields, retaining original input bytes through admission. There is no implicit adapter or conversion to the old command contract.

The application and PostgreSQL fact handler are the extension consumers. Resource hashes, exact supported version, confined extension paths, existing table ownership and package resources are checked by [registry verification](../tools/check_extension_registry.py), focused tests and installed-wheel validation. Database layout and migration receipts do not change: existing normalized due, observation, Task, authority and audit tables own these facts. General parsers, transports and future consumers must explicitly adopt this contract before emitting or executing it.

## Authority and publication

JSON admission supplies no grant. `FactPatchGrant` is independently injected and registered by a trusted resolver/setup helper, with exact command/Task/version/fields, principal, user evidence, issued time and optional expiry. The handler verifies the stored grant body, immutable USER source payload and independently registered account scope. A different field value, forged grant, stale Task revision or stale store epoch fails without mutation. The handler constructs the whole after-image itself; raw transport cannot smuggle additional aggregate changes.

The read frame preserves the original exact course/activity profile and, for an EXPIRED Task, the original notice Task revision. Repeated fact corrections do not move that notice backlink. EXPIRED disposition cannot be undone through a requiredness edit. EXPIRING requires an explicit existing or newly supplied condition; changing an active Task to non-expiring removes the now-inapplicable condition.

An exact short-lived private transaction permit binds the constructed after-image. The coordinator atomically publishes supporting due/remaining rows, the Task revision, provenance, full before/after audit, command receipt and store epoch. Its final CAS and permit check cover concurrent changes after the read frame. Supporting facts are checked against actual SQL rows at append; read-only planned rows cannot bypass publication validation. SQL/transport failure rolls back the whole transaction.

## Time, effort and retained derivations

An explicit RFC3339 instant must include its timezone and retains its original literal, UTC-equivalent instant, offset and microseconds; it receives no date-only policy. A pure date uses the accepted D-075 Beijing 23:59 policy. More than six fractional digits are rejected to avoid lossy PostgreSQL timestamp storage. Relative natural language is left for a later resolver. Explicit `deadline: null` clears the current deadline while retaining prior due rows and revisions. Changing the deadline invalidates the derived overdue assessment to UNKNOWN.

Known U creates an immutable USER_REMAINING observation at the independently resolved source-observed time, linked to the root user grant and transaction. Zero stays distinct from unknown and does not complete the Task; explicit null clears only current U. Total estimates, actual-work observations, stages, lifecycle and scheduling facts stay unchanged. A completed Task cannot acquire unknown or positive U through a fact edit. Revision-specific predictions remain in history and are marked invalid/inapplicable for the new Task revision, requiring new prediction evidence before use.

## Retry and handoff

An owned identical command is rebuilt from its original after-revision and durable annotation, yielding its original receipt even after subsequent edits, resolver removal, grant expiry or restart. Changed semantics, principal, original expected epoch or audit identity conflict; correlation changes are allowed. Retries neither revert the newer head nor duplicate due/remaining facts. Ambiguous commit acknowledgement remains handled by the existing transaction coordinator and durable reconciliation API.

Run `.\.venv\Scripts\python.exe -m unittest tests.test_fact_patches -q`, `tools\check_extension_registry.py`, and the isolated native `tools\verify_fact_patches.py`. Native acceptance uses synthetic principals, sources and grants only. Real course import, live intent resolution and deployment remain later work. Next card: M3A-14 completion/cancellation.
