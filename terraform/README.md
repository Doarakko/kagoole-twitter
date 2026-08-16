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

## Appendix: migrating off HCP Terraform (one-time)

The backend used to be HCP Terraform (organization `Doarakko`, workspace
`kagoole-twitter`). Once the migration is complete, this section can be
deleted.

Terraform cannot migrate off HCP Terraform on its own. Both `terraform init`
and `terraform init -migrate-state` refuse the move, so the state has to be
carried across by hand with `state pull` and `state push`.

No separate backup is needed along the way. HCP Terraform keeps every state
version, and the pulled file doubles as one until the workspace is deleted.

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

# Pull the state out. Keep this file until CI is green; it is the only copy
# that survives deleting the workspace.
terraform state pull > ~/kagoole-tfstate.json

# init on main generates an untracked .terraform.lock.hcl, and the branch
# tracks that path, so the switch below fails unless it is removed first
rm .terraform.lock.hcl
rm -rf .terraform

# Push the state into the empty GCS backend
git switch <this branch>
terraform init
terraform state push ~/kagoole-tfstate.json
terraform state list   # seven fewer entries than before the state rm
```

`grep -c '"mode"'` on the pulled file counts resource blocks, not instances, so
it will not match `terraform state list`. Two resources use `for_each`. Count
instances instead:

```sh
python3 -c "
import json, os
d = json.load(open(os.path.expanduser('~/kagoole-tfstate.json')))
print(sum(len(r['instances']) for r in d['resources']))
"
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
