# terraform

## 構成

| 項目 | 値 |
| --- | --- |
| GCP プロジェクト | `kagoole-379522` (project number `631578640507`) |
| リージョン | `asia-northeast1` |
| backend | GCS `gs://kagoole-379522-tfstate` / prefix `terraform/state` |
| terraform バージョン | `.terraform-version`（リポジトリルート）で固定 |

state バケットは **terraform 管理外**です。backend の保存先を backend 自身の state で管理できないことと、誤った apply で state ごと失うのを防ぐためです。

## 日常の運用

CI がすべて実行するので、通常ローカルで apply する必要はありません。

| タイミング | 実行内容 | workflow |
| --- | --- | --- |
| pull request | `fmt` / `init` / `validate` / `plan` → 結果を PR にコメント | `.github/workflows/terraform_plan.yml` |
| `main` へ merge | `apply -auto-approve` | `.github/workflows/terraform_apply.yml` |

GCP 認証は Workload Identity Federation によるキーレス認証で、service account key は使いません。

| 用途 | service account | 権限 |
| --- | --- | --- |
| terraform (CI) | `terraform-github-actions@kagoole-379522.iam.gserviceaccount.com` | `roles/owner` |
| コンテナ build / deploy (`deploy.yml`) | `github-actions@kagoole-379522.iam.gserviceaccount.com` | `artifactregistry.admin`, `run.developer`, `iam.serviceAccountUser` |

どちらも workload identity pool `gh-oidc-pool` を共有し、`attribute.repository` がこのリポジトリの場合のみ引き受け可能です。

## ローカルで実行する

state を直接触るため、通常は plan までに留めてください。

```sh
gcloud auth application-default login
cd terraform
terraform init
terraform plan
```

## 初回セットアップ

CI が使う service account そのものを terraform で管理しているため、**最初の 1 回だけはローカルからの apply が必要**です（鶏と卵）。これを終えれば以降は CI だけで回ります。

### 1. state バケットを作成する

terraform 管理外なので手動で作成します。

```sh
gcloud storage buckets create gs://kagoole-379522-tfstate \
  --project=kagoole-379522 \
  --location=asia-northeast1 \
  --uniform-bucket-level-access \
  --public-access-prevention

gcloud storage buckets update gs://kagoole-379522-tfstate --versioning
```

### 2. 初回 apply

```sh
gcloud auth application-default login
cd terraform
terraform init
terraform plan    # 内容を確認してから
terraform apply
```

これで `terraform-github-actions` service account、`roles/owner` の付与、workload identity のバインディングが作成され、CI が認証できるようになります。

### 3. 確認

```sh
gcloud iam service-accounts describe \
  terraform-github-actions@kagoole-379522.iam.gserviceaccount.com \
  --project=kagoole-379522
```

## 注意

- `terraform-github-actions` の service account と 2 つの IAM バインディングには `lifecycle { prevent_destroy = true }` を設定しています。これらが消えると CI が自分自身をロックアウトし、ローカル apply でしか復旧できないためです。ただし **リソースブロックごと削除した場合は効きません**（`lifecycle` の設定は state ではなく config 側にあるため）。
- CI の service account が `roles/owner` を持つのは、この config が service account 作成・プロジェクト IAM 付与・API 有効化まで含むためです。将来 CI を最小権限にしたくなったら、ブートストラップ部分（`cicd` 相当）を別 state に切り出すタイミングです。
- Secret Manager に登録する値そのものは terraform 管理外です。secret のリソースだけを作成し、値は別途登録します。

## 付録: HCP Terraform からの移行（一度きり）

以前は HCP Terraform (org `Doarakko` / workspace `kagoole-twitter`) を backend にしていました。移行が完了していれば、この節は削除して構いません。

```sh
cd terraform

# cloud {} ブロックが残っている状態で state を吸い出してバックアップする
git switch main
terraform login
terraform init
terraform state pull > /tmp/kagoole-twitter.tfstate

# tfe provider ごと廃止するため、tfe_variable を state から外す
for r in enable_gcp_provider_auth tfc_gcp_project_number tfc_gcp_workload_pool_id \
         tfc_gcp_workload_provider_id tfc_gcp_service_account_email; do
  terraform state rm "tfe_variable.$r"
done

# GCS backend に切り替えた状態で state を移行する
git switch <このブランチ>
terraform init -migrate-state
terraform state list
```

移行後、HCP Terraform の workspace は削除します。**この workspace はこのリポジトリと VCS 連携しているため、削除するまで PR に失敗した `Terraform Cloud` チェックが出続けます。**

初回 apply では、TFC 用に作られていた以下のリソースが destroy されます。

- `google_iam_workload_identity_pool.tfc_pool` (`my-tfc-pool`)
- `google_iam_workload_identity_pool_provider.tfc_provider` (`my-tfc-provider-id`)
- `google_service_account.tfc_service_account` (`tfc-service-account`)
- `google_project_iam_member.tfc_project_member` (`roles/editor`)
