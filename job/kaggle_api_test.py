import datetime
import os
import sys

from kaggle import KaggleApi


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
            days=300
        )
        competitions: list[Competition] = list_new_competitions(after)

        for c in competitions:
            print(f"New #kaggle competition \"{c.title}\" is launched.\n\nMedal: {c.can_get_award_points}\n"
                f"Kernel Only: {c.is_kernel_only}\nDeadline: {c.deadline}\n{c.url}")
    except Exception as e:
        print(e)
        sys.exit(1)
