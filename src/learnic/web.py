from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from learnic.bootstrap import (
    setup_configs,
    setup_map_tables,
    setup_routes,
)
from learnic.infrastructure.configs import Configs
from learnic.infrastructure.tasks.broker import broker
from learnic.ioc import setup_providers

API_TITLE: Final = "Learnic API"
API_VERSION: Final = "0.1.0"
API_DESCRIPTION: Final = """
HTTP API for the Learnic learning platform.

This document is the **single source of truth for the frontend**: every
request body, response body, status code, and error shape that the SPA
needs is described here. Anything not in this schema is not part of the
public contract.

## Authentication

The API authenticates browsers exclusively through HttpOnly cookies set
by the auth flow — there is no `Authorization` header path:

- `accessCookie` (`access_token`, path `/`) — sent on every protected
  request. Lifetime is short; rotate via `POST /auth/refresh` when a
  401 `InvalidToken` lands.
- `refreshCookie` (`refresh_token`, path `/auth/refresh`) — used only
  by `POST /auth/refresh` and `POST /auth/logout`.
- `signupSessionCookie` (`signup_session`, path `/auth`) — installed by
  `POST /auth/register` and polled by
  `GET /auth/email-verification/wait` to auto-login the registration
  tab once the user clicks the verification link.

Browsers handle these cookies automatically; SPAs only need
`fetch(..., { credentials: "include" })` (or the equivalent in their
HTTP client). Mobile / non-browser clients should persist the
`Set-Cookie` values and replay them.

## Active sessions

Every refresh-token family (one per device-login) is denormalised
with the IP, raw `User-Agent`, and a parsed short device label
captured at issue/rotation time. Endpoints:

- `GET /auth/sessions` — list every active session for the current
  user. The session matching the caller's own refresh cookie is
  flagged with `is_current = true` so the SPA can render it as
  'this device' and warn before letting the user revoke it.
- `DELETE /auth/sessions/{session_id}` — revoke a specific session.
  When the targeted session is the caller's own, auth cookies are
  cleared on the response and the in-flight access JTI is added to
  the denylist; other devices keep their cookies but their next
  refresh fails with `InvalidToken`. Cross-user or unknown ids
  return HTTP 404 `EntityNotFound` without leaking which case
  applies.

`POST /auth/logout` and `POST /auth/logout-all` continue to work as
the "sign out this device" / "sign out everywhere" coarse-grained
flows; the `/auth/sessions` endpoints are the per-device alternative
for surfacing a security-settings UI.

## Error responses

Every error this API can produce is documented per-operation under the
appropriate status code and follows one of three shapes:

- **422 `FieldError`** — value-object invariant violated. Body is
  `{"error": "<ErrorClassName>", ...public_attrs}` where extras carry
  context (`field`, `limit`, `reason`, ...). Typed via
  `FieldErrorResponseModel`.
- **404 `EntityNotFound`** — body is
  `{"error": "EntityNotFound", "entity_id": "<uuid>"}`.
- **401 / 403 / 409 named errors** — body is
  `{"error": "<ClassNameWithoutErrorSuffix>"}` (e.g.
  `"InvalidCredentials"`, `"InvalidToken"`, `"EmailAlreadyRegistered"`,
  `"EmailNotVerified"`).

Validation failures from Pydantic (request body type/length) come back
as the standard FastAPI 422 envelope (`{"detail": [...]}`); domain VO
violations come back as the `FieldError` shape above. Both share the
same status code; clients should branch on the response body.

## WebSocket channels

OpenAPI 3 does not model WebSockets, so this section is the contract
for the project's WS endpoints. They share authentication and
close-code conventions but differ in direction and payload shape.
None of them appear under `paths` in this schema; treat the prose
below as authoritative.

### Authentication and close codes

All channels reuse the standard `accessCookie` HttpOnly cookie —
browsers send it on the upgrade handshake automatically. The server
validates the cookie *before* `accept`, so authentication failures are
delivered as a close frame, not as a message. Close codes used by the
WS layer:

- `4401` — missing or denied access cookie.
- `4403` — authenticated, but not authorised (e.g. not the product
  author).
- `4404` — target resource does not exist.

There is no server-side event buffering or replay. On reconnect the
client refetches initial state via REST and re-subscribes — events
emitted while disconnected are lost by design.

### `WS /products/{product_id}/events` — unified product deltas

Read-only push of every per-product delta — product metadata,
cover, status, webinar defaults, Q&A, collaboration lifecycle,
role catalogue, **and** course-content edits (modules, lessons,
blocks, releases, draft reset) when the product is a course.
Subscribers must hold `read_product` on the target product —
the product owner (short-circuited as having every permission)
and any active collaborator whose grants transitively include
`read_product` (every editor / manager permission does).
Non-authorised callers get `4403`. Webinar products see product
events only; course-content `kind` values are emitted exclusively
for products that carry the `has_course_content` capability.
Cohorts (and their schedules / sessions) are intentionally not
covered yet.

Bootstrap by fetching every REST resource the SPA renders from
the channel before opening the socket: `GET /products/{id}`,
`GET /products/{id}/qa` (if Q&A is shown),
`GET /products/{id}/collaborations` (if the team tab is shown),
and — for courses only —
`GET /products/{id}/content/draft` and
`GET /products/{id}/content/releases`.

**Server → client envelope.** Both event families share one shape;
`kind` is the discriminator declared on each member of either
the `ProductPayload` or `ContentPayload` union (one dataclass
per kind).

```json
{
  "kind": "<Payload.KIND>",
  "product_id": "<UUID>",
  "actor_id": "<UUID>",
  "payload": { ... },
  "occurred_at": "<ISO 8601>"
}
```

**Product `kind` values** (`ProductPayload` union):

- Metadata: `name_changed`, `description_changed`,
  `duration_changed`, `price_changed`.
- Cover: `cover_changed`, `cover_removed`.
- Status: `published`, `archived`, `unarchived`, `deleted`.
- Webinar defaults: `webinar_defaults_updated`.
- Q&A: `qa_added`, `qa_question_changed`, `qa_answer_changed`,
  `qa_reordered`, `qa_deleted`.
- Collaboration: `collaboration_invited`,
  `collaboration_accepted`, `collaboration_declined`,
  `collaboration_revoked`, `collaboration_grants_updated`.
- Role catalogue: `role_created`, `role_updated`, `role_deleted`.
- Tags: `tags_changed`.

`payload` carries id-level fields plus the new value when trivial
(e.g. `name_changed` → `{"name": "..."}`); for non-trivial changes
the client should refetch the affected resource via REST.
`price_changed` carries `{"amount": <int>}` — the new price in
minor units (kopecks for RUB); currency is implicit (account
currency, RUB-only at this phase). The SPA can apply it in place
without a REST refetch.
`webinar_defaults_updated` is emitted by the PUT-style replace of
all webinar defaults and carries the full new snapshot —
`total_lessons` (int), `default_duration_minutes` (int),
`allow_recording` (bool), `default_max_participants`
(int | null), `default_stream_url` (string | null),
`access_window_minutes` (int | null) — so the SPA can apply the
change in place without a REST refetch.

`collaboration_*` events carry
`{"collaboration_id": "<UUID>", "collaborator_id": "<UUID | absent>",
"invited_email": "<string | absent>"}`. `collaboration_id` is
always present; `collaborator_id` is set on
`collaboration_invited` for by-user invites, on every
`collaboration_accepted`, and on `collaboration_revoked` /
`collaboration_grants_updated` when the affected row carries one;
`invited_email` appears only on `collaboration_invited` for
by-email invites that have not yet been accepted. SPA action per
kind:

- `collaboration_invited` — append the row to the collaborators
  list (refetch by id from
  `GET /products/{product_id}/collaborations` when the row is
  not already in cache).
- `collaboration_accepted` — flip the row to active; if the
  row was a by-email invite (`collaborator_id` was previously
  absent) refetch the collaborator profile.
- `collaboration_declined` — flip the row to declined (or
  remove from the open list, depending on the SPA's filter);
  no email is sent.
- `collaboration_revoked` — remove / grey out the row; when
  `payload.collaborator_id` matches the current user, also
  refetch `…/collaborations/me/permissions` to drop UI gating.
- `collaboration_grants_updated` — when
  `payload.collaborator_id` matches the current user, refetch
  `…/collaborations/me/permissions`.

`role_*` events carry the full role projection on
`role_created` / `role_updated` (same shape as `RoleSchema` from
`GET /roles/{id}` — `oid`, `product_id`, `name`, `description`,
`position`, `permissions[]`, `created_by`, `created_at`,
`updated_at`) so the SPA can splice or replace the row in its
catalogue without an extra REST round-trip. `role_deleted`
carries only `{"role_id": "<UUID>"}` — the SPA drops the row by
id. Crucially, `role_updated` doubles as a permission-change
signal for every collaborator that holds this role: the SPA must
recompute their effective permissions (drop the role from the
local cache, re-derive any UI gating) when the event arrives.

`tags_changed` fires on `PUT /products/{product_id}/tags` and
carries `{"tags": [{"oid": "<UUID>", "name": "<string>",
"color": "<string>"}, ...]}` — the full ordered post-mutation
tag list. The SPA replaces the cached `product.tags` array
verbatim; there are no per-item add/remove deltas because the
product tag set is always rewritten in one shot. Order in the
payload mirrors storage (`product_tags.position` ascending).

**Content `kind` values** (`ContentPayload` union — courses only):

- Module: `module_added`, `module_renamed`,
  `module_description_updated`, `modules_reordered`, `module_deleted`.
- Lesson: `lesson_added`, `lesson_renamed`, `lesson_moved`,
  `lessons_reordered`, `lesson_deleted`.
- Block: `block_added`, `block_updated`, `block_deleted`,
  `blocks_reordered`.
- Release: `release_created`, `draft_reset`.

`payload` is rich enough for the SPA to apply every content `kind`
in place via `setQueryData` without a follow-up REST round-trip.
Container events (`module_added`, `lesson_added`, `block_added`,
`block_updated`) carry a full snapshot of the affected entity in
the same shape as the corresponding `GET /products/{id}/content/draft`
sub-tree — the SPA reuses its existing draft types to splice it in.
Concretely:

- `module_added` → `{"module": {"oid", "title", "description",
  "position", "lessons": []}}`. New modules always have an empty
  `lessons` list; the field is included so the SPA can splice the
  module into its draft cache without first synthesizing the empty
  array.
- `lesson_added` → `{"module_id", "lesson": {"oid", "title",
  "position", "blocks": []}}`. `module_id` is the parent; `lesson`
  matches `CourseDraftLessonSchema`.
- `lesson_moved` → `{"lesson_id", "from_module_id", "to_module_id",
  "position"}`. `from_module_id` is the lesson's previous module so
  the SPA can locate the lesson in its draft cache without a tree
  scan.
- `block_added` → `{"lesson_id", "block": <LessonBlockSchema>}`.
  The block snapshot is the discriminated union over `type`
  (`html` / `katex` / `code` / `rutube_video`) — same field set
  the REST draft endpoint returns for that block type. The SPA
  appends `block` to the parent lesson's `blocks` array.
- `block_updated` → `{"block": <LessonBlockSchema>}`. Full
  post-mutation snapshot; the SPA replaces the block by `oid`.
- `module_renamed`, `module_description_updated`,
  `modules_reordered`, `module_deleted`,
  `lesson_renamed`, `lessons_reordered`, `lesson_deleted`,
  `block_deleted`, `blocks_reordered` all carry the small
  id-level fields needed to patch the cache (titles, ordered
  id arrays, the deleted entity's id).
- `release_created`, `draft_reset` carry `{"release_id", "ordinal",
  "version", "kind"}` — refetch `GET /products/{id}/content/releases`
  for the full release record (notes, released_by, released_at).

Server-side, the two `kind` families originate from independent
publish/subscribe buses (`ProductEventBus`, `ContentEventBus`)
that the WS endpoint fans into a single stream. Cross-family
ordering is not guaranteed — each `kind` drives an independent
slice of the SPA cache, so the SPA must not rely on one family's
event arriving before another's. Client → server messages are not
interpreted yet.

### `WS /users/me/notifications` — per-user notification deltas

Read-only push of notification-panel deltas — new card created,
single card flipped to read, all-read sweep — to the connecting
user. The recipient is derived from the access cookie, so the
client opens exactly one socket and never specifies a user id.

Bootstrap by fetching `GET /users/me/notifications` (and
`GET /users/me/notifications/counters` for the bell badge) before
opening the socket. No replay buffer; on reconnect the client
refetches initial state and re-subscribes.

**Authentication.** Standard `accessCookie` HttpOnly cookie sent
by the browser on the WS handshake. Failure closes with `4401`
before `accept`.

**Server → client envelopes.** The discriminator is `kind`:

```json
{
  "kind": "created",
  "notification": {
    "oid": "<UUID>",
    "kind": "<NotificationKind value>",
    "category": "<NotificationCategory value>",
    "actor": { "oid": "<UUID>", "full_name": "<Last First Patronymic>" },
    "created_at": "<ISO 8601>",
    "read_at": null,
    "details": { "type": "...", ... }
  }
}
```

```json
{
  "kind": "updated",
  "notification": { ... same shape as `created.notification` ... }
}
```

```json
{ "kind": "read", "notification_id": "<UUID>" }
```

```json
{ "kind": "read_all" }
```

**`kind` values** (drawn from `NotificationEventKind`):

- `created` — a fresh notification was persisted; the panel
  prepends the hydrated `notification` view to its list and
  bumps the matching tab counter.
- `updated` — the embedded snapshot of an existing notification
  changed (currently fired when the collaboration referenced by
  an `invite_sent` card transitions to `active` / `declined` /
  `revoked`); the panel replaces the card by `notification.oid`.
  No new row is created and `created_at` is unchanged — only the
  `details.collaboration` snapshot reflects the new state.
- `read` — a single card was flipped to read; the panel removes
  its blue dot by `notification_id`.
- `read_all` — every unread card of the caller was flipped; the
  panel clears all blue dots and zeroes the unread counters.

**Notification `kind` values** (drawn from `NotificationKind`,
inside the `created` / `updated` envelopes):

- `invite_sent` — a collaborator was invited; the panel renders
  the card with Accept / Decline buttons that call the in-app
  endpoints (`POST /collaborations/{id}/accept` /
  `POST /collaborations/{id}/decline`). The card's
  `details.collaboration` snapshot is the single source of
  truth for the resolved / unresolved UI state — the SPA does
  not need to remember the local "I just clicked Accept"
  status across reloads.
- `invite_accepted` — an invitee accepted; the inviter's panel
  shows the new collaborator's avatar + name.
- `invite_declined` — an invitee declined; the inviter's panel
  shows the decliner's avatar + name and an optional Re-invite
  CTA when the recipient still holds `MANAGE_COLLABORATORS`.
- `access_revoked` — a collaborator's active access was revoked;
  the recipient's panel shows the read-only "access revoked"
  card with the revoker's avatar + name.
- `new_login` — a successful login landed on the user's account;
  the recipient's panel shows a security card with the device
  label / User-Agent / IP captured at the HTTP boundary. No
  actor — the card uses a security-shield avatar and reads
  "New login from <device>". Belongs to the `security` tab.

**`details.collaboration` snapshot.** Both `invite_sent` and
`invite_accepted` carry an embedded snapshot of the underlying
`product_collaboration` row at read time:

```json
{
  "status": "pending_invite | active | declined | revoked",
  "accepted_at": "<ISO 8601 | null>",
  "declined_at": "<ISO 8601 | null>",
  "revoked_at": "<ISO 8601 | null>",
  "invite_expires_at": "<ISO 8601 | null>"
}
```

The SPA uses `status` as the single source of truth for the
Accept / Decline UI state — a reload (or an `updated` event)
picks up the latest values, so the client never needs to
remember whether the invitation was already resolved. `null`
on the whole object means the collaboration row could not be
hydrated — treat the invite as unavailable.

`payload`-style data is carried inside `details`; the
`details.type` field discriminates the body shape. Client →
server messages are not interpreted yet — silence is read as
"may break in future" by SPA teams, so do not send anything.

### `WS /users/me/confirm-events` — email-confirmation deltas

Read-only push of email-confirmation events to initiator tabs that
are waiting on a single-token confirmation. Used by `/verify-email`
during signup so the registration tab learns in real time when the
user clicks the verification link on another device, and by future
profile flows that wait on email-confirmed actions (change-email,
delete-account, ...).

**Authentication.** Accepts EITHER `accessCookie` (logged-in users
on profile / danger-zone flows) OR `signupSessionCookie` (the
registration tab that doesn't hold an access cookie yet). Failure
closes with `4401` before `accept`. The channel is keyed by the
resolved `user_id` regardless of which cookie validated.

**Lifecycle.** No replay buffer. Open the socket *before* the
initiator action so a fast confirm cannot land between submit and
subscribe. On reconnect the client should refetch state via REST
(e.g. `GET /auth/email-verification/wait` for signup) — events
emitted while disconnected are lost by design.

**Bootstrap.** None for client-state hydration; the socket reflects
deltas, not state. For signup specifically, the legacy
`GET /auth/email-verification/wait` long-poll endpoint stays as the
authoritative source of "is this tab now logged in?" — it's the only
HTTP call that can install auth cookies on the original tab. Use the
WS push as the *trigger* to call `/wait` once instead of polling.

**Server → client envelope.**

```json
{
  "kind": "<ConfirmEventKind value>",
  "purpose": "<EmailTokenPurpose value>"
}
```

**`kind` values** (drawn from `ConfirmEventKind`):

- `confirmed` — a single-token email confirmation was consumed and
  committed for the channel's user. `purpose` says which action
  fired (`verify` for email-verification at registration; future
  values mirror new `EmailTokenPurpose` entries). The SPA filters by
  `purpose` and reacts: redirect, finalize signup, refresh a profile
  field, etc.

Client → server messages are not interpreted — silence is read as
"may break in future" by SPA teams, so do not send anything.

### `WS /presence/ws` — bidirectional presence

Holding the socket open marks the connecting user online; closing it
marks them offline. No application-level keep-alive is required —
the server refreshes connection freshness internally on a fixed
interval.

**Client → server** (JSON):

- `{"type": "subscribe",   "user_ids": ["<uuid>", ...]}` — start
  receiving deltas for the listed user ids.
- `{"type": "unsubscribe", "user_ids": ["<uuid>", ...]}` — stop
  receiving deltas for the listed user ids.

**Server → client** (JSON):

- `{"type": "snapshot",  "presences": [{"user_id": "<uuid>",
  "status": "online" | "offline"}, ...]}` — sent right after each
  `subscribe`, with the current state of the just-added ids.
- `{"type": "presence",  "user_id": "<uuid>", "status": "online" |
  "offline"}` — delta pushed when a subscribed user's status
  changes.

Subscriptions are scoped to a single connection. Reconnects must
replay the desired `subscribe` list.

## Money / minor units

Every money amount the API emits or accepts is in **minor units of
the wallet's currency**:

- For `RUB` (currently the only supported currency), 1 RUB = 100
  kopecks. A wallet showing `150_00` holds 150 RUB.
- Floats are never used over the wire. The server represents every
  amount as a JSON integer; the SPA does the same on the way back.
- Negative amounts appear only on signed-`delta` ledger entries
  (debits). Balances (`available`, `pending`) and request bodies
  (`amount`) are always non-negative integers.

The minor-unit convention is documented end-to-end so a generated
SDK can apply the same rule wherever a money field appears.

## Wallets and orders

A wallet is a money holder pinned to one (user, currency) pair.
Every registered user has a `RUB` wallet from sign-up (older users
were backfilled at migration time).

**Purchase flow.** `POST /products/{id}/purchase` debits the
caller's `available` balance by the product's price and creates an
`Order` referencing two freeze rows: one carrying the author's
share, one carrying the platform's commission. Both stay in
`frozen` state until their `unfreeze_at` passes (typically 14 days,
configurable via `WALLET_SALE_HOLD_TTL_SECONDS` for dev). A
periodic worker tick releases ripe freezes into the corresponding
`available` balance.

**Refund flow.** While both freezes are still `frozen`, the buyer
can `POST /users/me/orders/{id}/refund`: the freezes flip to
`cancelled`, the price returns to the buyer's `available`, and the
ledger gets a `refund` row plus two `cancel_freeze` informational
rows. Once either freeze has been released, the window is closed
and the SPA should redirect the user to support.

**Ledger.** `GET /users/me/wallet/ledger` returns every money
event that touched the wallet (`purchase`, `refund`, `freeze`,
`release`, `cancel_freeze`, `topup`, `adjustment`) with a signed
`delta`. Informational events (`freeze`, `cancel_freeze`) carry
`delta = 0` because the money is on the freeze row, not on
`available`. Summing `delta` over all entries of a wallet equals
`available` — an invariant that supports self-checking and audit.
""".strip()

OPENAPI_TAGS: Final[list[dict[str, Any]]] = [
    {
        "name": "Root",
        "description": (
            "Liveness and welcome endpoints. Not protected and not "
            "intended for SPA consumption — present so deployment "
            "tooling (Docker, Caddy) has something to probe."
        ),
    },
    {
        "name": "Auth",
        "description": (
            "Registration, login, token rotation, logout, email "
            "verification, and password reset. All session state is "
            "kept in HttpOnly cookies; the SPA never touches a token "
            "directly."
        ),
    },
    {
        "name": "Users",
        "description": (
            "User profile reads and edits. `GET /users/{user_id}` is "
            "public; everything under `/users/me/...` requires the "
            "`accessCookie` security scheme."
        ),
    },
    {
        "name": "UserSocialLinks",
        "description": (
            "Public list of social-network links per user — `(kind, "
            "url)` pairs displayed on the public profile alongside "
            "website / portfolio / public email. "
            "`GET /users/{user_id}/social-links` is public; "
            "`PUT /users/me/social-links` atomically replaces the "
            "caller's list (order of `items` becomes the persisted "
            "`position`, capped at `SOCIAL_LINKS_MAX_COUNT`)."
        ),
    },
    {
        "name": "UserExperiences",
        "description": (
            "Per-user work / study timeline entries — icon, dates, "
            "title, description, optional source URL. "
            "`GET /users/{user_id}/experiences` is public; "
            "everything under `/users/me/experiences/...` requires the "
            "`accessCookie` scheme and mutates only the caller's own "
            "rows (HTTP 403 `NotResourceOwner` otherwise). The icon is "
            "managed through dedicated `POST` / `DELETE` "
            "`/users/me/experiences/{experience_id}/icon` endpoints."
        ),
    },
    {
        "name": "Products",
        "description": (
            "User-owned learning products — courses and webinars. "
            "`GET /products` (catalog) and `GET /products/{id}` are "
            "public; `POST /products/courses`, "
            "`POST /products/webinars`, `GET /products/mine`, all "
            "PATCH/POST/DELETE state-changing endpoints, require the "
            "`accessCookie` scheme. Mutations are author-only; "
            "non-owners get HTTP 403 `NotResourceOwner`. Drafts can "
            "be deleted; published or archived products must be "
            "archived first (HTTP 409 `ProductNotInDraft`). "
            "Real-time deltas of product metadata and Q&A flow over "
            "`WS /products/{product_id}/events` — see the "
            "**WebSocket channels** section in the API description."
        ),
    },
    {
        "name": "Cohorts",
        "description": (
            "Webinar cohorts — concrete streams of a webinar product. "
            "`GET /cohorts/{id}` and `GET /products/{id}/cohorts` are "
            "public; mutations require the `accessCookie` scheme and "
            "are restricted to either the parent product's author or "
            "the cohort's `host_id` (HTTP 403 `NotResourceOwner` "
            "otherwise). `POST /products/{id}/cohorts` requires a "
            "webinar product (HTTP 409 `NotAWebinar` for courses)."
        ),
    },
    {
        "name": "WebinarSchedules",
        "description": (
            "Recurring schedules attached to a cohort. Adding or "
            "updating a schedule kicks off a TaskIQ-driven "
            "materialisation that expands the rrule into concrete "
            "`WebinarSession` rows. The materialisation is "
            "incremental — past sessions are not retroactively "
            "rewritten on update; the worker resumes from the last "
            "`original_starts_at` cursor. Mutations follow the same "
            "host-or-author authorisation as cohorts."
        ),
    },
    {
        "name": "WebinarSessions",
        "description": (
            "Concrete materialised sessions of a cohort, plus manual "
            "one-offs. `GET` endpoints are public; mutations "
            "(reschedule, cancel, complete, attach/remove recording, "
            "change stream URL) follow the same host-or-author "
            "authorisation as cohorts."
        ),
    },
    {
        "name": "Enrollments",
        "description": (
            "Student enrollments — unified across course and "
            "webinar products. `type` on the response shape "
            "discriminates: `course` carries `course_details` "
            "(product_id, release_id, progress_percent, "
            "completed_at), `webinar` carries `webinar_details` "
            "(cohort_id). "
            "Create: `POST /courses/{course_id}/enrollments` "
            "(course self-enroll; 409 on `ProductDoesNotSupport`, "
            "`AlreadyEnrolled`, or `CannotEnrollInUnreleased"
            "Course`) or `POST /cohorts/{cohort_id}/enrollments` "
            "(webinar; 409 on `EnrollmentClosed`, `AlreadyEnrolled`, "
            "or `CohortFull`). "
            "Caller-scoped: `GET /users/me/enrollments` returns "
            "both types. List by parent: "
            "`GET /courses/{course_id}/enrollments` (author/"
            "`READ_PRODUCT`) and `GET /cohorts/{cohort_id}/"
            "enrollments` (host/author). "
            "Item ops: "
            "`PATCH /courses/{course_id}/enrollments/{id}/progress` "
            "is student-only and auto-completes at 100; "
            "`/complete` and `/refund` are author-only for course, "
            "host-or-author for webinar. No `drop` — walk-away "
            "semantics go through refund (the historical "
            "webinar-only `DROPPED` status was retired)."
        ),
    },
    {
        "name": "CourseReleases",
        "description": (
            "Immutable releases of a course product. A release "
            "snapshots the current draft (modules + lessons + "
            "blocks) into mirror tables, pinning every row to the "
            "new release id. Creating the **first** release also "
            "flips the product's status to ``PUBLISHED`` — courses "
            "are not published any other way (the standalone "
            "publish endpoint refuses for courses with HTTP 409 "
            "``CannotPublishCourseDirectly``). Versions follow "
            "semver: from the previous ``v(M.m.p)``, ``patch`` → "
            "``v(M.m.p+1)``, ``minor`` → ``v(M.m+1.0)``, ``major`` "
            "→ ``v(M+1.0.0)``. The first release starts from the "
            "implicit baseline ``v0.0.0``. All endpoints under "
            "this tag are author-only."
        ),
    },
    {
        "name": "CourseContent",
        "description": (
            "Author-side editing of course content — modules and "
            "lessons inside a course product. All endpoints under "
            "`/products/{product_id}/...` and "
            "`/products/{product_id}/lessons/...` require the "
            "`accessCookie` scheme and are author-only (HTTP 403 "
            "`NotResourceOwner` otherwise). Operations refuse on "
            "webinar products with HTTP 409 `NotACourse`. Content "
            "lives in the product's draft workspace; releases are "
            "introduced in a later phase and snapshot the draft. "
            "Real-time deltas of course-content edits flow over "
            "the unified product channel "
            "`WS /products/{product_id}/events` — see the "
            "**WebSocket channels** section in the API description."
        ),
    },
    {
        "name": "Tags",
        "description": (
            "Globally-shared name + color labels attachable to any "
            "product. Tags are append-only and not author-scoped: "
            "any authenticated user can search the pool, and any "
            "user with `edit_description` on a product can attach "
            "existing tags or mint new ones via the get-or-create "
            "branch of `PUT /products/{product_id}/tags`. "
            "Dedup happens by `slug` (lower-cased, "
            "whitespace-collapsed `name`); two clients typing the "
            "same tag converge on the same row. Color is owned by "
            "the first creator and stored canonical-hex (validated "
            "by `pydantic_extra_types.color.Color`); per-product "
            "overrides are intentionally not supported. Real-time "
            "deltas of a product's tag list flow over the product "
            "channel `WS /products/{product_id}/events` as "
            "`tags_changed` — see the **WebSocket channels** "
            "section in the API description."
        ),
    },
    {
        "name": "Roles",
        "description": (
            "Per-product role catalogue used by collaboration grants. "
            "Two system roles (Commentor, Editor) are seeded by "
            "Alembic and visible inside every product. "
            "Custom roles live inside a single product and are managed "
            "by collaborators with `manage_roles` (HTTP 403 "
            "`InsufficientPermissions` otherwise). Deleting a role "
            "still referenced by any grant returns HTTP 409 "
            "`RoleInUse` — reassign collaborators first. Permissions "
            "carry implicit dependencies (e.g. `edit_modules` implies "
            "`edit_lessons`); the authoriser expands them at check "
            "time, so the persisted permission set may be smaller "
            "than the effective one."
        ),
    },
    {
        "name": "Collaborations",
        "description": (
            "Multi-user collaboration on products. Each collaboration "
            "carries a list of grants `(role, scope, scope_id?)` "
            "where scope is `product` / `module` / `lesson`; resolved "
            "permissions are the union of every grant whose scope "
            "covers the requested target, expanded through the "
            "permission-implication graph. The product author is "
            "short-circuited as having every permission and cannot "
            "be invited as a collaborator. "
            "Two invite paths: `POST /products/{id}/collaborations/"
            "by-user` for already-registered users, "
            "`POST /products/{id}/collaborations/by-email` for "
            "(possibly) unregistered ones — both produce a "
            "`PENDING_INVITE` row and email a link of the shape "
            "`/products/{product_id}/collaboration-invitation/"
            "{collaboration_id}/accept?token=...`. The SPA bounces "
            "unauthenticated users through `/login?next=...` and "
            "POSTs the token to `POST /collaborations/{id}/accept-by-token`. "
            "All collaborator-side notifications (invite, accept, "
            "revoke, grant change, self-leave) are delivered by "
            "email. Real-time deltas of the collaborator list flow "
            "over the product channel "
            "`WS /products/{product_id}/events` to anyone with "
            "`read_product` (every collaborator) — see the "
            "**WebSocket channels** section in the API description "
            "for the full kind list and payload semantics."
        ),
    },
    {
        "name": "Presence",
        "description": (
            "Online-status reads and live push. "
            "`GET /presence/{user_id}` answers a one-off query. "
            "`WS /presence/ws` is a long-lived WebSocket: holding it "
            "open marks the connecting user online; the client "
            "subscribes to user ids of interest and receives "
            "`snapshot` (initial state) and `presence` (deltas) push "
            "messages. Both endpoints reuse the standard "
            "`accessCookie` security scheme. The WebSocket protocol "
            "is documented in full in the **WebSocket channels** "
            "section of the API description above (OpenAPI 3 does not "
            "model WebSockets, so the contract lives there as prose)."
        ),
    },
    {
        "name": "Notifications",
        "description": (
            "In-app notification panel for the bell icon. "
            "`GET /users/me/notifications` returns a cursor-paginated "
            "list, optionally filtered by tab "
            "(`?category=teaching|learning|security|files|jobs|other`). "
            "`GET /users/me/notifications/counters` returns per-tab "
            "totals + unread for the segmented control and the bell "
            "badge. `POST /users/me/notifications/{id}/read` flips "
            "one card to read; `POST /users/me/notifications/read-all` "
            "is the double-check icon. Real-time deltas (new card, "
            "single-read, read-all) flow over "
            "`WS /users/me/notifications` — see the "
            "**WebSocket channels** section in the API description."
        ),
    },
    {
        "name": "Wallet",
        "description": (
            "Per-user money holder. `GET /users/me/wallet` returns "
            "available + pending totals; `GET /users/me/wallet/ledger` "
            "returns the immutable journal of every credit and debit. "
            "All amounts are in **minor units** (kopecks for RUB) — "
            "see the *Money / minor units* section in the API "
            "description for the convention and rationale."
        ),
    },
    {
        "name": "Orders",
        "description": (
            "Purchases of paid products. `POST /products/{id}/purchase` "
            "charges the caller's wallet and freezes the author's and "
            "platform's shares until the refund window closes. "
            "`POST /users/me/orders/{id}/refund` reverses the order "
            "while both freezes are still in `frozen` state — once "
            "either is released by the worker, the refund window has "
            "closed and the buyer is redirected to support."
        ),
    },
    {
        "name": "Dev",
        "description": (
            "Development-only endpoints, registered only when "
            "`APP_ENVIRONMENT=development`. Bypass the missing "
            "payment integration: `POST /dev/wallet/topup` credits "
            "the caller's own wallet; `POST /dev/freezes/release-now` "
            "runs the release worker synchronously instead of waiting "
            "for the next scheduler tick. Absent from prod builds."
        ),
    },
]


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    await broker.startup()
    try:
        yield
    finally:
        await broker.shutdown()


def _create_app(configs: Configs) -> FastAPI:
    setup_map_tables()
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=_lifespan,
    )
    setup_routes(app, configs)
    container = setup_providers(configs)
    setup_dishka(container, app)
    return app


def create_app_production() -> FastAPI:
    return _create_app(setup_configs())


def create_app_tests(configs: Configs) -> FastAPI:
    return _create_app(configs)
