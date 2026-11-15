"""Replays the login sequence from traffic-notes.md against fake servers."""

from urllib.parse import parse_qs

import httpx
import pytest
import respx

from asvz_enroll.errors import LoginError, UnexpectedLoginPageError, WrongCredentialsError
from asvz_enroll.login import AUTHORISATION_URL, LOGIN_API_URL, REDIRECT_URL, TOKEN_URL, log_in

EDU_ID_URL = "https://login.eduid.ch/idp/profile/oidc/authorize"

SESSION_CHECK_PAGE = """
<title>Switch edu-ID - Loading Session Information</title>
<form action="/idp/profile/oidc/authorize?execution=e1s1" method="post">
  <input name="shib_idp_ls_success.shib_idp_session_ss" type="hidden" value="false">
  <input name="shib_idp_ls_supported" type="hidden">
  <input name="_eventId_proceed" type="hidden">
</form>"""

USERNAME_PAGE = """
<title>Switch edu-ID - Login</title>
<form action="/idp/profile/oidc/authorize?execution=e1s2" method="post">
  <input type="email" name="j_username">
  <button type="submit" name="_eventId_submit">Continue</button>
</form>"""

PASSWORD_PAGE = """
<title>Switch edu-ID - Login</title>
<form action="/idp/profile/oidc/authorize?execution=e1s3" method="post">
  <input type="email" name="j_username" value="me@example.org" readonly>
  <input type="password" name="j_password">
  <button type="submit" name="_eventId_proceed">Login</button>
</form>"""

SECOND_FACTOR_PAGE = "<title>Switch edu-ID - Two-step login</title><p>Enter your code</p>"


def _form_data(request: httpx.Request) -> dict[str, list[str]]:
    return parse_qs(request.content.decode(), keep_blank_values=True)


def _fake_asvz_and_edu_id(mock: respx.MockRouter, after_password: httpx.Response) -> None:
    mock.get(AUTHORISATION_URL).respond(
        302, headers={"Location": "https://id.asvz.ch/login?authRequest=V2_123"}
    )
    mock.get("https://id.asvz.ch/login").respond(text="<title>ASVZ | Login</title>")
    mock.post(f"{LOGIN_API_URL}/externalAuth/loginUrl").respond(
        json={"authUrl": f"{EDU_ID_URL}?client_id=asvz_idp_prod"}
    )
    mock.get(EDU_ID_URL).respond(text=SESSION_CHECK_PAGE)
    mock.post(EDU_ID_URL, params={"execution": "e1s1"}).respond(text=USERNAME_PAGE)
    mock.post(EDU_ID_URL, params={"execution": "e1s2"}).respond(text=PASSWORD_PAGE)
    mock.post(EDU_ID_URL, params={"execution": "e1s3"}).mock(return_value=after_password)
    mock.get("https://id.asvz.ch/login/idp/success").respond(text="<title>ASVZ | Login</title>")


BACK_TO_ASVZ = httpx.Response(
    302, headers={"Location": "https://id.asvz.ch/login/idp/success?id=intent-1&token=intent-token"}
)


@respx.mock(assert_all_called=False)
def test_successful_login_returns_the_access_token(respx_mock: respx.MockRouter) -> None:
    _fake_asvz_and_edu_id(respx_mock, after_password=BACK_TO_ASVZ)
    finish = respx_mock.post(f"{LOGIN_API_URL}/zitadelAuth/login").respond(
        json={"action": "Redirect", "redirectUri": "https://idp.asvz.ch/oidc/callback"}
    )

    def send_back_with_code(request: httpx.Request) -> httpx.Response:
        state = parse_qs(respx_mock.calls[0].request.url.query.decode())["state"][0]
        return httpx.Response(
            302, headers={"Location": f"{REDIRECT_URL}?code=the-code&state={state}"}
        )

    respx_mock.get("https://idp.asvz.ch/oidc/callback").mock(side_effect=send_back_with_code)
    respx_mock.get(REDIRECT_URL).respond(text="lesson app")
    token_request = respx_mock.post(TOKEN_URL).respond(
        json={"access_token": "the-token", "expires_in": 43200}
    )

    token = log_in("me@example.org", "my-password")

    assert token.value == "the-token"
    assert "the-token" not in repr(token)

    session_check, username_step, password_step = (
        _form_data(call.request)
        for call in respx_mock.calls
        if call.request.url.host == "login.eduid.ch" and call.request.method == "POST"
    )
    assert session_check["shib_idp_ls_supported"] == ["true"]
    assert username_step["j_username"] == ["me@example.org"]
    assert password_step["j_password"] == ["my-password"]

    assert finish.calls.last.request.content == (
        b'{"idpIntentId":"intent-1","idpIntentToken":"intent-token",'
        b'"userId":null,"authRequestId":"V2_123"}'
    )
    sent_for_token = _form_data(token_request.calls.last.request)
    assert sent_for_token["code"] == ["the-code"]
    assert len(sent_for_token["code_verifier"][0]) >= 43


@respx.mock(assert_all_called=False)
def test_wrong_password_is_recognised(respx_mock: respx.MockRouter) -> None:
    _fake_asvz_and_edu_id(respx_mock, after_password=httpx.Response(200, text=PASSWORD_PAGE))

    with pytest.raises(WrongCredentialsError):
        log_in("me@example.org", "wrong")


@respx.mock(assert_all_called=False)
def test_second_factor_page_is_reported_by_its_title(respx_mock: respx.MockRouter) -> None:
    _fake_asvz_and_edu_id(respx_mock, after_password=httpx.Response(200, text=SECOND_FACTOR_PAGE))

    with pytest.raises(UnexpectedLoginPageError, match="Two-step login"):
        log_in("me@example.org", "my-password")


@respx.mock(assert_all_called=False)
def test_extra_step_at_asvz_is_explained(respx_mock: respx.MockRouter) -> None:
    _fake_asvz_and_edu_id(respx_mock, after_password=BACK_TO_ASVZ)
    respx_mock.post(f"{LOGIN_API_URL}/zitadelAuth/login").respond(json={"action": "Register"})

    with pytest.raises(LoginError, match="Register"):
        log_in("me@example.org", "my-password")
