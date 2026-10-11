# Authenticated prototype command transport

M3A-16 exposes the existing PostgreSQL handlers through a loopback HTTP API.
The [shared application request boundary](../../src/application/command_transport.py),
[HTTP adapter](../../src/adapters/prototype_http.py),
[bounded envelope codec](../../src/adapters/prototype_codec.py) and
[handler router](../../src/adapters/postgres_transport.py) remain separate.
This is the prototype transport choice; n8n remains the sole workflow platform.
Live user channels, real credentials and personal activation are still deferred.

## Shared machine wire

A future n8n HTTP request and native fixtures use the same UTF-8 JSON envelope:
`POST http://127.0.0.1:<bound-port>/v1/commands`,
`Content-Type: application/json`, and a separate `Authorization: Bearer <token>`
header. Token values never belong in request JSON, source records or results.
No ordinary user is asked to author these envelopes.

The version is `0.1.0-prototype-request`. Every envelope has exactly
`schema_version`, `operation`, `request_id`, `correlation_ref`, `payload` and
`parameters`. Payload is the exact input text/JSON string; it is not reparsed
and reserialized before handler admission. Receipt/resolution control operations use null; QUERY_STATE carries exact query JSON text.
Original command/reply IDs must equal request_id where an input carries one.
Changing correlation metadata does not replace canonical command identity.

| Operation | Payload | Exact parameters |
| --- | --- | --- |
| CREATE_TASK | Frozen single-user CREATE_TASK Command JSON text | expected_store_revision, audit_id |
| PATCH_TASK | Opt-in task-fact-patch JSON text | expected_store_revision, audit_id |
| COMPLETE_TASK | Frozen single-user completion Command JSON text | expected_store_revision, audit_id |
| CANCEL_TASK | Frozen single-user cancellation Command JSON text | expected_store_revision, audit_id |
| REPORT_WORK | Opt-in work-report JSON text | expected_store_revision, audit_id |
| RESOLVE | Opt-in resolution-intent JSON text | source_ref |
| RESOLVE_CREATION | Original natural/guided user text | source_ref, session_id, desired_task_id, input_mode (NATURAL/GUIDED) |
| CLARIFY | Opt-in clarification-reply JSON text | source_ref |
| RESOLUTION_GET | null | session_id, revision (null means current) |
| REFRESH_RESOLUTION | null | session_id, expected_revision, scope_hash |
| RESOLUTION_HANDOFF | null | session_id, revision, scope_hash, authority_ref |
| LOOKUP_COMMAND | null | empty object; request_id identifies the canonical command |
| QUERY_STATE | Opt-in read-query JSON text (8 KiB maximum) | empty object; full Task reference scope required |

For example, the machine completion envelope is shaped as follows. All IDs and
facts shown are synthetic and need independently registered authority before
publication:

```json
{
  "schema_version": "0.1.0-prototype-request",
  "operation": "COMPLETE_TASK",
  "request_id": "synthetic-completion",
  "correlation_ref": "synthetic-attempt",
  "payload": "<exact supported frozen Command JSON text>",
  "parameters": {
    "expected_store_revision": 7,
    "audit_id": "synthetic-completion-audit"
  }
}
```

Unknown operations/versions/fields, duplicate keys, malformed/nonfinite JSON,
invalid action effects, principal mismatches and revision coercion fail before
opening the backend or invoking a handler. No arbitrary SQL, aggregate writes,
grants, caller objects, database targets or provider operations are exposed.

## Independent authentication and scope

CredentialAuthenticator receives a separate immutable trusted registry, an
injected clock and SHA-256 hashes of opaque URL-safe 32-256 character tokens.
It compares hashes with compare_digest and requires active credentials within
their issued/expiry interval. A credential binds one principal, USER_COMMAND
origin, an explicit operation set and an optional Task-ID allowlist. Duplicate
hashes with different identities are invalid configuration. Synthetic fixture
tokens are test data; this module does not provision live credentials.

Payloads cannot supply caller/authentication flags. Their principal must match
the authenticated credential. Narrow Task-ID credentials route only listed
literal mutation targets; reference/clarification/history/receipt operations
require a credential with unrestricted routing scope. This prevents a narrow
credential from discovering or choosing another Task through a name/session.
Unrestricted routing still grants no domain authority.

Backend source/account scopes are selected per authenticated principal; another
principal's registered source binding is not shared. Existing exact Task grants,
resolved manual intents, schema/reference checks, immutable source provenance,
Task/store CAS, full audit and command receipts remain mandatory. The router
cannot register authority or import provider data. Original user inputs for
normalization/clarification must already exist in the independently scoped
source repository; exact bytes/PRESENT USER state/capture time are checked.
The current freeform instance supports creation; other command classes remain
separate M3A-21 instances.

An authenticated retry still needs a currently valid transport credential.
Canonical owned replay can use a fresh credential for the same principal even
when original domain grants, parser intents or source-account bindings are no
longer available. Wrong principals cannot inspect another user's receipt.

## HTTP bounds and lifetime

make_http_server accepts only 127.0.0.1 and an explicit integer port (0 selects
an ephemeral test port). The standard-library single-request server is a local
prototype, not a deployed user channel. The trusted backend_factory creates and
closes a separate idle/autocommit connection per admitted request. Credential,
operation, principal, Task scope and input checks occur before that factory.

HTTP framing requires exactly one Authorization, Content-Type and Content-Length
header, rejects Transfer-Encoding/chunked input, bounds the envelope at 2 MiB
and requires a complete body within a total five-second monotonic deadline.
Inner inputs retain the frozen codec's 256 KiB bound; creation/resolution/reply
input also keeps its existing 8 KiB bound where applicable. Envelope allowance
covers JSON quoting overhead without widening base contracts. Response encoding
is bounded at 2 MiB. Rejections send typed JSON and close the connection.
A bounded 100 ms discard after an early response avoids Windows resetting a
connection with unread bytes; it performs no parsing or database work.

Request/access logs are suppressed; responses use Cache-Control: no-store.
The API's supported route/method and malformed HTTP failures return redacted
codes rather than raw request/provider/SQL/credential text. No listener remains
running after the verifier or tests finish.

## Result meaning and minimal projection

`0.1.0-prototype-response` has exactly schema_version, request_id, correlation_ref,
status, code, next_action and data. Unidentified rejected input uses null request
ID and a fixed server correlation. Success data is a closed allowlisted receipt,
creation acknowledgement, work settlement, clarification frame view or resolution
handoff; the kind must match the called operation. Missing facts remain PENDING,
not an accepted Task. Frame views expose needed choices/known fields/questions
and revision/hash, excluding raw source/immutable frame bytes/internal pending
proposal JSON. Work settlement excludes hidden raw report bodies. Receipts and
handoff identifiers are references, not independent permission.

| Semantic status | HTTP | Next action |
| --- | --- | --- |
| SUCCESS | 200 | NONE; inspect the domain code (for example PENDING_DETAILS) |
| PERMANENT | 400 by default | CORRECT_REQUEST |
| CONFLICT | 409 | RESOLVE_CONFLICT |
| RETRYABLE | 503 | RETRY_LATER, preserving command identity |
| UNKNOWN | 202 | RECONCILE through owned lookup/retry |

Authentication rejection uses 401; insufficient transport scope uses 403.
HTTP framing/size/route errors retain their corresponding 400/408/411/413/415/
404/405 codes. Authentication does not translate an unknown outcome into failure.
If backend exit or result serialization fails after possible publication, the
response is UNKNOWN with no data or raw exception. A lost network response can
also follow commit; consumers must reconcile the same original command ID,
not generate a replacement action. The API does not automatically retry writes.

## Reproduce and continue

```powershell
.venv/Scripts/python.exe -m unittest tests.test_command_transport -q
.venv/Scripts/python.exe tools/verify_command_transport.py
.venv/Scripts/python.exe tools/verify_package_install.py
```

Twenty-nine focused methods and 525 full regression methods pass.
[Native transport acceptance](../../reports/acceptance/M3A-16.json) passes 23
checks over actual loopback HTTP and isolated PostgreSQL, including every
existing mutation handler, owned replay/lookup, normalization/follow-up/handoff,
refresh/stale-answer rejection, per-principal source scopes, no-grant rejection,
precommit rollback/retry and unknown postcommit result recovery. Both the final
HTTP server and owned PostgreSQL cluster stopped; all databases were dropped.

[Clean offline installation](../../reports/acceptance/M3A-16-package.json)
passes authenticated routing, unauthenticated rejection and explicit absent
optional-driver results outside the checkout. Sixty modules, 38 selected schemas
(30 base plus eight opt-in) and all 61 installed Python files are verified.
The two new extension contracts have no database owners: the existing twelve
SQL steps, 72 domain tables/176 FKs, three metadata tables and 91 baseline pins
remain unchanged. M3A-17 Task/history read models are next; complete runtime,
live n8n/provider integration, planner, learning and deployment remain open.

## Read-model extension

[M3A-17](../../database/READ_MODELS.md) adds QUERY_STATE and the closed READ_PAGE
success type without expanding any existing explicit credential operation grants.
The factory injects an independent stable `read_cursor_key`; absence returns
READ_SERVICE_UNCONFIGURED. Account scopes remain filtered by authenticated
principal. Task/history/pending pages retain original version references, states
and query/principal-bound continuations across restart and concurrent changes.
See the read-model handoff for exact filters, coverage, lifetime and size bounds.
