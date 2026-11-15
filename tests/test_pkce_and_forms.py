from asvz_enroll.html_forms import find_forms, page_title
from asvz_enroll.pkce import code_challenge_for, make_code_verifier

LOGIN_PAGE = """
<html><head><title>Switch edu-ID - Login</title></head><body>
<form id="loginForm" action="/idp/profile/oidc/authorize?execution=e1s2" method="post">
  <input type="hidden" name="csrf_token" value="abc">
  <input type="email" name="j_username">
  <button type="submit" name="_eventId_submit">Continue</button>
</form></body></html>
"""


def test_code_challenge_matches_the_example_in_the_pkce_standard() -> None:
    # RFC 7636, appendix B
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert code_challenge_for(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_code_verifiers_are_long_enough_and_different_each_time() -> None:
    assert len(make_code_verifier()) >= 43
    assert make_code_verifier() != make_code_verifier()


def test_form_is_read_like_a_browser_would_submit_it() -> None:
    (form,) = find_forms(LOGIN_PAGE, "https://login.eduid.ch/idp/profile/oidc/authorize")

    assert form.submit_url == "https://login.eduid.ch/idp/profile/oidc/authorize?execution=e1s2"
    assert form.asks_for("j_username")
    assert form.filled_in_with({"j_username": "me@example.org"}) == {
        "csrf_token": "abc",
        "j_username": "me@example.org",
        "_eventId_submit": "",
    }


def test_page_title() -> None:
    assert page_title(LOGIN_PAGE) == "Switch edu-ID - Login"
