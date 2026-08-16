# terraform

## Overview

| Item | Value |
| --- | --- |
| GCP project | `kagoole-379522` (project number `631578640507`) |
| Region | `asia-northeast1` |
| Backend | GCS `gs://kagoole-379522-tfstate` with prefix `terraform/state` |
| Terraform version | Pinned by `.terraform-version` in the repository root |

The state bucket is **not managed by terraform**. A backend cannot manage the
bucket that stores its own state, and keeping it outside terraform also
prevents a bad apply from destroying the state along with it.

## Day-to-day operation

Everything runs in CI, so there is normally no need to apply locally.

| Trigger | What runs | Workflow |
| --- | --- | --- |
| Pull request | `fmt` / `init` / `validate` / `plan`, result posted as a PR comment | `.github/workflows/terraform_plan.yml` |
| Merge to `main` | `apply -auto-approve` | `.github/workflows/terraform_apply.yml` |

GCP authentication uses Workload Identity Federation, so no service account
key is involved.

| Purpose | Service account | Roles |
| --- | --- | --- |
| terraform (CI) | `terraform-github-actions@kagoole-379522.iam.gserviceaccount.com` | `roles/owner` |
| Container build and deploy (`deploy.yml`) | `github-actions@kagoole-379522.iam.gserviceaccount.com` | `artifactregistry.admin`, `run.developer`, `iam.serviceAccountUser` |

Both share the workload identity pool `gh-oidc-pool` and can only be
impersonated when `attribute.repository` matches this repository.

## Running locally

Local runs touch the shared state directly, so stop at `plan` unless you are
bootstrapping.

```sh
gcloud auth application-default login
cd terraform
terraform init
terraform plan
```

## Initial setup

The service account that CI authenticates as is itself managed by terraform,
so **the very first apply has to be run locally** (chicken and egg). Once it is
done, everything else runs in CI.

### 1. Create the state bucket

It is not managed by terraform, so create it by hand.

```sh
gcloud storage buckets create gs://kagoole-379522-tfstate \
  --project=kagoole-379522 \
  --location=asia-northeast1 \
  --uniform-bucket-level-access \
  --public-access-prevention

gcloud storage buckets update gs://kagoole-379522-tfstate --versioning
```

### 2. Run the first apply

The GCS backend reads Application Default Credentials, which `gcloud auth
login` alone does not create.

```sh
gcloud auth login
gcloud auth application-default login
cd terraform
terraform init
terraform plan    # review the output first
terraform apply
```

This creates the `terraform-github-actions` service account, its `roles/owner`
binding, and the workload identity binding, after which CI can authenticate.

### 3. Verify

```sh
gcloud iam service-accounts describe \
  terraform-github-actions@kagoole-379522.iam.gserviceaccount.com \
  --project=kagoole-379522

gcloud iam service-accounts get-iam-policy \
  terraform-github-actions@kagoole-379522.iam.gserviceaccount.com \
  --project=kagoole-379522
```

The policy should carry `roles/iam.workloadIdentityUser` for
`principalSet://.../attribute.repository/Doarakko/kagoole-twitter`.

Then push a commit and confirm the `terraform plan` workflow goes green.

**Wait a few minutes before running CI.** The workload identity binding takes
time to propagate, and a run started immediately after the apply fails with
`Permission 'iam.serviceAccounts.getAccessToken' denied` even though the policy
above is already correct. Re-running the job after a few minutes is enough; do
not start changing the configuration.

## Notes

- The `terraform-github-actions` service account and its two IAM bindings are
  guarded with `lifecycle { prevent_destroy = true }`, because losing them
  locks CI out of its own project and recovery requires a local apply. This
  does **not** protect against deleting the resource blocks themselves, since
  the `lifecycle` setting lives in the config rather than in the state.
- The CI service account needs `roles/owner` because this config also creates
  service accounts, grants project IAM, and enables APIs. If you ever want to
  narrow that down, that is the point at which to split the bootstrap
  resources into a separate state.
- Secret Manager values are not managed by terraform. Only the secret
  resources are created here; the values are registered separately.
