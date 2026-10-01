# [Kagoole Twitter](https://twitter.com/kagoole)

Tweet when new [Kaggle](https://www.kaggle.com/) competition is launched.

Please follow and enjoy Kaggle!

![example](./example.png)

## Infrastructure

Runs as a [Cloudflare Python Worker](https://developers.cloudflare.com/workers/languages/python/)
on a Cron Trigger. There is no container and no cloud project to manage.

> Migrating from the old GCP setup is not finished until the steps in
> [CUTOVER.md](./CUTOVER.md) are done. Cloud Scheduler keeps invoking the old
> Cloud Run job until it is paused, and both would post the same tweet.

| Item | Value |
| --- | --- |
| Worker | `kagoole-twitter` |
| Entry point | `job/src/entry.py` (`Default.scheduled`) |
| Schedule | `*/30 * * * *` — Cron Triggers always run in **UTC** |
| Config | `job/wrangler.jsonc` |
| Logs | Workers Logs, or `wrangler tail` |

Cloudflare resources are managed with wrangler only, so there is no Terraform.

- Pull request touching `job/**`: `pytest` runs (`.github/workflows/test.yml`)
  and `black` checks formatting (`.github/workflows/lint.yml`)
- Merge to `main` touching `job/**`: `pywrangler deploy` runs
  (`.github/workflows/deploy.yml`)

Deploying from CI needs two repository secrets, `CLOUDFLARE_API_TOKEN` (an
account token with the *Edit Cloudflare Workers* permissions) and
`CLOUDFLARE_ACCOUNT_ID`.

### Worker secrets

Six secrets, registered once and never committed. They are not declared in
`wrangler.jsonc`; Cloudflare delivers them onto `env` at runtime.

```sh
cd job
for name in KAGGLE_USERNAME KAGGLE_KEY TWITTER_CONSUMER_KEY \
            TWITTER_CONSUMER_SECRET TWITTER_ACCESS_TOKEN \
            TWITTER_ACCESS_TOKEN_SECRET; do
  npx wrangler secret put "$name"
done
```

Posting a tweet uses OAuth 1.0a user context, which is signed with the
consumer and access credentials alone, so no bearer token is needed.

### Local development

Copy `job/.dev.vars.example` to `job/.dev.vars` and fill in real values;
wrangler injects them as secrets during `dev`. Keep `DRY_RUN=1` to run
everything except posting.

```sh
cd job
uv run pytest
uv run pywrangler dev --test-scheduled
```

Then trigger the scheduled handler from another shell:

```sh
curl "http://localhost:8787/cdn-cgi/local/scheduled?cron=*%2F30+*+*+*+*"
```

Widen `LOOKBACK_MINUTES` in `job/src/entry.py` to see the tweet text for
competitions that launched further back.

### Notes

- The Worker declares no third-party runtime dependencies. Python Workers run
  on Pyodide, where `kaggle` and `tweepy` cannot work because both need
  `requests` and blocking sockets, so the Kaggle REST call uses the runtime's
  own `fetch` and the OAuth 1.0a signing lives in `job/src/oauth1.py`.
- Deploys go through `pywrangler`, not `wrangler`. Even with no dependencies
  of our own, the `workers` module is not built into the runtime at this
  compatibility date -- it comes from `workers-runtime-sdk`, and only
  `pywrangler` vendors it into the bundle. Plain `wrangler deploy` uploads
  successfully and then fails at import with `ModuleNotFoundError: No module
  named 'workers'`.
- `env` is passed to `scheduled()` as `None` on current runtimes, so
  `job/src/entry.py` falls back to `self.env`, where the bindings actually
  live.
- The lookback window in `job/src/entry.py` and the cron expression in
  `job/wrangler.jsonc` have to be changed together.

## Reference

- [Kagoole](https://github.com/Doarakko/kagoole)
