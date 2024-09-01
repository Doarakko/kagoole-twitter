terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.0.1"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
