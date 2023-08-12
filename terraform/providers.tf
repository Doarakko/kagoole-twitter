terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.77.0"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
