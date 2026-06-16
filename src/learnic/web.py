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
role catalogue, **and** note-content edits (modules, lessons,
blocks, releases, draft reset) when the product is a note.
Subscribers must hold `read_product` on the target product —
the product owner (short-circuited as having every permission)
and any active collaborator whose grants transitively include
`read_product` (every editor / manager permission does).
Non-authorised callers get `4403`. Webinar products see product
events only; note-content `kind` values are emitted exclusively
for products that carry the `has_note_content` capability.
Cohorts (and their schedules / sessions) are intentionally not
covered yet.

Bootstrap by fetching every REST resource the SPA renders from
the channel before opening the socket: `GET /products/{id}`,
`GET /products/{id}/qa` (if Q&A is shown),
`GET /products/{id}/collaborations` (if the team tab is shown),
and — for notes only —
`GET /notes/{note_id}/content/draft` and
`GET /notes/{note_id}/releases`.

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
- Visibility: `visibility_changed`.
- Q&A: `qa_added`, `qa_question_changed`, `qa_answer_changed`,
  `qa_reordered`, `qa_deleted`.
- Collaboration: `collaboration_invited`,
  `collaboration_accepted`, `collaboration_declined`,
  `collaboration_revoked`, `collaboration_grants_updated`.
- Role catalogue: `role_created`, `role_updated`, `role_deleted`.
- Tags: `tags_changed`.
- Gifts: `gift_issued`, `gift_accepted`, `gift_declined`,
  `gift_revoked`.

`payload` carries id-level fields plus the new value when trivial
(e.g. `name_changed` → `{"name": "..."}`); for non-trivial changes
the client should refetch the affected resource via REST.
`price_changed` carries `{"amount": <int>}` — the new price in
minor units (kopecks for RUB); currency is implicit (account
currency, RUB-only at this phase). The SPA can apply it in place
without a REST refetch.
`visibility_changed` carries `{"visibility": "public" | "private"}`
— the product's new enrollment visibility (orthogonal to lifecycle
`status`; `private` stays catalog-visible but is invite-only, i.e.
self-enroll is refused). Owner-only mutation via
`PATCH /products/{id}/visibility`; the SPA can apply it in place
without a REST refetch.

`collaboration_*` events carry
`{"collaboration_id": "<UUID>", "collaborator_id": "<UUID | absent>",
"invited_email": "<masked string | absent>"}`. `collaboration_id` is
always present; `collaborator_id` is set on
`collaboration_invited` for by-user invites, on every
`collaboration_accepted`, and on `collaboration_revoked` /
`collaboration_grants_updated` when the affected row carries one;
`invited_email` appears only on `collaboration_invited` for
by-email invites that have not yet been accepted, and is **masked**
(`f*****d@domain.com`) — the channel fans out to every READ_PRODUCT
subscriber, so the raw address is never broadcast; it matches the
masked email the REST collaborator list returns. SPA action per
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

`gift_*` events track the product's gift lifecycle so a
collaborator watching the editor's "Gifts" tab sees it update
live. `gift_issued` fires on both the by-user
(`POST /products/{product_id}/gifts/by-user`) and by-email
(`…/gifts/by-email`) invite paths; `gift_accepted` /
`gift_declined` when the recipient resolves the invite;
`gift_revoked` when a manager cancels a still-pending gift. Each
carries only `{"gift_id": "<UUID>"}`; the SPA refetches the
permission-gated list (`GET /products/{product_id}/gifts`)
rather than applying in place. Unlike `collaboration_invited`,
the invitee's email is deliberately NOT on the wire so it never
reaches a collaborator who only has editor access. Expiry of
stale pending invites is swept by a daily cron and is NOT
broadcast — the SPA discovers purged invites on its next refetch.

**Content `kind` values** (`ContentPayload` union — notes only):

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
the same shape as the corresponding `GET /notes/{note_id}/content/draft`
sub-tree — the SPA reuses its existing draft types to splice it in.
Concretely:

- `module_added` → `{"module": {"oid", "title", "description",
  "position", "lessons": []}}`. New modules always have an empty
  `lessons` list; the field is included so the SPA can splice the
  module into its draft cache without first synthesizing the empty
  array.
- `lesson_added` → `{"module_id", "lesson": {"oid", "title",
  "position", "blocks": []}}`. `module_id` is the parent; `lesson`
  matches `NoteDraftLessonSchema`.
- `lesson_moved` → `{"lesson_id", "from_module_id", "to_module_id",
  "position"}`. `from_module_id` is the lesson's previous module so
  the SPA can locate the lesson in its draft cache without a tree
  scan.
- `block_added` → `{"lesson_id", "block": <LessonBlockSchema>}`.
  The block snapshot is the discriminated union over `type` —
  `html` / `katex` / `code` / `rutube_video` /
  `single_choice` / `multi_choice` / `text_input` /
  `file` / `video_file` / `photo_collage` — same field set
  the REST draft endpoint returns for that block type. The SPA
  appends `block` to the parent lesson's `blocks` array. File-backed
  variants carry `file_id` (UUID or `null` if the referenced file
  was purged) plus an optional `title`; `photo_collage` additionally
  carries an `items` array of `{file_id, caption}` entries.
- `block_updated` → `{"block": <LessonBlockSchema>}`. Full
  post-mutation snapshot; the SPA replaces the block by `oid`.
- `module_renamed`, `module_description_updated`,
  `modules_reordered`, `module_deleted`,
  `lesson_renamed`, `lessons_reordered`, `lesson_deleted`,
  `block_deleted`, `blocks_reordered` all carry the small
  id-level fields needed to patch the cache (titles, ordered
  id arrays, the deleted entity's id).
- `release_created`, `draft_reset` carry `{"release_id", "ordinal",
  "version", "kind"}` — refetch `GET /notes/{note_id}/releases`
  for the full release record (notes, released_by, released_at).

Server-side, the two `kind` families originate from independent
publish/subscribe buses (`ProductEventBus`, `ContentEventBus`)
that the WS endpoint fans into a single stream. Cross-family
ordering is not guaranteed — each `kind` drives an independent
slice of the SPA cache, so the SPA must not rely on one family's
event arriving before another's. Client → server messages are not
interpreted yet.

### `WS /products/{product_id}/cursors` — live editor cursors

Bidirectional push of "where is each editor / viewer right now"
deltas for one product. Used by the SPA to render other users'
cursors on the editor surface (field labels, lesson titles, block
inputs, …) and to optionally raise their "what they're doing"
status (`editing`, `typing`, `viewing`, `commenting`, …) next to
the avatar. The server stays semantically dumb: ``field_id`` and
``action`` are opaque strings; the SPA owns the taxonomy.

Authorisation reuses `read_product` — every collaborator whose
grants transitively include `READ_PRODUCT` (owners + every editor
/ manager) can subscribe; non-authorised callers get `4403`. The
product must exist (`4404` otherwise) and the access cookie must
validate (`4401` otherwise) before `accept`.

**Lifecycle and replay policy.** No replay. Immediately after
`accept`, the server pushes a `snapshot` message with every other
user's current cursor (the caller's own cursor is omitted). After
that, the channel is bidirectional:

- The client publishes its own `cursor_at` / `cursor_left`
  messages as the editing user focuses / blurs / types.
- The server fans out other users' deltas (`cursor_at` /
  `cursor_left`) and emits `user_gone` when a user's last
  connection for the product closes.
- Stale cursors (no `cursor_at` from a user for at least 30 s)
  are pruned lazily — the next `snapshot` filters them out. The
  SPA carries its own ~15 s eviction timer per cursor and never
  needs to wait for server-side staleness.

On reconnect, re-open the socket and replay the current
`cursor_at`; the new `snapshot` will hydrate everyone else.

**Client → server** (JSON):

- `{"type": "cursor_at", "field_id": "<str ≤256>",
  "action": "<str ≤64>" | null}` — caller's cursor is now at
  `field_id`. Any subsequent `cursor_at` from the same client
  overwrites the previous entry. `field_id` and `action` are
  opaque to the server; the server only enforces length caps.
  Send periodic refreshes (every ~10 s) while the field stays
  focused so the lazy-staleness window doesn't trip on a quiet
  editor.
- `{"type": "cursor_left", "field_id": "<str>"}` — caller is no
  longer at `field_id`. The server forwards `cursor_left` only
  when its stored entry actually matches both the caller's
  connection and `field_id`; a stale "leave" for a field the
  caller already moved off of is a no-op (the originator silently
  drops it).

**Server → client** (JSON):

- `{"type": "snapshot", "cursors": [{"user_id", "field_id",
  "action", "updated_at"}]}` — sent exactly once, right after
  `accept`. Contains every other live cursor for the product;
  empty list is valid.
- `{"type": "cursor_at", "user_id", "field_id", "action",
  "updated_at"}` — another user's new or refreshed cursor.
  Replace any previous entry for `user_id` in the SPA store.
- `{"type": "cursor_left", "user_id", "field_id"}` — another
  user explicitly left `field_id`. Drop the entry from the SPA
  store.
- `{"type": "user_gone", "user_id"}` — another user's last
  connection for this product closed. Drop every entry for
  `user_id`.

`updated_at` is ISO 8601 UTC. The server never echoes the
caller's own deltas back, so the SPA can publish optimistically
and treat its local copy as the source of truth for its own
cursor.

Field-id and action taxonomies are SPA-owned and intentionally
opaque to the server. The current SPA convention uses dotted,
lowercase keys (`product.title`, `module.<id>.title`,
`lesson.<id>.title`, `block.<id>.body`, `block.<id>.option.<idx>`,
`block.<id>.tab.<idx>.code`, …) and a small action set
(`editing`, `typing`, `viewing`, `commenting`). New keys / actions
do not require backend changes.

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

### `WS /users/me/storage` — live storage-quota meter

Read-only push of the caller's storage-quota pool — plan code,
byte cap, used and remaining bytes — so a quota meter updates the
moment an upload, replace, delete, or reconcile eviction commits.
The quota owner is derived from the access cookie; there is no
path parameter. A collaborator who needs the *note author's* pool
(the one their uploads are charged against) uses
`GET /notes/{note_id}/storage-remaining` instead — this channel
always shows the connecting user's own pool.

**No REST bootstrap is needed.** The server pushes a full
`snapshot` envelope immediately after the handshake, and again on
every reconnect. No replay buffer; the post-reconnect `snapshot`
already reflects everything missed while offline.

**Authentication.** Standard `accessCookie` HttpOnly cookie sent
by the browser on the WS handshake. Failure closes with `4401`
before `accept`.

**Server → client envelopes.** The discriminator is `kind`; both
kinds carry the identical FULL snapshot of the pool (never a
delta), with field names mirroring `NoteStorageRemainingSchema`:

```json
{
  "kind": "snapshot",
  "plan_code": "FREE",
  "storage_bytes_max": 2147483648,
  "storage_bytes_used": 1572864000,
  "storage_bytes_remaining": 574619648,
  "occurred_at": "<ISO 8601>"
}
```

```json
{ "kind": "usage_changed", ... same fields as `snapshot` ... }
```

**`kind` values** (drawn from `StorageQuotaEventKind`):

- `snapshot` — sent once right after `accept` (and after every
  reconnect); the client replaces its meter state wholesale.
- `usage_changed` — a quota-changing operation committed (file /
  video / collage block added, replaced, or removed; lesson,
  module, or note deleted; reconcile-job eviction). Apply exactly
  like `snapshot`.

Every envelope is self-contained — apply directly, no refetch is
ever required. Publish order across concurrent commits is not
guaranteed: keep the envelope with the newest `occurred_at` and
drop older ones. `storage_bytes_remaining` is clamped to `0` —
an over-quota pool (e.g. after a plan downgrade) reports `0`
free, never a negative number.

Client → server messages are not interpreted — silence is read as
"may break in future" by SPA teams, so do not send anything.

### `WS /notes/{note_id}/storage` — live per-note storage panel

Read-only push for the editor's storage card: how many bytes THIS
note's files occupy (`note_storage_bytes_used`) plus the note
author's pool (cap / used / remaining — same fields as
`WS /users/me/storage`). Quota is anchored on the note author, so
collaborators and the author watching the same note see identical
numbers. Events fire on every committed mutation of the AUTHOR'S
pool — an upload into a sibling note moves
`storage_bytes_remaining` here too.

**No REST bootstrap is needed.** A full `snapshot` envelope is
pushed right after the handshake and again on every reconnect.
The REST twin with the same shape is
`GET /notes/{note_id}/storage` (operation `getNoteStorage`).

**Authentication and authorization.** Standard `accessCookie` on
the handshake; the actor must hold `EDIT_LESSONS` on the note —
the same gate as the upload commands. Close codes: `4401`
(missing/denied cookie), `4404` (no such note), `4403` (actor
lacks `EDIT_LESSONS`) — all before `accept`.

**Server → client envelopes.** The discriminator is `kind`; both
kinds carry the identical FULL snapshot (never a delta):

```json
{
  "kind": "snapshot",
  "plan_code": "FREE",
  "note_storage_bytes_used": 367001600,
  "storage_bytes_max": 2147483648,
  "storage_bytes_used": 1879048192,
  "storage_bytes_remaining": 268435456,
  "occurred_at": "<ISO 8601>"
}
```

```json
{ "kind": "usage_changed", ... same fields as `snapshot` ... }
```

**`kind` values** (drawn from `StorageQuotaEventKind`):

- `snapshot` — sent once right after `accept` (and after every
  reconnect); the client replaces its card state wholesale.
- `usage_changed` — a quota-changing operation committed anywhere
  in the author's pool. Apply exactly like `snapshot`.

`note_storage_bytes_used` counts files referenced from this
note's blocks only (file / video-file / photo-collage),
deduplicated, soft-deleted excluded, cover not counted — so
`note_storage_bytes_used <= storage_bytes_used` always holds.
Same staleness rule as the per-user channel: keep the envelope
with the newest `occurred_at`, drop older ones.

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

## Pagination

List endpoints use **offset-based** pagination via two query
parameters:

- `offset` — items to skip; integer `>= 0`, default `0`.
- `limit` — page size; integer `1..100`, default `20`
  (`DEFAULT_LIMIT` / `MAX_LIMIT` in
  `application/common/pagination.py`).

Index endpoints that expose a total (the marketplace product list
and the blog-post admin list) return the unpaginated count in the
**`X-Total-Count`** response header, so the SPA can render page
controls without a second request.

Free-text search, where offered, takes a `q` query parameter bounded
to `2..100` characters (`SEARCH_QUERY_MIN_LEN` /
`SEARCH_QUERY_MAX_LEN`); shorter strings are rejected at the boundary
to keep single-character lookups off full-table scans.

**Cursor exception — notifications.** `GET /users/me/notifications`
is **cursor-paginated** instead: pass the opaque `cursor` from the
previous page's `next_cursor` (omit it for the first page) plus a
`limit` (`1..100`). The response carries `next_cursor`, which is
`null` once the tail is reached. Offset/limit does not apply here.

## File uploads

Routes that accept binary content take a `multipart/form-data` body
with a single file field (FastAPI `UploadFile`).

- **Size caps are per-call-site, never global.** Every upload route
  enforces its own ceiling via `open_upload(file, max_bytes=...)`;
  the named constants live in
  `presentation/http/common/upload_limits.py` — avatar `5 MB`, user
  cover `10 MB`, CV-timeline icon `2 MB`, product cover `10 MB`,
  lesson file block `50 MB`, lesson video block `1 GiB`,
  photo-collage item `80 MB`, blog image `10 MB`, blog video
  `1 GiB`, blog-post cover `10 MB`.
- **Over-cap** uploads return **`422`** with body
  `{"error": "FileTooLarge", "limit": <max_bytes>}` so the SPA can
  show the exact ceiling.
- **Wrong content type** returns **`415 Unsupported Media Type`**
  with body `{"error": "WrongFileContentType", "expected_prefix":
  "image/"|"video/", "actual": "<mime>"}`. Image routes require an
  `image/...` type; video routes require `video/...`.
- **Exceeding the author's storage budget** returns **`413`** with
  body `{"error": "StorageQuotaExceeded", "plan_code": ...,
  "used_bytes": ..., "attempted_bytes": ..., "limit_bytes": ...}`.

The body is streamed to object storage in chunks straight off the
spooled request — it never enters application memory — and the cap
is enforced before any S3 write.
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
        "name": "Admin",
        "description": (
            "Platform-administration endpoints under `/admin`. Every "
            "operation requires the `accessCookie` scheme **and** the "
            "caller's platform-admin flag — non-admins get HTTP 403 "
            "`NotAdmin`. Admins are minted out-of-band via the "
            "`learnic-admin grant-admin <user_id>` CLI (no self-service "
            "route). Covers a dashboard counters read "
            "(`GET /admin/stats`), banning a user "
            "(`POST /admin/users/{user_id}/ban`, which also revokes "
            "every active session — there is no user-deletion "
            "counterpart), and permanently deleting a note "
            "(`DELETE /admin/notes/{note_id}`, irreversible and "
            "allowed in any status, unlike the author-facing "
            "draft-only delete)."
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
        "name": "BlogPosts",
        "description": (
            "Admin-authored blog. Reads are public and split by URL "
            "space: `GET /blog/posts` (paginated index of **published** "
            "posts, newest first, total in the `X-Total-Count` header) "
            "and `GET /blog/posts/{slug}` (a single published post with "
            "its ordered blocks). Every write — and reads in any status "
            "— live under `/admin/blog/posts`, require the `accessCookie` "
            "scheme **and** the platform-admin flag (non-admins get 403 "
            "`NotAdmin`), and cover the full post lifecycle "
            "(create draft, rename, change slug, publish/unpublish, "
            "delete) plus block management. A post body is an ordered "
            "list of blocks of three kinds — `image`, `html`, `video` — "
            "managed under `/admin/blog/posts/{post_id}/blocks/...`. "
            "Image and video blocks are `multipart/form-data` uploads "
            "(content type must start with `image/` / `video/`, else "
            "415); read views carry short-lived presigned media URLs. "
            "Block create/update return the full block; reorder takes "
            "the complete id permutation (else 409 `InvalidReorder`)."
        ),
    },
    {
        "name": "Billing",
        "description": (
            "Caller-scoped subscription read — current plan, plan "
            "limits, and aggregate storage usage. Plans live in code "
            "(`learnic/entities/billing/plan.py`); the DB carries "
            "only `(user_id, plan_code, ...)` grant rows. Absence of an "
            "active grant means the caller is on the in-code default "
            "plan (`FREE`). Quota enforcement on file-backed block "
            "creation surfaces as HTTP 413 `StorageQuotaExceeded` — "
            "the response body carries `plan_code`, `used_bytes`, "
            "`attempted_bytes`, and `limit_bytes` so the SPA can render "
            "an actionable message. A live quota meter is pushed over "
            "`WS /users/me/storage` — see `## WebSocket channels`. "
            "Administrators grant a tariff free of charge (e.g. add a "
            "user to BETA) via `POST /admin/users/{user_id}/"
            "subscription` and revoke it with the matching `DELETE` — "
            "both admin-only. Grantable plan codes are the registry "
            "entries (currently `FREE` (default) and `BETA`); an "
            "unknown code is rejected with 422 `UnknownPlanCode` — the "
            "SPA must source codes from the backend, not invent them."
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
            "User-owned learning products — notes and webinars. "
            "`GET /products` (catalog) and `GET /products/{id}` are "
            "public; `POST /products/notes`, "
            "`POST /products/webinars`, `GET /products/mine`, all "
            "PATCH/POST/DELETE state-changing endpoints, require the "
            "`accessCookie` scheme. Mutations are author-only; "
            "non-owners get HTTP 403 `NotResourceOwner`. Drafts can "
            "be deleted; published or archived products must be "
            "archived first (HTTP 409 `ProductNotInDraft`). "
            "Real-time deltas of product metadata and Q&A flow over "
            "`WS /products/{product_id}/events`; live editor "
            "cursors flow over `WS /products/{product_id}/cursors` — "
            "see the **WebSocket channels** section in the API "
            "description."
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
            "webinar product (HTTP 409 `NotAWebinar` for notes)."
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
            "Student enrollments — currently note-only. "
            "Polymorphic on `kind` (`note`); the kind-specific "
            "body lives in `details` (note: `release_id`, "
            "`progress_percent`, `completed_at`). `product_id` and "
            "`student_id` live on the base shape. `status` has two "
            "values: `active` (default) and `revoked` "
            "(author/admin removal of access). Note completion "
            "lives on `details.completed_at` and is orthogonal to "
            "`status` — a completed enrollment is still `active`. "
            "Create: `POST /products/{product_id}/enrollments` "
            "(self-enroll; product must be `PUBLISHED` — 409 "
            "`CannotEnrollInUnpublishedProduct` otherwise; 409 on "
            "`ProductDoesNotSupport`, `AlreadyEnrolled`, or "
            "`CannotEnrollInUnreleasedNote`). Admin grants live on "
            "an internal handler and do not expose an HTTP route. "
            "Caller-scoped: `GET /users/me/enrollments`. "
            "List by parent: "
            "`GET /notes/{note_id}/enrollments` (author/"
            "`READ_PRODUCT`). "
            "Item ops: "
            "`POST /notes/{note_id}/enrollments/{id}/complete` "
            "is author-only (marks `completed_at`); "
            "`PATCH .../{id}/release` re-pins the enrollment to "
            "another release (author-only, `MANAGE_RELEASES`)."
        ),
    },
    {
        "name": "NoteReleases",
        "description": (
            "Immutable releases of a note product. A release "
            "snapshots the current draft (modules + lessons + "
            "blocks) into mirror tables, pinning every row to the "
            "new release id. Creating the **first** release also "
            "flips the product's status to ``PUBLISHED`` — notes "
            "are not published any other way (the standalone "
            "publish endpoint refuses for notes with HTTP 409 "
            "``CannotPublishNoteDirectly``). Versions follow "
            "semver: from the previous ``v(M.m.p)``, ``patch`` → "
            "``v(M.m.p+1)``, ``minor`` → ``v(M.m+1.0)``, ``major`` "
            "→ ``v(M+1.0.0)``. The first release starts from the "
            "implicit baseline ``v0.0.0``. All endpoints under "
            "this tag are author-only."
        ),
    },
    {
        "name": "NoteContent",
        "description": (
            "Author-side editing of note content — modules and "
            "lessons inside a note product. Authoring endpoints "
            "under `/notes/{note_id}/modules/...` and "
            "`/notes/{note_id}/lessons/...` require the "
            "`accessCookie` scheme and collaborator permissions "
            "(HTTP 403 otherwise). Operations refuse on non-note "
            "products with HTTP 409 `NotANote`. Content lives in "
            "the product's draft workspace; releases (see the "
            "NoteReleases tag) snapshot the draft. "
            "Student/visitor reads live under `/notes/{note_id}`: "
            "`GET /notes/{note_id}/scheme` (structure only, public "
            "for any published note — including `private` ones) "
            "hands out the lesson ids, then "
            "`GET /notes/{note_id}/release-lessons/{lesson_id}` "
            "loads one lesson's blocks on demand (allowed for "
            "collaborators with `READ_PRODUCT`, actively-enrolled "
            "students on their pinned release, and anyone — "
            "including anonymous — when the note is published with "
            "`public` visibility; uniform 404 otherwise). "
            "Real-time deltas of note-content edits flow over "
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
        "name": "Gifts",
        "description": (
            "Gift product (note) access to another person. The "
            "gifter issues a gift via "
            "`POST /products/{id}/gifts/by-user` (registered user) or "
            "`POST /products/{id}/gifts/by-email` (possibly "
            "unregistered) — both produce a `PENDING_INVITE` row with "
            "a ~14-day TTL and notify the recipient on three channels: "
            "a push banner, an in-app card with Accept / Decline "
            "buttons, and an email with Accept / Decline buttons that "
            "link to the SPA routes `/gifts/{id}/accept` and "
            "`/gifts/{id}/decline` (carrying the token). Those pages "
            "POST to `POST /gifts/{id}/accept-by-token` / "
            "`/gifts/{id}/decline`; the in-app card POSTs to the "
            "token-less `POST /gifts/{id}/accept`. Accepting creates "
            "the note enrollment; the gifter is notified of the "
            "outcome. The gifter may cancel a still-pending gift with "
            "`DELETE /gifts/{id}`. Expired pending gifts are purged by "
            "a nightly job and cannot be accepted. Requires "
            "`manage_releases` on the product to issue or revoke."
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
        "name": "Dev",
        "description": (
            "Development-only endpoints, registered only when "
            "`APP_ENVIRONMENT=development` and absent from prod "
            "builds. `POST /dev/jobs/reconcile-storage-quotas` "
            "enqueues the over-quota reconciliation pass on demand "
            "(the same task the cron scheduler fires daily at 03:00 "
            "UTC), so a developer can trigger it without waiting for "
            "the next tick."
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
