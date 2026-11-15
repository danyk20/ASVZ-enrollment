"""Logs in to ASVZ with a SWITCH edu-ID and returns an access token.

The app does what a browser does, one function per stop (see "Login" in traffic-notes.md):

1. start_authorisation        ASVZ login server opens a login attempt (the "auth request").
2. ask_for_edu_id_login_page  ASVZ tells us where SWITCH edu-ID wants us to log in.
3. sign_in_at_edu_id          We answer the edu-ID forms: session check, username, password.
4. finish_asvz_login          ASVZ accepts the edu-ID result and names the next address.
5. collect_authorisation_code That address leads back to the lesson app with a one-time code.
6. exchange_code_for_token    The code is swapped for the access token.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx

from asvz_enroll.errors import LoginError, UnexpectedLoginPageError, WrongCredentialsError
from asvz_enroll.html_forms import HtmlForm, find_forms, page_title
from asvz_enroll.models import AccessToken
from asvz_enroll.pkce import code_challenge_for, make_code_verifier, make_random_state

# The lesson app, as registered at the ASVZ login server.
CLIENT_ID = "347016538475304947"
REDIRECT_URL = "https://schalter.asvz.ch/tn/auth"
SCOPE = "openid profile email api"

# The ASVZ login server.
AUTHORISATION_URL = "https://idp.asvz.ch/oauth/v2/authorize"
TOKEN_URL = "https://idp.asvz.ch/oauth/v2/token"

# The ASVZ login page and the API behind it.
LOGIN_PAGE_HOST = "id.asvz.ch"
EDU_ID_SUCCESS_PATH = "/login/idp/success"
EDU_ID_FAILURE_PATH = "/login/idp/fail"
LOGIN_API_URL = "https://api.id.asvz.ch/api"
EDU_ID_PROVIDER_ID = "346086364019705801"

# Field names of the SWITCH edu-ID forms.
USERNAME_FIELD = "j_username"
PASSWORD_FIELD = "j_password"
SESSION_CHECK_PREFIX = "shib_idp_ls_"
PROCEED_FIELD = "_eventId_proceed"

MOST_EDU_ID_PAGES_WE_ANSWER = 8
TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class EduIdResult:
    """What SWITCH edu-ID hands back to ASVZ after a successful login."""

    intent_id: str
    intent_token: str
    user_id: str | None


def log_in(username: str, password: str) -> AccessToken:
    code_verifier = make_code_verifier()
    state = make_random_state()

    with httpx.Client(follow_redirects=True, timeout=TIMEOUT_SECONDS) as browser:
        auth_request_id = start_authorisation(browser, code_challenge_for(code_verifier), state)
        edu_id_login_page = ask_for_edu_id_login_page(browser)
        edu_id_result = sign_in_at_edu_id(browser, edu_id_login_page, username, password)
        next_address = finish_asvz_login(browser, edu_id_result, auth_request_id)
        code = collect_authorisation_code(browser, next_address, state)
        return exchange_code_for_token(browser, code, code_verifier)


def start_authorisation(browser: httpx.Client, code_challenge: str, state: str) -> str:
    """Returns the id of the login attempt, which ASVZ puts in the address it sends us to."""
    response = browser.get(
        AUTHORISATION_URL,
        params={
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URL,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        },
    )
    response.raise_for_status()
    auth_request_id = _query_value(response.url, "authRequest")
    if auth_request_id is None:
        raise UnexpectedLoginPageError(
            f"ASVZ did not open a login attempt; it sent us to {_without_query(response.url)}."
        )
    return auth_request_id


def ask_for_edu_id_login_page(browser: httpx.Client) -> httpx.Response:
    response = browser.post(
        f"{LOGIN_API_URL}/externalAuth/loginUrl",
        json={
            "idpId": EDU_ID_PROVIDER_ID,
            "successUrl": f"https://{LOGIN_PAGE_HOST}{EDU_ID_SUCCESS_PATH}",
            "failureUrl": EDU_ID_FAILURE_PATH,
            "forceLogin": False,
        },
    )
    response.raise_for_status()
    login_page = browser.get(response.json()["authUrl"])
    login_page.raise_for_status()
    return login_page


def sign_in_at_edu_id(
    browser: httpx.Client, page: httpx.Response, username: str, password: str
) -> EduIdResult:
    """Answer each edu-ID page in turn until edu-ID sends us back to ASVZ."""
    password_already_given = False

    for _ in range(MOST_EDU_ID_PAGES_WE_ANSWER):
        if _is_back_at_asvz(page.url):
            return _read_edu_id_result(page.url)

        form = _form_to_answer(page)
        answers = _answers_for(form, username, password)
        # The password page repeats the username field, so only a second request for the
        # password means the login was refused. (A wrong username is refused there too.)
        if form.asks_for(PASSWORD_FIELD):
            if password_already_given:
                raise WrongCredentialsError(
                    "SWITCH edu-ID did not accept the username or password."
                )
            password_already_given = True

        page = browser.post(form.submit_url, data=form.filled_in_with(answers))
        page.raise_for_status()

    raise UnexpectedLoginPageError("SWITCH edu-ID kept showing pages; giving up.")


def finish_asvz_login(
    browser: httpx.Client, edu_id_result: EduIdResult, auth_request_id: str
) -> str:
    """Returns the address ASVZ wants the browser to visit next."""
    response = browser.post(
        f"{LOGIN_API_URL}/zitadelAuth/login",
        json={
            "idpIntentId": edu_id_result.intent_id,
            "idpIntentToken": edu_id_result.intent_token,
            "userId": edu_id_result.user_id,
            "authRequestId": auth_request_id,
        },
    )
    response.raise_for_status()
    answer = response.json()
    if answer.get("action") != "Redirect":
        raise LoginError(
            f"ASVZ wants an extra step ({answer.get('action')}) that needs a person. "
            "Log in once in a browser at https://schalter.asvz.ch/tn/ and try again."
        )
    return str(answer["redirectUri"])


def collect_authorisation_code(browser: httpx.Client, next_address: str, state: str) -> str:
    response = browser.get(next_address)
    code = _query_value(response.url, "code")
    if code is None or _query_value(response.url, "state") != state:
        raise UnexpectedLoginPageError(
            f"Expected to land on {REDIRECT_URL} with a code, "
            f"but landed on {_without_query(response.url)}."
        )
    return code


def exchange_code_for_token(browser: httpx.Client, code: str, code_verifier: str) -> AccessToken:
    response = browser.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URL,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        },
    )
    if response.is_error:
        raise LoginError(f"ASVZ did not issue a token (HTTP {response.status_code}).")
    token = response.json()
    return AccessToken(
        value=token["access_token"],
        expires_at=datetime.now(UTC) + timedelta(seconds=token["expires_in"]),
    )


def _is_back_at_asvz(url: httpx.URL) -> bool:
    return url.host == LOGIN_PAGE_HOST


def _read_edu_id_result(url: httpx.URL) -> EduIdResult:
    intent_id = _query_value(url, "id")
    intent_token = _query_value(url, "token")
    if url.path != EDU_ID_SUCCESS_PATH or intent_id is None or intent_token is None:
        raise LoginError(f"ASVZ reported a failed edu-ID login ({url.path}).")
    return EduIdResult(intent_id, intent_token, user_id=_query_value(url, "user"))


def _form_to_answer(page: httpx.Response) -> HtmlForm:
    forms = find_forms(page.text, str(page.url))
    for form in forms:
        if _answers_for(form, username="", password="") or _only_wants_us_to_proceed(form):
            return form
    raise UnexpectedLoginPageError(
        f'SWITCH edu-ID showed a page this app cannot answer: "{page_title(page.text)}". '
        "If it asks for a second factor or a consent, log in once in a browser and try again."
    )


def _answers_for(form: HtmlForm, username: str, password: str) -> dict[str, str]:
    """Our answers to the questions this form asks; empty if it asks none we know."""
    answers: dict[str, str] = {}
    if form.asks_for(USERNAME_FIELD):
        answers[USERNAME_FIELD] = username
    if form.asks_for(PASSWORD_FIELD):
        answers[PASSWORD_FIELD] = password
    for field_name in form.fields:
        # edu-ID first asks whether the browser can store a session. A browser's JavaScript
        # answers "true"; we have no JavaScript, so we give the same answers by hand.
        if field_name.startswith(f"{SESSION_CHECK_PREFIX}success.") or field_name == (
            f"{SESSION_CHECK_PREFIX}supported"
        ):
            answers[field_name] = "true"
    return answers


def _only_wants_us_to_proceed(form: HtmlForm) -> bool:
    return form.asks_for(PROCEED_FIELD) or form.submit_button_name == PROCEED_FIELD


def _query_value(url: httpx.URL, name: str) -> str | None:
    values = parse_qs(urlsplit(str(url)).query).get(name)
    return values[0] if values else None


def _without_query(url: httpx.URL) -> str:
    """The address without its query, because queries carry one-time secrets."""
    return str(url.copy_with(query=None))
