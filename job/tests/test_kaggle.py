"""Tests for parsing the Kaggle response and rendering the tweet.

The tweet text is the contract with everyone following @kagoole, so it is
pinned here character for character.
"""

import datetime

from kaggle import (
    Competition,
    absolute_url,
    build_tweet_text,
    parse_datetime,
    select_new_competitions,
)

UTC = datetime.timezone.utc


def api_item(title="Titanic", enabled="2024-06-01T12:00:00.0000000Z"):
    return {
        "title": title,
        "url": f"https://www.kaggle.com/competitions/{title.lower()}",
        "isKernelsSubmissionsOnly": False,
        "awardsPoints": True,
        "enabledDate": enabled,
        "deadline": "2024-12-01T23:59:00.0000000Z",
    }


def test_parse_datetime_accepts_dotnet_seven_digit_fractions():
    # This is what Kaggle actually sends, and what fromisoformat rejects.
    assert parse_datetime("2024-01-15T00:00:00.0000000Z") == datetime.datetime(
        2024, 1, 15, tzinfo=UTC
    )


def test_parse_datetime_accepts_no_fraction():
    assert parse_datetime("2024-06-01T23:59:00Z") == datetime.datetime(
        2024, 6, 1, 23, 59, tzinfo=UTC
    )


def test_parse_datetime_truncates_to_microseconds():
    parsed = parse_datetime("2024-06-01T23:59:00.123456789+00:00")
    assert parsed.microsecond == 123456


def test_parse_datetime_pads_short_fractions():
    assert parse_datetime("2024-06-01T23:59:00.5Z").microsecond == 500000


def test_parse_datetime_assumes_utc_when_naive():
    assert parse_datetime("2024-06-01T23:59:00").tzinfo == UTC


def test_parse_datetime_converts_other_offsets_to_utc():
    assert parse_datetime("2024-06-01T23:59:00+09:00") == datetime.datetime(
        2024, 6, 1, 14, 59, tzinfo=UTC
    )


def test_parse_datetime_renders_the_way_the_tweet_expects():
    # The tweet interpolates the datetime, so its str() is part of the output.
    assert str(parse_datetime("2024-06-01T23:59:00Z")) == "2024-06-01 23:59:00+00:00"


def test_absolute_url_expands_relative_paths():
    assert (
        absolute_url("/competitions/foo") == "https://www.kaggle.com/competitions/foo"
    )


def test_absolute_url_leaves_absolute_urls_alone():
    url = "https://www.kaggle.com/competitions/foo"
    assert absolute_url(url) == url


def test_select_new_competitions_keeps_the_recent_ones():
    after = datetime.datetime(2024, 6, 1, 11, 30, tzinfo=UTC)
    payload = [
        api_item("New", "2024-06-01T12:00:00.0000000Z"),
        api_item("AlsoNew", "2024-06-01T11:45:00.0000000Z"),
    ]

    selected = select_new_competitions(payload, after)

    assert [c.title for c in selected] == ["New", "AlsoNew"]


def test_select_new_competitions_stops_at_the_first_old_one():
    # The response is sorted by recentlyCreated, so the scan short-circuits.
    # Anything after the first old entry is not even parsed.
    after = datetime.datetime(2024, 6, 1, 11, 30, tzinfo=UTC)
    payload = [
        api_item("New", "2024-06-01T12:00:00.0000000Z"),
        api_item("Old", "2024-05-01T12:00:00.0000000Z"),
        api_item("OutOfOrder", "2024-06-01T12:30:00.0000000Z"),
    ]

    selected = select_new_competitions(payload, after)

    assert [c.title for c in selected] == ["New"]


def test_select_new_competitions_on_an_empty_response():
    assert select_new_competitions([], datetime.datetime.now(UTC)) == []


def test_build_tweet_text():
    competition = Competition(
        title="Titanic - Machine Learning from Disaster",
        url="https://www.kaggle.com/competitions/titanic",
        is_kernel_only=False,
        can_get_award_points=True,
        started_at=datetime.datetime(2024, 6, 1, tzinfo=UTC),
        deadline=datetime.datetime(2024, 6, 1, 23, 59, tzinfo=UTC),
    )

    assert build_tweet_text(competition) == (
        'New #kaggle competition "Titanic - Machine Learning from Disaster"'
        " is launched.\n"
        "\n"
        "Medal: True\n"
        "Kernel Only: False\n"
        "Deadline: 2024-06-01 23:59:00+00:00\n"
        "https://www.kaggle.com/competitions/titanic"
    )


def test_build_tweet_text_from_an_api_item():
    competition = Competition.from_api(api_item())
    text = build_tweet_text(competition)

    assert 'New #kaggle competition "Titanic" is launched.\n\n' in text
    assert "Deadline: 2024-12-01 23:59:00+00:00" in text
