terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  service_account_key_file = var.service_account_key_file
  cloud_id = var.cloud_id
  folder_id = var.folder_id
  zone = "ru-central1-a"
}

resource "yandex_iam_service_account" "sa" {
  name = "vvot03-sa-task1"
}

resource "yandex_resourcemanager_folder_iam_member" "sa-admin" {
  folder_id = var.folder_id
  role      = "admin"
  member    = "serviceAccount:${yandex_iam_service_account.sa.id}"
}

resource "yandex_iam_service_account_static_access_key" "sa-static-key" {
  service_account_id = yandex_iam_service_account.sa.id
  description        = "static access key for service account"
}

resource "yandex_storage_bucket" "vvot03-photo" {
	access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
	secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
	bucket = "vvot03-photo"
}

resource "yandex_function" "vvot03-face-detection" {
  name               = "vvot-03-face-detection"
  description        = "Обработчик фотографий"
  user_hash          = "any_user_defined_string"
  runtime            = "python311"
  entrypoint         = "face-detection.handler"
  memory             = "128"
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.sa.id
  content {
    zip_filename = "face-detection.zip"
  }
  
  environment = {
    QUEUE_URL = yandex_message_queue.vvot03-task.id
    AWS_ACCESS_KEY_ID = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
    AWS_DEFAULT_REGION = "ru-central1-a"
  }
}

resource "yandex_function_iam_binding" "vvot03-face-detection-iam" {
  function_id = yandex_function.vvot03-face-detection.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}

resource "yandex_function_trigger" "vvot03-photo" {
  name        = "vvot03-photo"
  description = "trigger for invoking cloud function for photos"
  object_storage {
     batch_cutoff = 3
     bucket_id = yandex_storage_bucket.vvot03-photo.id
     create    = true
  }
  function {
    id                 = yandex_function.vvot03-face-detection.id
    service_account_id = yandex_iam_service_account.sa.id
  } 
}

resource "yandex_message_queue" "vvot03-task" {
	name = "vvot03-task"
	visibility_timeout_seconds = 600
	receive_wait_time_seconds = 20
	message_retention_seconds = 1209600
	access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
	secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
}

resource "yandex_ydb_database_serverless" "vvot03-db-photo-face" {
  name                = "vvot03-db-photo-face"
  deletion_protection = true

  serverless_database {
    enable_throttling_rcu_limit = false
    provisioned_rcu_limit       = 10
    storage_size_limit          = 5
    throttling_rcu_limit        = 0
  }
}

resource "yandex_ydb_table" "photo_originals" {
  path = "photo_originals"
  connection_string = yandex_ydb_database_serverless.vvot03-db-photo-face.ydb_full_endpoint

column {
      name = "original_key"
      type = "Utf8"
      not_null = true
    }
column {
      name = "cut_key"
      type = "Utf8"
      not_null = true
    }
column {
        name = "has_name"
        type = "Bool"
    }

column {
        name = "name"
        type = "string"
    }

  primary_key = ["original_key","cut_key"]

}

resource "yandex_function" "vvot03-face-cut" {
  name               = "vvot-03-face-cut"
  description        = "Обрезка фотографий"
  user_hash          = "any_user_defined_string"
  runtime            = "python311"
  entrypoint         = "face-cut.handler"
  memory             = "128"
  execution_timeout  = "50"
  service_account_id = yandex_iam_service_account.sa.id
  content {
    zip_filename = "face-cut.zip"
  }
  
  environment = {
    AWS_ACCESS_KEY_ID = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
    AWS_DEFAULT_REGION = "ru-central1-a"
    DATABASE_URL = yandex_ydb_database_serverless.vvot03-db-photo-face.ydb_full_endpoint
    FACE_STORAGE = var.bucket_faces
    PHOTO_STORAGE = var.bucket_photo
  }
}

resource "yandex_function_iam_binding" "vvot03-face-cut-iam" {
  function_id = yandex_function.vvot03-face-cut.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}


resource "yandex_function_trigger" "vvot03-task" {
    name = "vvot03-task"
    description = "trigger that invokes face cutting function"
    message_queue {
        queue_id = yandex_message_queue.vvot03-task.arn
        service_account_id = yandex_iam_service_account.sa.id
        batch_size = "1"
        batch_cutoff = "10"
    }
    function {
        id = yandex_function.vvot03-face-cut.id
    }
}

resource "yandex_storage_bucket" "vvot03-faces" {
	access_key = yandex_iam_service_account_static_access_key.sa-static-key.access_key
	secret_key = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
	bucket = "vvot03-faces"
}

resource "yandex_api_gateway" "vvot03-apigw" {
  name = "vvot03-apigw"
  description = "api gateway for faces"
  labels = {
    label       = "label"
    empty-label = ""
  }
  spec = <<-EOT
openapi: 3.0.0
info:
  title: vvot03-apigw
  version: 1.0.0
paths:
  /:
    get:
      parameters:
      - name: face
        in: query
        description: 'key of object in object storage'
        required: true
        schema:
          type: string
      responses:
        '200':
          description: OK
          content:
              image/png:
                schema: 
                  type: string
                  format: binary
      x-yc-apigateway-integration:
        type: object_storage
        bucket: ${var.bucket_faces}
        object: '{face}'
        presigned_redirect: false
        service_account_id: ${yandex_iam_service_account.sa.id}
        operationId: static
        responses:
        '200':
          description: OK
          content:
              image/png:
                schema: 
                  type: string
                  format: binary
EOT
}

resource "yandex_function" "vvot03-boot" {
  name               = "vvot03-boot"
  description        = "Обработчик для бота"
  user_hash          = "any_user_defined_string1"
  runtime            = "python311"
  entrypoint         = "bot.handler"
  memory             = "128"
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.sa.id
  tags               = ["my_tag"]
  content {
    zip_filename = "3.zip"
  }
  environment = {
    APITG = yandex_api_gateway.vvot03-apigw.id
    TGKEY = var.tgkey
    DATABASE_URL = yandex_ydb_database_serverless.vvot03-db-photo-face.ydb_full_endpoint
    AWS_ACCESS_KEY_ID = yandex_iam_service_account_static_access_key.sa-static-key.access_key
    AWS_SECRET_ACCESS_KEY = yandex_iam_service_account_static_access_key.sa-static-key.secret_key
    AWS_DEFAULT_REGION = "ru-central1-a"
    FACE_STORAGE = var.bucket_faces
    PHOTO_STORAGE = var.bucket_photo
  }
}

resource "yandex_function_iam_binding" "vvot03-boot-iam" {
  function_id = yandex_function.vvot03-boot.id
  role        = "serverless.functions.invoker"

  members = [
    "system:allUsers",
  ]
}

output "bot_id" {
  value = yandex_function.vvot03-boot.id
}

data "http" "webhook" {
  url = "https://api.telegram.org/bot6761917445:AAFhQOcud0sTuDwgYb4lk0tXzFPvbnrq7t8/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.vvot03-boot.id}"
}

