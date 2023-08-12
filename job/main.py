import datetime
import os
import sys

from google.cloud import secretmanager
import google_crc32c
from kaggle import KaggleApi
import tweepy


def get_secret_value(name: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = client.secret_version_path(os.getenv("GCP_PROJECT_ID"), name, "latest")
    response = client.access_secret_version(request={"name": name})

    crc32c = google_crc32c.Checksum()
    crc32c.update(response.payload.data)

    if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        print("Data corruption detected.")
        return None

    payload = response.payload.data.decode("UTF-8")

    return payload


class Competition:
    title: str = None
    url: str = None
    is_kernel_only: bool = False
    can_get_award_points: bool = False
    started_at: datetime.time = None
    deadline: datetime.time = None

    def set_from_kaggle_api(self, c):
        self.title = getattr(c, "title")
        self.url = getattr(c, "url")
        self.is_kernel_only = getattr(c, "isKernelsSubmissionsOnly")
        self.can_get_award_points = getattr(c, "awardsPoints")
        self.started_at = getattr(c, "enabledDate").replace(
            tzinfo=datetime.timezone.utc
        )
        self.deadline = getattr(c, "deadline").replace(tzinfo=datetime.timezone.utc)


def new_kaggle_api():
    api = KaggleApi()
    api.authenticate()

    return api


def list_new_competitions(after: datetime.datetime) -> list[Competition]:
    api = new_kaggle_api()

    competitions: list[Competition] = []
    for c in api.competitions_list(sort_by="recentlyCreated"):
        competition = Competition()
        competition.set_from_kaggle_api(c)

        if competition.started_at < after:
            break

        competitions.append(competition)

    return competitions


if __name__ == "__main__":
    try:
        # if you change interval, you must change execution schedule in Cloud Scheduler too(terraform/gcp.tf).
        after = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=30
        )
        competitions: list[Competition] = list_new_competitions(after)

        twitter_client: tweepy.Client = tweepy.Client(
            bearer_token=get_secret_value("twitter_bearer_token"),
            consumer_key=get_secret_value("twitter_consumer_key"),
            consumer_secret=get_secret_value("twitter_consumer_secret"),
            access_token=get_secret_value("twitter_access_token"),
            access_token_secret=get_secret_value("twitter_access_token_secret"),
        )

        for c in competitions:
            twitter_client.create_tweet(
                text=f'New #kaggle competition "{c.title}" is launched.\n\nMedal: {c.can_get_award_points}\n'
                f'Kernel Only: {c.is_kernel_only}\nDeadline: {c.deadline}\n{c.url}'
            )
    except Exception as e:
        print(e)
        sys.exit(1)
