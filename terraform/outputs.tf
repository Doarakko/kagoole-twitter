output "gh_actions_google_workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github_actions.name
}

output "gh_actions_google_service_account" {
  value = google_service_account.github_actions.email
}
