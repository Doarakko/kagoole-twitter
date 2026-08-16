# [Kagoole Twitter](https://twitter.com/kagoole)

Tweet when new [Kaggle](https://www.kaggle.com/) competition is launched.

Please follow and enjoy Kaggle!

![example](./example.png)

## Infrastructure

Terraform state is stored in `gs://kagoole-379522-tfstate`.

- Pull request: `terraform plan` runs and the result is posted as a comment
- Merge to `main`: `terraform apply` runs

GCP authentication uses Workload Identity Federation, so no service account key is required.

## Reference

- [Kagoole](https://github.com/Doarakko/kagoole)
