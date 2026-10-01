"""Tweet when a new Kaggle competition is launched.

Runs on a Cloudflare Cron Trigger. The schedule lives in wrangler.jsonc.

There are no third-party runtime dependencies: Python Workers run on Pyodide,
where `kaggle` and `tweepy` cannot work (both need `requests` and blocking
sockets), so the two HTTP calls use the runtime's own `fetch` and the signing
lives in oauth1.py.
"""

import base64
import datetime
import json

from workers import WorkerEntrypoint, fetch

from kaggle import build_tweet_text, select_new_competitions
from oauth1 import build_authorization_header

# page=1 is the default, but state it: the response is a single fixed-size
# page and this job deliberately does not paginate. The scan stops at the
# first competition older than the cutoff, so a second page is never needed.
KAGGLE_COMPETITIONS_URL = (
    "https://www.kaggle.com/api/v1/competitions/list?sortBy=recentlyCreated&page=1"
)
TWEET_URL = "https://api.twitter.com/2/tweets"

# If you change this, change triggers.crons in wrangler.jsonc too.
LOOKBACK_MINUTES = 30


async def list_new_competitions(env, after: datetime.datetime) -> list:
    # Pyodide has no `requests`, so build the Basic auth header by hand.
    credentials = base64.b64encode(
        f"{env.KAGGLE_USERNAME}:{env.KAGGLE_KEY}".encode("utf-8")
    ).decode("ascii")

    response = await fetch(
        KAGGLE_COMPETITIONS_URL,
        method="GET",
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "User-Agent": "kagoole-twitter",
        },
    )
    if response.status != 200:
        raise RuntimeError(
            f"kaggle api returned {response.status}: {await response.text()}"
        )

    payload = await response.json()
    print(f"kaggle api returned {len(payload)} competitions")

    return select_new_competitions(payload, after)


async def create_tweet(env, text: str) -> None:
    authorization = build_authorization_header(
        "POST",
        TWEET_URL,
        consumer_key=env.TWITTER_CONSUMER_KEY,
        consumer_secret=env.TWITTER_CONSUMER_SECRET,
        access_token=env.TWITTER_ACCESS_TOKEN,
        access_token_secret=env.TWITTER_ACCESS_TOKEN_SECRET,
    )

    response = await fetch(
        TWEET_URL,
        method="POST",
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
        },
        body=json.dumps({"text": text}),
    )
    if response.status not in (200, 201):
        raise RuntimeError(
            f"twitter api returned {response.status}: {await response.text()}"
        )


def is_dry_run(env) -> bool:
    """Skip posting, so a local run can exercise everything but the tweet."""
    return str(getattr(env, "DRY_RUN", "")).lower() in ("1", "true", "yes")


class Default(WorkerEntrypoint):
    # The runtime requires all four parameters, unlike fetch().
    async def scheduled(self, controller, env, ctx):
        # The `env` parameter arrives as None on current runtimes; the
        # bindings live on self.env. Prefer the parameter in case that is
        # ever fixed, and fall back to the attribute that actually works.
        env = env if env is not None else self.env

        try:
            print("start")

            after = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                minutes=LOOKBACK_MINUTES
            )

            competitions = await list_new_competitions(env, after)
            print(f"completed list_new_competitions: {len(competitions)} new")

            dry_run = is_dry_run(env)
            for c in competitions:
                text = build_tweet_text(c)
                if dry_run:
                    print(f"[dry run] would tweet:\n{text}")
                    continue

                # Sequential on purpose: preserves the original order and
                # stays clear of the write rate limit.
                await create_tweet(env, text)
                print(f'tweet "{c.title}"')

            print("end")
        except Exception as e:
            # The old job called sys.exit(1), which means nothing here.
            # Re-raising is what marks the cron invocation as failed.
            print(e)
            raise
