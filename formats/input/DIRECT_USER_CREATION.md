# Direct-user task creation input

This is the M3A-21@CREATE_TASK instance of the repeat-per-command-class card.
The [normalizer](../../src/application/direct_creation.py) accepts bounded
Chinese creation phrases or textual guided fields, emits the unchanged frozen
pending Candidate envelope and prepares the existing manual-creation handoff.
It does not select a real transport, mint an authority grant, resolve Course
names, choose defaults, confirm Candidates or write Tasks.

## User input and supported meaning

An explicit supported example is:

```text
新增任务：阅读论文，必须完成，重要性4，难度3/2/3，剩余约40分钟，领域学习
```

Supported prefixes include 新增任务、添加任务、创建任务、新建任务、加个任务
and 记一个任务, with optional 请/帮我 and 一个 where applicable. The first
segment is the title; commas, semicolons or newlines separate labelled fields.
Quotes `“…”`, `"…"` or `「…」` explicitly retain a literal title, including commas
and words that would otherwise look like additional commands. Titles are
trimmed for the normalized value; the exact original bytes remain retained.

| Field | Supported input | Result |
| --- | --- | --- |
| Importance | 重要性4, scores 1–5 | Explicit importance only |
| Requiredness | 必须完成/必须做/必做/必须 or 可选/非必做/自设/不是必须 | REQUIRED or OPTIONAL |
| Difficulty | 难度3/2/3, full-width slash, or 难度323 | Thinking/repetition/new learning, in that order, all 1–5 |
| Remaining | 剩余约40分钟 or 剩余时间1.5小时 | Integral seconds for user U, not original total or actual work |
| Domain | 领域学习/运动/生活/其他 | study/exercise/life_administration/other |

The guided form accepts exact text answers under title, importance,
requiredness, difficulty, remaining and domain. Users fill separate prompts;
`guided_message` serializes those answers internally, preserving whitespace and
unknown answers. Users never need to write JSON. Empty/不知道/不确定/暂不清楚/
暂不回答/跳过 remain unknown. Explicit unknown U becomes null in the manual
command; omission remains omission; 0 is a known estimate and implies no
completion or actual work. A single duration can have decimals if its seconds
are integral. Ranges, unitless estimates, negative/nonintegral seconds and
compound durations require clarification.

Unsupported prefixes, negation/conditional phrases, duplicate fields, partial
ratings, extra requirements, unquoted relative dates or compound actions,
pronoun references, question phrasing and unmatched quotes remain unresolved.
Duplicate identical values also need clarification; no last-value precedence
is introduced. Unsupported fields are never silently dropped into an executable
command. Deadline interpretation and EXPIRING conditions require later command
classes/reference resolution rather than a guessed due or condition ID.

## Independent context, source and proposal

The constructor accepts independently supplied typed `UserInputBinding` entries
mapping an authenticated principal to its provider/account SourceScope. Neither
the raw message nor guided fields may construct the caller or that registry.
Each parse requires an authenticated USER_COMMAND CallerIdentity, a present
immutable USER SourceRecord matching that binding, exact statement bytes/hash,
known nonfuture capture time and supported source schema. Other accounts,
external/unauthenticated callers, malformed UTF-8, controls in titles and
oversized input fail explicitly. Input is bounded to 8192 bytes and titles to
500 characters. No input is executed as code.

Use the retained canonical SourceRecord returned/read by the evidence repository
when a capture already exists. Its original capture time identifies the
statement; a retry's arrival time must not replace it. Guided source bytes bind
the entire serialized answer set, not only its title or an unrelated statement.

`CreationProposal` retains the exact statement/source, principal, mode,
closed-schema Candidate, explicit creation facts, unknown fields, issues and
missing essential fields. Confidence reports parsing certainty, never authority.
The Candidate stays PENDING with no accepted authority/Task ID. Domain is a
separate explicit application creation fact; it is not hidden inside the frozen
Candidate's closed proposed_fields. Returned dictionaries are detached.

`normalized` means the supported requested action and supplied fields are clear.
It does not imply all essential Task metadata is known. `ready_for_creation`
also requires explicit title, domain, importance, requiredness and all three
difficulty scores. No title-only instruction implicitly becomes an OPTIONAL
Task with convenient ratings or domain. Original effort, due, session splitting,
profiles and timestamps remain unknown unless separately supplied/accepted.

## Existing creation service handoff

`manual_handoff(proposal, command_id=..., task_id=..., authority_ref=...,
caller=...)` rechecks ownership, reparses the exact original bytes and compares
the complete proposal fingerprint. Changed facts or unresolved issues cannot
cross the boundary. It then builds the frozen CREATE_TASK Command and exact
ResolvedManualIntent for [manual creation](../../database/MANUAL_TASK_CREATION.md).
Human titles remain labels; independently supplied stable Task IDs identify
records. No provider ID or title is silently promoted to Task identity.

The handoff does not create/register the named root grant. The trusted caller
and authority service still resolves that grant independently from the explicit
original user statement, runs current reference/schema checks and invokes the
existing atomic handler. A clear explicit instruction needs no additional
identical approval question. Missing facts use its durable PENDING_DETAILS path;
conflicting/uncertain input cannot enter that path as a resolved command.

Do not separately enqueue the pending Candidate envelope for a clear direct
command: its resolved command/audit is the canonical path, and a second queue
entry would ask for duplicate confirmation. Uncertain input may use the existing
candidate/source queue with no authority or Task mutation; its original statement
retains the unresolved details. Scoped clarification resumption is M3A-22.

## Executed scope and next consumers

Run `.venv/Scripts/python.exe -m unittest tests.test_direct_creation -q` for the
21 focused methods, and `.venv/Scripts/python.exe tools/verify_direct_creation.py`
for 16 isolated native source/creation/pending/replay checks. The native fixture
supplies authenticated caller/account bindings and exact grants independently,
without live credentials or a model. All its databases are dropped and server
stopped. [Acceptance](../../reports/acceptance/M3A-21-create.json) records the
observed evidence and [installation](../../reports/acceptance/M3A-21-create-package.json)
checks imported behavior outside the checkout.

The [console demo](../../tools/creation_demo.py) supports `--interactive`,
`--guided` and their combination. It uses a synthetic trusted caller/source
fixture, prints ordinary human prompts and never calls SQL. Six archived runs
exercise scripted natural/guided input and actual stdin with complete, unknown,
partial and conflicting answers.

Other M3A-21 command classes remain separate instances, including existing fact,
lifecycle and work-report operations. M3A-22 target resolution/concise follow-up
can consume this first verified instance; authenticated transport still depends
on that service. Full runtime, review loops and real channel activation remain
open. The base 30 schemas, three opt-in extensions, 91 baseline pins and
eleven-step migration plan are unchanged.
