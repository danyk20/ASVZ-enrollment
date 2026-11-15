"""PKCE: how a login without a client secret proves that the app which started it also ends it.

The app invents a secret (the verifier), shows the login server only its hash (the challenge),
and reveals the secret itself when it collects the token.
"""

import base64
import hashlib
import secrets


def make_code_verifier() -> str:
    return secrets.token_urlsafe(48)


def code_challenge_for(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def make_random_state() -> str:
    """A value sent with the login request and expected back unchanged."""
    return secrets.token_urlsafe(24)
