terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.14.1"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
