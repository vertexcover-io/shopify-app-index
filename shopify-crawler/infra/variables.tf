variable "version" {}

variable "location" {
  default = "centralindia"
}

variable "environment" {
  default = "production"
}

variable "docker-image"{
  default = "vertexcover/shopify-crawler"
}

variable "container" {
  type = "map"
  default = {
    cpu = "0.5"
    memory = "1.5"
  }
}

variable "max_crawler_workers" {
  default = "20"
}


variable "gcloud_creds_file" {}
variable "user_object_id" {}


