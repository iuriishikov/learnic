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
for the project's WS endpoints. There are three channels — they share
authentication and close-code conventions but differ in direction and
payload shape. None of them appear under `paths` in this schema; treat
the prose below as authoritative.

### Authentication and close codes

All channels reuse the standard `accessCookie` HttpOnly cookie —
browsers send it on the upgrade handshake automatically. The server
validates the cookie *before* `accept`, so authentication failures are
delivered as a close frame, not as a message. Close codes used by the
WS layer:

- `4401` — missing or denied access cookie.
- `4403` — authenticated, but not authorised (e.g. not the product
  author).
- `4404` — target resource does not exist or is the wrong type
  (e.g. opening the course-content channel on a webinar product).

There is no server-side event buffering or replay. On reconnect the
client refetches initial state via REST and re-subscribes — events
emitted while disconnected are lost by design.

### `WS /products/{product_id}/events` — product-level deltas

Read-only push of product-metadata and Q&A deltas to the product's
author. Course-content events flow through a separate channel (see
below); webinar defaults and cohorts are intentionally not covered
yet.

Bootstrap by fetching `GET /products/{product_id}` (and
`GET /products/{product_id}/qa` if Q&A is shown) before opening the
socket.

**Server → client envelope.**

```json
{
  "kind": "<ProductEventKind value>",
  "product_id": "<UUID>",
  "actor_id": "<UUID>",
  "payload": { ... },
  "occurred_at": "<ISO 8601>"
}
```

**`kind` values** (drawn from `ProductEventKind`):

- Metadata: `name_changed`, `description_changed`,
  `duration_changed`.
- Cover: `cover_changed`, `cover_removed`.
- Status: `published`, `archived`, `unarchived`, `deleted`.
- Q&A: `qa_added`, `qa_question_changed`, `qa_answer_changed`,
  `qa_reordered`, `qa_deleted`.

`payload` carries id-level fields plus the new value when trivial
(e.g. `name_changed` → `{"name": "..."}`); for non-trivial changes
the client should refetch the affected resource via REST. Client →
server messages are not interpreted yet.

### `WS /courses/{course_id}/events` — course-content deltas

Read-only push of course-content edits (modules, lessons, blocks,
releases, draft reset) to the course's author. Course products only
— opening this socket on a webinar product yields a `4404` close.

Bootstrap by fetching
`GET /products/{product_id}/content/draft` before opening the socket.

**Server → client envelope.** Same shape as the product-level
channel, with `kind` drawn from `ContentEventKind`.

**`kind` values:**

- Module: `module_added`, `module_renamed`,
  `module_description_updated`, `modules_reordered`, `module_deleted`.
- Lesson: `lesson_added`, `lesson_renamed`, `lesson_moved`,
  `lessons_reordered`, `lesson_deleted`.
- Block: `block_added`, `block_updated`, `block_deleted`,
  `blocks_reordered`.
- Release: `release_created`, `draft_reset`.

`payload` carries id-level info — apply small changes (e.g.
`module_renamed` carries the new title) directly, and refetch the
affected lesson or block via REST for content-heavy changes (e.g.
`block_updated` only carries `block_id` + `type`). Client → server
messages are not interpreted yet.

### `WS /products/{product_id}/collaboration-events` — collaboration deltas

Read-only push of :class:`CollaborationEvent` instances — invite,
accept, revoke, grants-updated — to clients that hold
`manage_collaborators` on the product (the product author is
short-circuited as having every permission).

**Authentication.** Standard `accessCookie` HttpOnly cookie sent
by the browser on the WS handshake. Failure closes with `4401`
before `accept`.

**Authorization.** The connecting user must hold
`manage_collaborators` on the target product (typically the
author or a Moderator). Non-authorised callers get `4403`.

**Lifecycle.** Server pushes events one-way until the client
disconnects. No client → server messages are interpreted yet —
silence is read as "may break in future" by SPA teams, so do
not send anything. No replay buffer; on reconnect the client
should refetch
`GET /products/{product_id}/collaborations` (and
`GET /products/{product_id}/collaborations/me/permissions` for
the affected user) and re-subscribe.

**Bootstrap.** Before opening the socket, fetch
`GET /products/{product_id}/collaborations` to load the current
collaborator list — the channel only carries deltas after the
moment of subscription.

**Server → client envelope.**

```json
{
  "kind": "<CollaborationEventKind value>",
  "product_id": "<UUID>",
  "actor_id": "<UUID>",
  "payload": {
    "collaboration_id": "<UUID>",
    "collaborator_id": "<UUID | absent>",
    "invited_email": "<string | absent>"
  },
  "occurred_at": "<ISO 8601>"
}
```

`payload.collaboration_id` is always present; `collaborator_id`
appears once an invitee is bound (set on `INVITED` for by-user
invites, on every `ACCEPTED`, and on `REVOKED` /
`GRANTS_UPDATED` when the affected row carries one).
`invited_email` appears only on `INVITED` for by-email invites
that have not yet been accepted.

**`kind` values** (drawn from `CollaborationEventKind`):

- `invited` — new pending collaboration created. The SPA
  appends the row to the collaborators list.
- `accepted` — invitee accepted; the SPA flips the row to
  active and re-fetches the collaborator profile if it was a
  by-email invite (`collaborator_id` was previously absent).
- `revoked` — collaboration ended (manager-initiated revoke or
  self-leave). The SPA removes / greys out the row and, when
  `payload.collaborator_id` matches the current user, also
  refetches `…/me/permissions` to drop UI gating.
- `grants_updated` — the affected user's grants changed.
  Subscribers re-fetch `…/me/permissions` if
  `payload.collaborator_id` matches the current user.

Role-catalogue events (create/update/delete custom role) are
**not** broadcast on this channel in this phase — clients should
re-call `GET /products/{product_id}/roles` on demand.

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
        "name": "WebinarEnrollments",
        "description": (
            "Student enrollments in webinar cohorts. "
            "`POST /cohorts/{cohort_id}/enrollments` self-enrolls "
            "the current user (returns 409 `EnrollmentClosed`, "
            "`AlreadyEnrolled`, or `CohortFull` on pre-condition "
            "failure). `GET /cohorts/{cohort_id}/enrollments` lists "
            "for the host/author. "
            "`GET /users/me/webinar-enrollments` returns the current "
            "user's enrollments. Drop/complete/refund endpoints under "
            "`/cohorts/{cohort_id}/enrollments/{enrollment_id}/...` "
            "— self-drop is allowed; complete/refund are host-or-author."
        ),
    },
    {
        "name": "CourseEnrollments",
        "description": (
            "Student enrollments in self-paced course products. "
            "`POST /courses/{course_id}/enrollments` self-enrolls the "
            "current user (returns 409 `NotACourse` or "
            "`AlreadyEnrolled` on pre-condition failure). "
            "`PATCH /courses/{course_id}/enrollments/{enrollment_id}"
            "/progress` is student-only and auto-completes at 100. "
            "Complete/refund endpoints are author-only. "
            "`GET /users/me/course-enrollments` returns the current "
            "user's enrollments; "
            "`GET /courses/{course_id}/enrollments` is author-only."
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
            "`WS /courses/{course_id}/events` — see the "
            "**WebSocket channels** section in the API description."
        ),
    },
    {
        "name": "Roles",
        "description": (
            "Per-product role catalogue used by collaboration grants. "
            "Four system roles (Viewer, Commentor, Editor, Moderator) "
            "are seeded by Alembic and visible inside every product. "
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
            "POSTs the token to `POST /collaborations/{id}/accept`. "
            "All collaborator-side notifications (invite, accept, "
            "revoke, grant change, self-leave) are delivered by "
            "email. Real-time deltas of the collaborator list flow "
            "over `WS /products/{product_id}/collaboration-events` "
            "to managers — see the **WebSocket channels** section "
            "in the API description."
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
    setup_routes(app)
    container = setup_providers(configs)
    setup_dishka(container, app)
    return app


def create_app_production() -> FastAPI:
    return _create_app(setup_configs())


def create_app_tests(configs: Configs) -> FastAPI:
    return _create_app(configs)
