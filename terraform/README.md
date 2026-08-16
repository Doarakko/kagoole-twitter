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

```sh
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
```

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

## Appendix: migrating off HCP Terraform (one-time)

The backend used to be HCP Terraform (organization `Doarakko`, workspace
`kagoole-twitter`). Once the migration is complete, this section can be
deleted.

No separate backup is needed along the way. HCP Terraform keeps every state
version, and the migration copies rather than moves, so the source state stays
intact until the workspace is deleted.

The workspace pins its Terraform version. If it is older than the version in
`.terraform-version`, state writes are rejected with `Incompatible Terraform
version` while reads still succeed. Raise it under **Settings > General >
Terraform Version** before starting; the workspace is going away anyway.

```sh
cd terraform

# Start from main, where the cloud {} block is still in place
git switch main
terraform login
terraform init
terraform state list

# The tfe provider is going away, so drop everything that belongs to it,
# including the two data sources. Leaving them behind makes the state require
# hashicorp/tfe, which is absent from the branch's .terraform.lock.hcl and
# breaks the init below.
#
# This only edits the state; it never calls the provider, so no TFE token is
# needed and the variables in the HCP Terraform workspace are left alone.
terraform state rm \
  tfe_variable.enable_gcp_provider_auth \
  tfe_variable.tfc_gcp_project_number \
  tfe_variable.tfc_gcp_workload_pool_id \
  tfe_variable.tfc_gcp_workload_provider_id \
  tfe_variable.tfc_gcp_service_account_email \
  data.tfe_organization.organization \
  data.tfe_workspace.workspace

# init on main generates an untracked .terraform.lock.hcl, and the branch
# tracks that path, so the switch below fails unless it is removed first
rm .terraform.lock.hcl

# Migrate the state with the GCS backend in place. Note that -migrate-state
# is rejected here: it only covers backend-to-backend moves, and migrating off
# HCP Terraform is driven by interactive prompts on a plain init instead.
git switch <this branch>
terraform init
terraform state list   # seven fewer entries than before the state rm
```

Delete the HCP Terraform workspace once CI is green. **It is connected to this
repository over VCS, so a failing `Terraform Cloud` check keeps appearing on
every pull request until the workspace is gone.** Deleting it also discards the
retained state versions, so leave it in place until the migration is confirmed.

The first apply destroys the resources that existed only for HCP Terraform:

- `google_iam_workload_identity_pool.tfc_pool` (`my-tfc-pool`)
- `google_iam_workload_identity_pool_provider.tfc_provider` (`my-tfc-provider-id`)
- `google_service_account.tfc_service_account` (`tfc-service-account`)
- `google_service_account_iam_member.tfc_service_account_member`
- `google_project_iam_member.tfc_project_member` (`roles/editor`)

So the first plan should show five destroys and three creates.
