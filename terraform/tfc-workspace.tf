provider "tfe" {
  hostname = var.tfc_hostname
}

data "tfe_organization" "organization" {
  name = var.tfc_organization_name
}

data "tfe_workspace" "workspace" {
  organization = data.tfe_organization.organization.name
  name         = var.tfc_workspace_name
}

resource "tfe_variable" "enable_gcp_provider_auth" {
  workspace_id = data.tfe_workspace.workspace.id

  key      = "TFC_GCP_PROVIDER_AUTH"
  value    = "true"
  category = "env"

  description = "Enable the Workload Identity integration for GCP."
}

resource "tfe_variable" "tfc_gcp_project_number" {
  workspace_id = data.tfe_workspace.workspace.id

  key      = "TFC_GCP_PROJECT_NUMBER"
  value    = data.google_project.project.number
  category = "env"

  description = "The numeric identifier of the GCP project"
}

resource "tfe_variable" "tfc_gcp_workload_pool_id" {
  workspace_id = data.tfe_workspace.workspace.id

  key      = "TFC_GCP_WORKLOAD_POOL_ID"
  value    = google_iam_workload_identity_pool.tfc_pool.workload_identity_pool_id
  category = "env"

  description = "The ID of the workload identity pool."
}

resource "tfe_variable" "tfc_gcp_workload_provider_id" {
  workspace_id = data.tfe_workspace.workspace.id

  key      = "TFC_GCP_WORKLOAD_PROVIDER_ID"
  value    = google_iam_workload_identity_pool_provider.tfc_provider.workload_identity_pool_provider_id
  category = "env"

  description = "The ID of the workload identity pool provider."
}

resource "tfe_variable" "tfc_gcp_service_account_email" {
  workspace_id = data.tfe_workspace.workspace.id

  key      = "TFC_GCP_RUN_SERVICE_ACCOUNT_EMAIL"
  value    = google_service_account.tfc_service_account.email
  category = "env"

  description = "The GCP service account email runs will use to authenticate."
}
