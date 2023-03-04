terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.53.1"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = "asia-northeast1-a"
}

provider "google-beta" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

data "google_project" "project" {
}

resource "google_project_service" "project" {
  project = var.gcp_project_id
  for_each = toset([
    "iamcredentials.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "sts.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])
  service = each.value
}

resource "google_iam_workload_identity_pool" "tfc_pool" {
  provider                  = google-beta
  workload_identity_pool_id = "my-tfc-pool"
}

resource "google_iam_workload_identity_pool_provider" "tfc_provider" {
  provider                           = google-beta
  workload_identity_pool_id          = google_iam_workload_identity_pool.tfc_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "my-tfc-provider-id"
  attribute_mapping = {
    "google.subject"                        = "assertion.sub",
    "attribute.aud"                         = "assertion.aud",
    "attribute.terraform_run_phase"         = "assertion.terraform_run_phase",
    "attribute.terraform_project_id"        = "assertion.terraform_project_id",
    "attribute.terraform_project_name"      = "assertion.terraform_project_name",
    "attribute.terraform_workspace_id"      = "assertion.terraform_workspace_id",
    "attribute.terraform_workspace_name"    = "assertion.terraform_workspace_name",
    "attribute.terraform_organization_id"   = "assertion.terraform_organization_id",
    "attribute.terraform_organization_name" = "assertion.terraform_organization_name",
    "attribute.terraform_run_id"            = "assertion.terraform_run_id",
    "attribute.terraform_full_workspace"    = "assertion.terraform_full_workspace",
  }
  oidc {
    issuer_uri = "https://${var.tfc_hostname}"
  }
  attribute_condition = "assertion.sub.startsWith(\"organization:${var.tfc_organization_name}:project:${var.tfc_project_name}:workspace:${var.tfc_workspace_name}\")"
}

resource "google_service_account" "tfc_service_account" {
  account_id   = "tfc-service-account"
  display_name = "Terraform Cloud Service Account"
}

resource "google_service_account_iam_member" "tfc_service_account_member" {
  service_account_id = google_service_account.tfc_service_account.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.tfc_pool.name}/*"
}

resource "google_project_iam_member" "tfc_project_member" {
  project = var.gcp_project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.tfc_service_account.email}"
}

resource "google_service_account" "github_actions" {
  project      = var.gcp_project_id
  account_id   = "github-actions"
  display_name = "A service account for GitHub Actions"
}

resource "google_iam_workload_identity_pool" "github_actions" {
  provider                  = google-beta
  project                   = var.gcp_project_id
  workload_identity_pool_id = "gh-oidc-pool"
  display_name              = "gh-oidc-pool"
  description               = "Workload Identity Pool for GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  provider                           = google-beta
  project                            = var.gcp_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "gh-oidc-provider"
  display_name                       = "gh-oidc-provider"
  description                        = "OIDC identity pool provider for GitHub Actions"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "admin_account_iam" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.gh_repo_name}"
}

resource "google_project_iam_member" "admin_account_iam" {
  project  = var.gcp_project_id
  for_each = toset(["roles/iam.serviceAccountUser", "roles/artifactregistry.admin", "roles/run.developer"])
  role     = each.value
  member   = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_cloud_run_v2_job" "default" {
  name         = "kagoole-twitter"
  location     = var.gcp_region
  launch_stage = "BETA"

  template {
    template {
      dynamic "volumes" {
        for_each = toset([
          google_secret_manager_secret.kaggle_username,
          google_secret_manager_secret.kaggle_key,
          google_secret_manager_secret.twitter_bearer_token,
          google_secret_manager_secret.twitter_consumer_key,
          google_secret_manager_secret.twitter_consumer_secret,
          google_secret_manager_secret.twitter_access_token,
          google_secret_manager_secret.twitter_access_token_secret
        ])

        content {
          name = "a-volume"
          secret {
            secret       = volumes.value.id
            default_mode = 292
            items {
              version = "1"
              path    = "my-secret"
              mode    = 256
            }
          }
        }
      }

      containers {
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        dynamic "volume_mounts" {
          for_each = toset([
            google_secret_manager_secret.kaggle_username,
            google_secret_manager_secret.kaggle_key,
            google_secret_manager_secret.twitter_bearer_token,
            google_secret_manager_secret.twitter_consumer_key,
            google_secret_manager_secret.twitter_consumer_secret,
            google_secret_manager_secret.twitter_access_token,
            google_secret_manager_secret.twitter_access_token_secret
          ])

          content {
            name       = "a-volume"
            mount_path = "/secrets"
          }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.gcp_project_id
        }
        env {
          name = "KAGGLE_USERNAME"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.kaggle_username.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "KAGGLE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.kaggle_key.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.default]
}

resource "google_secret_manager_secret" "kaggle_username" {
  secret_id = "kaggle_username"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "kaggle_username" {
  secret      = google_secret_manager_secret.kaggle_username.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "kaggle_key" {
  secret_id = "kaggle_key"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "kaggle_key" {
  secret      = google_secret_manager_secret.kaggle_key.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "twitter_bearer_token" {
  secret_id = "twitter_bearer_token"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "twitter_bearer_token" {
  secret      = google_secret_manager_secret.twitter_bearer_token.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "twitter_consumer_key" {
  secret_id = "twitter_consumer_key"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "twitter_consumer_key" {
  secret      = google_secret_manager_secret.twitter_consumer_key.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "twitter_consumer_secret" {
  secret_id = "twitter_consumer_secret"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "twitter_consumer_secret" {
  secret      = google_secret_manager_secret.twitter_consumer_secret.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "twitter_access_token" {
  secret_id = "twitter_access_token"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "twitter_access_token" {
  secret      = google_secret_manager_secret.twitter_access_token.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret" "twitter_access_token_secret" {
  secret_id = "twitter_access_token_secret"

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "twitter_access_token_secret" {
  secret      = google_secret_manager_secret.twitter_access_token_secret.name
  secret_data = "please enter in console"
}

resource "google_secret_manager_secret_iam_member" "default" {
  for_each = toset([
    google_secret_manager_secret.kaggle_username,
    google_secret_manager_secret.kaggle_key,
    google_secret_manager_secret.twitter_bearer_token,
    google_secret_manager_secret.twitter_consumer_key,
    google_secret_manager_secret.twitter_consumer_secret,
    google_secret_manager_secret.twitter_access_token,
    google_secret_manager_secret.twitter_access_token_secret
  ])
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
  depends_on = [
    google_secret_manager_secret.kaggle_username,
    google_secret_manager_secret.kaggle_key,
    google_secret_manager_secret.twitter_bearer_token,
    google_secret_manager_secret.twitter_consumer_key,
    google_secret_manager_secret.twitter_consumer_secret,
    google_secret_manager_secret.twitter_access_token,
    google_secret_manager_secret.twitter_access_token_secret
  ]
}

resource "google_cloud_scheduler_job" "default" {
  name = "kagoole-twitter-job"
  # if you change execution schedule, you must change interval too(job/main.py).
  schedule         = "* /10 * * * *"
  time_zone        = "Asia/Tokyo"
  attempt_deadline = "180s"
  region           = var.gcp_region

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.gcp_region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.gcp_project_id}/jobs/kagoole-twitter:run"

    oauth_token {
      service_account_email = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"
    }
  }
}
