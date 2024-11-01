terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.9.0"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
