import os
import sys

from dotenv import load_dotenv
import tweepy

load_dotenv()

if __name__ == "__main__":
    try:
        twitter_client: tweepy.Client = tweepy.Client(
            bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
            consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
            consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
            access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
            access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        )

        twitter_client.create_tweet(text="This is test tweet.")
    except Exception as e:
        print(e)
        sys.exit(1)
