data "local_file" "gcloud_creds" {
  filename = "${var.gcloud_creds_file}"
}


provider "azurerm" {
  version = "=1.21.0"
}

data "azurerm_client_config" "currentClient" {}


resource "azurerm_resource_group" "shopifyCrawlerGroup" {
  name     = "shopifyCrawlerGroup"
  location = "${var.location}"

  tags {
    environment = "${var.environment}"
  }
}

resource "azurerm_user_assigned_identity" "shopifyCrawlerIdentity" {
  resource_group_name      = "${azurerm_resource_group.shopifyCrawlerGroup.name}"
  location                 = "${azurerm_resource_group.shopifyCrawlerGroup.location}"

  name = "shopifyCrawlerIdentity"
}


resource "azurerm_key_vault" "shopifyVault" {
  name = "shofiyVault"
  resource_group_name      = "${azurerm_resource_group.shopifyCrawlerGroup.name}"
  location                 = "${azurerm_resource_group.shopifyCrawlerGroup.location}"
  enabled_for_disk_encryption = true
  enabled_for_deployment  = true
  sku {
      name = "standard"
  }
  tenant_id = "${data.azurerm_client_config.currentClient.tenant_id}"

  access_policy {
     tenant_id = "${data.azurerm_client_config.currentClient.tenant_id}"
     object_id = "${var.user_object_id}"

     key_permissions = [
       "create",
       "get",
       "list"
     ]

     secret_permissions = [
       "set",
       "get",
       "delete",
       "list"
     ]
   }

  access_policy {
    tenant_id = "${data.azurerm_client_config.currentClient.tenant_id}"
    object_id = "${azurerm_user_assigned_identity.shopifyCrawlerIdentity.principal_id}"
    secret_permissions = [
      "get"
    ]

  }

  tags {
    environment = "${var.environment}"
  }

}

resource "azurerm_key_vault_secret" "gcloudCreds" {
  name      = "gcloudCreds"
  value     = "${data.local_file.gcloud_creds.content}"
  vault_uri = "${azurerm_key_vault.shopifyVault.vault_uri}"
  content_type = "application/json"
  tags {
    environment = "${var.environment}"
  }
}

resource "azurerm_container_registry" "shopifyCrawlerRegistry" {
  name                     = "shopifyCrawlerRegistry"
  resource_group_name      = "${azurerm_resource_group.shopifyCrawlerGroup.name}"
  location                 = "${azurerm_resource_group.shopifyCrawlerGroup.location}"
  sku                      = "Basic"
  admin_enabled            = true

  tags {
    environment = "${var.environment}"
  }

  provisioner "local-exec" {
    command = "docker tag ${var.docker-image} ${azurerm_container_registry.shopifyCrawlerRegistry.login_server}/${var.docker-image}"
  }
}



//resource "azurerm_container_group" "shopifyCrawlerContainer" {
//  name                = "shopifyCrawlerContainer"
//  location            = "${azurerm_resource_group.shopifyCrawlerGroup.location}"
//  resource_group_name = "${azurerm_resource_group.shopifyCrawlerGroup.name}"
//  ip_address_type     = "private"
//  os_type             = "Linux"
//
//  image_registry_credential {
//    password = "${azurerm_container_registry.shopifyCrawlerRegistry.admin_password}"
//    server = "${azurerm_container_registry.shopifyCrawlerRegistry.login_server}"
//    username = "${azurerm_container_registry.shopifyCrawlerRegistry.admin_username}"
//  }
//
//  container {
//    name   = "vertexcover/shopifyCrawler"
//    image  = "${var.docker-image}"
//    cpu    = "${var.container.cpu}"
//    memory = "${var.container.memory}"
//
//    environment_variables {
//      "PROJECT_ENV" = "${var.environment}"
//      "MAX_WORKERS" = "${var.max_crawler_workers}"
//      "VERSION" = "${var.version}"
//    }
//  }
//
//  tags {
//    environment = "${var.environment}"
//    version = "${var.version}"
//  }
//}







