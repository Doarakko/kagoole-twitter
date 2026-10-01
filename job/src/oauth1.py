"""OAuth 1.0a request signing, using nothing but the standard library.

`tweepy` (and the `requests-oauthlib` underneath it) cannot run on Cloudflare
Workers, because Pyodide has no `requests` and no blocking sockets. Signing a
request is the only thing this project needed from it, so it lives here.
"""

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote


def percent_encode(value: str) -> str:
    """Percent-encode a value per RFC 3986, as OAuth 1.0a requires.

    The unreserved set is A-Z a-z 0-9 - . _ ~ and `quote` already leaves
    - . _ ~ alone, so the only thing to undo is its default `safe="/"`.
    """
    return quote(str(value), safe="~")


def build_signature(
    method: str,
    url: str,
    params: dict,
    consumer_secret: str,
    token_secret: str,
) -> str:
    """Return the base64 HMAC-SHA1 signature for a request.

    `url` must be the base URI: no query string and no fragment. Any query
    parameters belong in `params` alongside the oauth_* ones.

    `params` deliberately does not include the request body. RFC 5849
    section 3.4.1.3.1 only folds the body into the signature base string when
    the content type is application/x-www-form-urlencoded, and this project
    posts JSON.
    """
    normalized = "&".join(
        f"{percent_encode(k)}={percent_encode(v)}" for k, v in sorted(params.items())
    )
    base_string = "&".join(
        [method.upper(), percent_encode(url), percent_encode(normalized)]
    )
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"

    digest = hmac.new(
        signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1
    ).digest()

    return base64.b64encode(digest).decode("ascii")


def build_authorization_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    nonce: str = None,
    timestamp: int = None,
) -> str:
    """Return the value for the Authorization header of a signed request.

    `nonce` and `timestamp` are injectable so that the signature can be
    checked against a known test vector.
    """
    params = {
        "oauth_consumer_key": consumer_key,
        # secrets.token_hex reaches crypto.getRandomValues under Pyodide.
        "oauth_nonce": nonce if nonce is not None else secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        # Workers derive time from Date.now(), which only advances on I/O, so
        # tweets sent in one invocation can share a timestamp. That is fine:
        # the nonce differs and the server tolerates a window of minutes.
        "oauth_timestamp": str(
            timestamp if timestamp is not None else int(time.time())
        ),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    params["oauth_signature"] = build_signature(
        method, url, params, consumer_secret, access_token_secret
    )

    return "OAuth " + ", ".join(
        f'{percent_encode(k)}="{percent_encode(v)}"' for k, v in sorted(params.items())
    )
