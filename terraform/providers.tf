terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.73.2"
    }
  }

  cloud {
    organization = "Doarakko"

    workspaces {
      name = "kagoole-twitter"
    }
  }
}
