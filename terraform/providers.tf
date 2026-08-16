terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.36.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "5.36.0"
    }
  }

  backend "gcs" {
    bucket = "kagoole-379522-tfstate"
    prefix = "terraform/state"
  }
}
