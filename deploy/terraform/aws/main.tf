# VALIDATED ONLY - never applied from this repo. Applying creates billable resources.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "subnet_ids" {
  type    = list(string)
  default = []
}
variable "gpu_instance_type" {
  type    = string
  default = "g6.xlarge"
}

data "aws_iam_policy_document" "eks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "node_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "p360-eks-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_assume.json
}

resource "aws_iam_role" "node" {
  name               = "p360-eks-node"
  assume_role_policy = data.aws_iam_policy_document.node_assume.json
}

resource "aws_kms_key" "eks" {
  description         = "p360 EKS secrets encryption"
  enable_key_rotation = true
}

resource "aws_eks_cluster" "this" {
  name     = "p360"
  role_arn = aws_iam_role.cluster.arn
  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_public_access  = false
    endpoint_private_access = true
  }
  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks.arn
    }
  }
  enabled_cluster_log_types = ["api", "audit", "authenticator"]
}

resource "aws_eks_node_group" "gpu" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "gpu"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  instance_types  = [var.gpu_instance_type]
  ami_type        = "AL2023_x86_64_NVIDIA"
  scaling_config {
    desired_size = 1
    min_size     = 0
    max_size     = 2
  }
  taint {
    key    = "nvidia.com/gpu"
    effect = "NO_SCHEDULE"
  }
  labels = { "p360/gpu" = "true" }
}
