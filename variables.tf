variable "service_account_key_file" {
  type        = string
  description = "file with auth for initial service account"
}

variable "cloud_id" {
  type        = string
  description = "cloud id"
}

variable "folder_id" {
  type        = string
  description = "folder id"
}

variable "tgkey" {
  type        = string
  description = "tgkey"
}

variable "bucket_faces" {
  type        = string
  description = "bucket with faces"
}

variable "bucket_photo" {
  type        = string
  description = "bucket with original photos"
}