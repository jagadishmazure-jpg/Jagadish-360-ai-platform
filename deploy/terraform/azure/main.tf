# VALIDATED ONLY - never applied from this repo. Applying creates billable resources (GPU VMs are expensive).
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}

provider "azurerm" {
  features {}
}

variable "prefix" {
  type    = string
  default = "p360"
}
variable "location" {
  type    = string
  default = "eastus2"
}
variable "gpu_vm_size" {
  type    = string
  default = "Standard_NC4as_T4_v3"
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "azurerm_key_vault" "kv" {
  name                          = "${var.prefix}-kv"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  tenant_id                     = data.azurerm_client_config.me.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  public_network_access_enabled = false
}

data "azurerm_client_config" "me" {}

resource "azurerm_kubernetes_cluster" "aks" {
  name                      = "${var.prefix}-aks"
  location                  = azurerm_resource_group.rg.location
  resource_group_name       = azurerm_resource_group.rg.name
  dns_prefix                = var.prefix
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  local_account_disabled    = true
  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.me.tenant_id
  }
  default_node_pool {
    name       = "system"
    vm_size    = "Standard_D4s_v5"
    node_count = 2
  }
  identity {
    type = "SystemAssigned"
  }
  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }
  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }
}

resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.aks.id
  vm_size               = var.gpu_vm_size
  node_count            = 1
  node_taints           = ["sku=gpu:NoSchedule"]
}
