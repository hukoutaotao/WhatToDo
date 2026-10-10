# Non-secret runtime configuration

M3A-03 supplies a loader, immutable snapshots and a synthetic example. It does
not instantiate adapters, activate personal profiles or authorize Task writes.

Run `.venv\Scripts\python.exe tools/check_runtime_config.py` to validate the
example and print a summary without definition bodies or credential values.
Explicit `--override` and `--definition-root` arguments are available.

Precedence is the base JSON file followed by one explicitly named override.
Objects merge recursively; arrays and scalar values replace their base values.
There is no implicit local-file discovery. Environment variables only supply
values for named secret references; they cannot override policy or definitions.
Relative definition paths remain anchored to the base file's directory, even
when the override lives elsewhere, unless a trusted definition root is supplied.

The planning timezone is Asia/Shanghai. All seven non-clock adapter roles must
be present with DISABLED, FAKE or LIVE mode; the state store cannot be disabled.
Disabled or fake optional adapters need no credentials. A configured secret
reference for a LIVE adapter must resolve to a nonblank environment value.
LIVE state storage requires an explicit reference for its connection value.
Other LIVE roles may represent local implementations without credentials;
their eventual adapter factories must validate provider-specific requirements.
Successful loading alone cannot prove a provider is configured or reachable.

Each definition reference pins kind, ID, version, path and the SHA-256 of its
complete envelope, serialized as sorted-key, compact UTF-8 JSON without NaN.
The envelope contains `kind`, `id`, `version` and an object `body`. Paths must
remain within the selected root. Only one active version per kind/ID is allowed.
Bodies are retained as detached data, not executed, interpreted as grants or
treated as a frozen machine Profile schema. Changing a body requires updating
its explicit pin; the loader neither approves the change nor migrates Tasks.

Duplicate JSON keys, oversized files, invalid encoding, unknown fields, identity
or hash mismatches and unavailable enabled credentials fail with stable error
codes. Config objects retain references, never credential values. Errors and
the CLI summary omit input paths, definition bodies and secret values. Personal
retention, reviewed activation and live adapter setup remain later tasks.
