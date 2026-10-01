"""Tests for OAuth 1.0a signing.

The expected signatures below were produced by `oauthlib` and confirmed to
match this implementation byte for byte. A signature is all or nothing: get
the base string wrong and X answers 401 with no hint, so these vectors are
the only thing standing between a typo and a silently broken account.
"""

from oauth1 import build_authorization_header, build_signature, percent_encode

CONSUMER_KEY = "xvz1evFS4wEEPTGEFPHBog"
CONSUMER_SECRET = "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw"
ACCESS_TOKEN = "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb"
ACCESS_TOKEN_SECRET = "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE"
NONCE = "kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg"
TIMESTAMP = "1318622958"

TWEET_URL = "https://api.twitter.com/2/tweets"

OAUTH_PARAMS = {
    "oauth_consumer_key": CONSUMER_KEY,
    "oauth_nonce": NONCE,
    "oauth_signature_method": "HMAC-SHA1",
    "oauth_timestamp": TIMESTAMP,
    "oauth_token": ACCESS_TOKEN,
    "oauth_version": "1.0",
}


def sign(url, params, method="POST"):
    return build_signature(method, url, params, CONSUMER_SECRET, ACCESS_TOKEN_SECRET)


def test_percent_encode_leaves_unreserved_characters_alone():
    assert percent_encode("~") == "~"
    assert percent_encode("-._") == "-._"
    assert percent_encode("abcXYZ019") == "abcXYZ019"


def test_percent_encode_escapes_everything_else():
    # quote() defaults to safe="/", which OAuth does not allow.
    assert percent_encode("/") == "%2F"
    assert percent_encode(" ") == "%20"
    assert percent_encode("+") == "%2B"
    assert percent_encode("=") == "%3D"
    assert percent_encode("Ladies + Adding") == "Ladies%20%2B%20Adding"


def test_percent_encode_uses_utf8():
    assert percent_encode("ü") == "%C3%BC"


def test_signature_for_a_json_post():
    # The JSON body must not contribute to the signature, so the only
    # parameters are the six oauth_* ones.
    assert sign(TWEET_URL, OAUTH_PARAMS) == "KW/bTR/89oblzvjn7CwP2L8j5qQ="


def test_signature_includes_non_oauth_parameters():
    params = dict(
        OAUTH_PARAMS,
        status="Hello Ladies + Adding Some Parameters",
        include_entities="true",
    )
    signature = sign("https://api.twitter.com/1.1/statuses/update.json", params)
    assert signature == "OoccHtAezkskh3oNSnk3EgytbU8="


def test_signature_escapes_parameter_values():
    params = dict(
        OAUTH_PARAMS,
        text='New #kaggle competition "Foo/Bar~Baz" is launched. ü',
    )
    assert sign(TWEET_URL, params) == "CrNJEEkOOx34EoZ0qZeU/2+wo34="


def test_signature_depends_on_the_method():
    signature = sign("https://api.twitter.com/2/users/me", OAUTH_PARAMS, method="GET")
    assert signature == "6Kv2O8v3d2QmAMMoyJZvwReYnn8="


def test_authorization_header():
    header = build_authorization_header(
        "POST",
        TWEET_URL,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        nonce=NONCE,
        timestamp=int(TIMESTAMP),
    )

    assert header.startswith("OAuth ")
    # The signature is percent-encoded inside the header.
    assert 'oauth_signature="KW%2FbTR%2F89oblzvjn7CwP2L8j5qQ%3D"' in header
    for key in OAUTH_PARAMS:
        assert f'{key}="' in header


def test_authorization_header_varies_per_call():
    def header():
        return build_authorization_header(
            "POST",
            TWEET_URL,
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )

    # A reused nonce is rejected as a replay.
    assert header() != header()
