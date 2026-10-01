"""Reading the Kaggle competition list, without the `kaggle` package.

The `kaggle` package cannot run on Cloudflare Workers (it is built on
`requests`), so this talks to the same REST endpoint directly. The field
names and the selection rule are kept identical to what the package gave us,
because the tweet text is derived from them.
"""

import datetime

KAGGLE_BASE_URL = "https://www.kaggle.com"


def parse_datetime(value: str) -> datetime.datetime:
    """Parse a Kaggle timestamp into a timezone-aware UTC datetime.

    Kaggle emits .NET flavoured ISO-8601, e.g. "2024-01-15T00:00:00.0000000Z":
    seven fractional digits and a trailing "Z". `fromisoformat` never accepts
    more than six fractional digits on any version, so normalize the fraction
    and the "Z" before handing it over.
    """
    text = value.strip()

    if text[-1:] in ("Z", "z"):
        text = text[:-1] + "+00:00"

    if "." in text:
        head, _, tail = text.partition(".")
        digits = ""
        while tail[len(digits) : len(digits) + 1].isdigit():
            digits += tail[len(digits)]
        rest = tail[len(digits) :]
        text = f"{head}.{digits[:6].ljust(6, '0')}{rest}"

    parsed = datetime.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)

    return parsed.astimezone(datetime.timezone.utc)


def absolute_url(url: str) -> str:
    """Kaggle returns absolute URLs today; keep working if that ever changes."""
    return KAGGLE_BASE_URL + url if url.startswith("/") else url


class Competition:
    def __init__(
        self,
        title: str,
        url: str,
        is_kernel_only: bool,
        can_get_award_points: bool,
        started_at: datetime.datetime,
        deadline: datetime.datetime,
    ):
        self.title = title
        self.url = url
        self.is_kernel_only = is_kernel_only
        self.can_get_award_points = can_get_award_points
        self.started_at = started_at
        self.deadline = deadline

    @classmethod
    def from_api(cls, data: dict) -> "Competition":
        return cls(
            title=data["title"],
            url=absolute_url(data["url"]),
            is_kernel_only=bool(data["isKernelsSubmissionsOnly"]),
            can_get_award_points=bool(data["awardsPoints"]),
            started_at=parse_datetime(data["enabledDate"]),
            deadline=parse_datetime(data["deadline"]),
        )


def select_new_competitions(payload: list, after: datetime.datetime) -> list:
    """Return the competitions launched after `after`.

    The response is sorted by recentlyCreated, so the first competition older
    than the cutoff ends the scan.
    """
    competitions = []
    for item in payload:
        competition = Competition.from_api(item)
        if competition.started_at < after:
            break
        competitions.append(competition)

    return competitions


def build_tweet_text(c: Competition) -> str:
    # `deadline` is interpolated as a datetime on purpose: str() renders it as
    # "2024-06-01 23:59:00+00:00", which is what this account has always
    # tweeted. Interpolating the raw API string would change the tweet.
    return (
        f'New #kaggle competition "{c.title}" is launched.\n\n'
        f"Medal: {c.can_get_award_points}\n"
        f"Kernel Only: {c.is_kernel_only}\n"
        f"Deadline: {c.deadline}\n"
        f"{c.url}"
    )
