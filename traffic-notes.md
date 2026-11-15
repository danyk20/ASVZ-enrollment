# ASVZ enrolment — traffic notes (Stage 1)

Captured 2026-11-15 in the built-in browser, enrolling in lesson 781265
(Shotokan Karate, Tue 17 Nov 19:00, SC Hönggerberg). No tokens or passwords are stored here.

## Hosts

| Host | Role |
|---|---|
| `www.asvz.ch` | Public site (Drupal). Timetable data: `GET /asvz_api/event_search?_format=json&limit=60` (no login). |
| `schalter.asvz.ch/tn` | Angular app for lesson pages: `/tn/lessons/{lessonId}` |
| `schalter.asvz.ch/tn-api/api` | JSON API used by that app |
| `idp.asvz.ch` | OIDC issuer (token endpoint, discovery) |
| `id.asvz.ch` | Login UI (and `/logout`) |

## Login

- OIDC authorization code flow with PKCE, public client (no client secret).
  - issuer `https://idp.asvz.ch`, client_id `347016538475304947`
  - redirect_uri `https://schalter.asvz.ch/tn/auth`, scope `openid profile email api`
- After login the browser lands on `/tn/auth?code=…&state=…`; the app exchanges the code for tokens.
- Tokens are kept in `localStorage` of `schalter.asvz.ch` (`access_token`, `id_token`, `expires_at`, …).
  No cookies are used for the API.
- Access token: JWT, **lifetime 12 hours** (43200 s). **No refresh token** is issued
  (scope has no `offline_access`).
- The browser recording did not keep the requests between the start and the end of the login;
  they were worked out separately, see the sequence below.

### Login sequence (worked out 2026-11-15, implemented in `src/asvz_enroll/login.py`)

The whole sequence was confirmed with a real login on 2026-11-15 (`asvz-enroll --check-login`).

1. `GET https://idp.asvz.ch/oauth/v2/authorize?client_id=…&code_challenge=…` →
   302 to `https://id.asvz.ch/login?authRequest=V2_<number>` (a JavaScript page; ASVZ runs Zitadel).
2. `POST https://api.id.asvz.ch/api/externalAuth/loginUrl`, JSON
   `{idpId: "346086364019705801", successUrl: "https://id.asvz.ch/login/idp/success", failureUrl: "/login/idp/fail", forceLogin: false}`
   → `{authUrl: "https://login.eduid.ch/idp/profile/oidc/authorize?client_id=asvz_idp_prod&…"}`
3. SWITCH edu-ID (Shibboleth), each a form posted to `…/authorize?execution=e1sN`:
   a. session check: hidden `shib_idp_ls_*` fields, normally filled by JavaScript; posting
      `…success…=true`, `shib_idp_ls_supported=true`, `_eventId_proceed` works.
   b. username: `j_username`, button `_eventId_submit`.
   c. password: `j_password`, plus `j_username` repeated read-only; button `_eventId_proceed`.
      A wrong password is expected to show this page again (not confirmed).
   d. redirect via `https://idp.asvz.ch/idps/callback` to
      `https://id.asvz.ch/login/idp/success?id=<intent>&token=<intent token>[&user=<id>]`.
4. `POST https://api.id.asvz.ch/api/zitadelAuth/login`, JSON
   `{idpIntentId, idpIntentToken, userId, authRequestId}` → `{action: "Redirect", redirectUri}`.
   Other actions (`Register`, `ConfirmSwitchEduIdSync`, `ConfirmImAddressLinking`) need a person.
5. `GET redirectUri` → redirects to `https://schalter.asvz.ch/tn/auth?code=…&state=…`.
6. `POST https://idp.asvz.ch/oauth/v2/token` (form: `grant_type=authorization_code`, `code`,
   `redirect_uri`, `client_id`, `code_verifier`) → `access_token`, `expires_in`.

## API calls (all need `Authorization: Bearer <access_token>` unless noted)

| Call | Result |
|---|---|
| `GET /Lessons/{id}` | 200 without login. Lesson details, see below. |
| `GET /Lessons/{id}/MyEnrollment` | 404 if not enrolled, 200 if enrolled; 401 without token (verified) |
| `POST /Lessons/{id}/Enrollment`, body `{}` | **Enrols.** 201, `{"data":{"placeNumber":4,"statusId":4}}` |
| `DELETE /Lessons/{id}/Enrollment` | Cancels (from the app's JavaScript; not exercised) |
| `GET /MemberPerson`, `GET /memberships/my` | Profile and membership; the app loads them, enrolment does not send them |
| `GET /Enrollments` | All my enrolments (from the app's JavaScript; not exercised) |

Sequence the app ran when "enrol" was clicked:
`MyEnrollment` (404) → `POST Enrollment` (201) → `Lessons/{id}` → `MyEnrollment` (200, status "4 - definitiv").

The request headers and body of the POST were not visible in the recorder. The empty `{}` body
comes from the app's code (`enrollForLesson`), and the Bearer header was confirmed on
`MyEnrollment` (401 without, 200 with).

## Useful fields in `GET /Lessons/{id}`

- `enrollmentFrom` / `enrollmentUntil` — the window (here: opens 3 days before start, to the minute:
  start Tue 19:00 → opens Sat 19:00)
- `cancelationUntil`, `starts`, `ends`
- `participantsMax`, `participantCount` — free places
- `enrollmentEnabled`, `status`, `sportName`, `title`, `facilities`, `rooms`, `instructors`

## Open points

- Lesson ids change every week (781265 is this one occurrence). Stage 2 must look up next week's id,
  probably via `www.asvz.ch/asvz_api/event_search` with sport/facility filters — filters not yet examined.
- Behaviour of `POST Enrollment` before `enrollmentFrom` (error code/body) was not observed.
- The waiting-list case (lesson full) was not observed.

## Implications for Stage 2

- The enrolment itself is one POST with a bearer token; no browser needed at that moment.
- The hard part is getting a token unattended: 12 h lifetime and no refresh token, so a weekly job
  cannot reuse last week's token. Options:
  1. Script performs the login itself (needs the login requests captured, and stored credentials;
     breaks if 2FA is required).
  2. Headless browser with a persistent profile, relying on the `id.asvz.ch` session staying valid
     for a week (lifetime unknown).
  3. You log in manually within 12 h before the window; the script takes the token and fires the
     POST at the exact second.
