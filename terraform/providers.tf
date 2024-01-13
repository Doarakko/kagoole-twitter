terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.11.0"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
