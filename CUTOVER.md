# Cutover from GCP to Cloudflare

**Temporary document. Delete it once every step below is done.**

This branch removes the GCP infrastructure from the repository, but removing
the code does not remove the resources. Until the steps here are carried out,
Cloud Scheduler is still invoking the Cloud Run job every 30 minutes.

## Why the order matters

If this branch is merged before GCP is torn down, Cloud Scheduler
(`*/30 * * * *`) and the Cloudflare Cron Trigger (`*/30 * * * *`) both try to
post the same text to the same account. X rejects the second one as duplicate
content, so whichever loses the race fails every single run, and the
Cloudflare cron shows up as permanently failing even though it is working.

The `terraform/` directory is also how `terraform destroy` is run. It still
exists on `main`, so run the destroy from there. After this branch merges it
is only in git history (`git checkout <sha> -- terraform/`).

## Steps

1. **Create the Cloudflare API token.** Dashboard -> My Profile -> API Tokens
   -> *Edit Cloudflare Workers*, scoped to the one account. Add it and the
   account ID as the repository secrets `CLOUDFLARE_API_TOKEN` and
   `CLOUDFLARE_ACCOUNT_ID`.

2. **Register the six Worker secrets**, before the first deploy:

   ```sh
   cd job
   for name in KAGGLE_USERNAME KAGGLE_KEY TWITTER_CONSUMER_KEY \
               TWITTER_CONSUMER_SECRET TWITTER_ACCESS_TOKEN \
               TWITTER_ACCESS_TOKEN_SECRET; do
     npx wrangler secret put "$name"
   done
   ```

   The current values are in Secret Manager
   (`gcloud secrets versions access latest --secret=twitter_consumer_key`).
   `TWITTER_BEARER_TOKEN` is no longer needed.

3. **Smoke test locally.** Copy `job/.dev.vars.example` to `job/.dev.vars`,
   fill in real values, keep `DRY_RUN=1`, and follow the local development
   section of `README.md`.

4. **Pause Cloud Scheduler.** This is the step that prevents double posting,
   and it has to happen before the first Cloudflare cron fires.

   ```sh
   gcloud scheduler jobs pause kagoole-twitter-job --location=asia-northeast1
   ```

5. **Merge this branch** and confirm the deploy is green and the Worker shows
   a Cron Trigger in the dashboard.

6. **Watch at least two cron ticks** (about an hour) with
   `cd job && npx wrangler tail --format pretty` before touching GCP.

7. **Destroy GCP**, from a checkout that still has `terraform/`:

   ```sh
   cd terraform
   terraform destroy
   ```

   `google_service_account.terraform_github_actions` and its two IAM bindings
   carry `lifecycle { prevent_destroy = true }`. Remove those blocks, or
   `terraform state rm` them and delete the service account by hand, for the
   destroy to finish.

8. **Delete the state bucket.** It was never managed by terraform.

   ```sh
   gcloud storage rm -r gs://kagoole-379522-tfstate
   ```

9. **Delete or shut down the `kagoole-379522` project** if nothing else uses
   it, and remove any GCP-only repository secrets.

10. **Rotate the credentials.** Between steps 2 and 8 the Kaggle API key and
    the X tokens exist both in Secret Manager and in Cloudflare. Once GCP is
    gone, issue new ones and re-register them with `wrangler secret put` so
    the copies that lived in GCP stop being valid.

11. **Delete this file.**
