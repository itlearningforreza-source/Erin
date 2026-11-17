terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr_block = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway     = true
  single_nat_gateway     = false
  enable_dns_hostnames   = true
  enable_dns_support     = true
  enable_classiclink     = false
  assign_generated_ipv6_cidr_block = false

  tags = {
    Environment = var.environment
    Cluster     = var.cluster_name
    ManagedBy   = "terraform"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "karpenter.sh/discovery"          = var.cluster_name
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
    "karpenter.sh/discovery" = var.cluster_name
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnets
  cluster_endpoint_public_access = true

  cluster_addons = {
    vpc-cni = {
      most_recent = true
    }
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    eks-pod-identity-agent = {
      most_recent = true
    }
  }

  cluster_encryption_config = [{
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }]

  eks_managed_node_group_defaults = {
    ami_type       = "AL2_x86_64"
    instance_types = ["m6i.xlarge"]
    capacity_type  = "ON_DEMAND"

    labels = {
      Environment = var.environment
      ManagedBy   = "terraform"
    }

    tags = {
      Environment = var.environment
      Cluster     = var.cluster_name
      ManagedBy   = "terraform"
    }
  }

  eks_managed_node_groups = {
    system = {
      name           = "system"
      instance_types = ["m6i.large"]
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 10
      desired_size = 3

      labels = {
        workload-type = "system"
        node-group    = "system"
      }

      taints = [{
        key    = "workload-type"
        value  = "system"
        effect = "NO_SCHEDULE"
      }]

      ami_type = "AL2_x86_64"
    }

    platform = {
      name           = "platform"
      instance_types = ["m6i.xlarge", "m6i.2xlarge"]
      capacity_type  = "ON_DEMAND"

      min_size     = 3
      max_size     = 20
      desired_size = 5

      labels = {
        workload-type = "platform"
        node-group    = "platform"
      }

      ami_type = "AL2_x86_64"
    }

    data = {
      name           = "data"
      instance_types = ["r6i.xlarge", "r6i.2xlarge"]
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 10
      desired_size = 3

      labels = {
        workload-type = "data"
        node-group    = "data"
      }

      ami_type = "AL2_x86_64"
    }

    ml = {
      name           = "ml"
      instance_types = ["g5.xlarge", "g5.2xlarge"]
      capacity_type  = "ON_DEMAND"

      min_size     = 0
      max_size     = 5
      desired_size = 0

      labels = {
        workload-type = "ml"
        node-group    = "ml"
        nvidia.com/gpu = "true"
      }

      ami_type = "AL2_x86_64_GPU"
      gpu = true
    }
  }

  # Enable IRSA
  irsa_enabled = true

  # Enable Cluster Autoscaler
  cluster_autoscaler_enabled = true
}

# KMS key for EKS encryption
resource "aws_kms_key" "eks" {
  description = "KMS key for EKS cluster ${var.cluster_name} encryption"
  deletion_window_in_days = 30
  enable_key_rotation = true
}

# IAM roles for service accounts (IRSA)
module "iam_roles" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-roles-with-oidc"
  version = "~> 5.0"

  oidc_provider_arn = module.eks.oidc_provider_arn

  roles = {
    argocd = {
      name = "${var.cluster_name}-argocd"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:argocd:argocd-server",
        "system:serviceaccount:argocd:argocd-repo-server",
        "system:serviceaccount:argocd:argocd-application-controller"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/AdministratorAccess"
      ]
    }

    external-dns = {
      name = "${var.cluster_name}-external-dns"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:external-dns:external-dns"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/Route53FullAccess"
      ]
    }

    cert-manager = {
      name = "${var.cluster_name}-cert-manager"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:cert-manager:cert-manager"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/AdministratorAccess"
      ]
    }

    aws-load-balancer-controller = {
      name = "${var.cluster_name}-aws-load-balancer-controller"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:kube-system:aws-load-balancer-controller"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
      ]
    }

    ebs-csi-driver = {
      name = "${var.cluster_name}-ebs-csi-driver"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/AmazonEBSCSIDriverPolicy"
      ]
    }

    cluster-autoscaler = {
      name = "${var.cluster_name}-cluster-autoscaler"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:kube-system:cluster-autoscaler"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/AutoScalingFullAccess",
        "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
      ]
    }

    karpenter = {
      name = "${var.cluster_name}-karpenter"
      oidc_fully_qualified_subjects = [
        "system:serviceaccount:karpenter:karpenter"
      ]
      policy_arns = [
        "arn:aws:iam::aws:policy/AdministratorAccess"
      ]
    }
  }
}

# ALB Controller
resource "helm_release" "alb_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.5.0"

  set {
    name  = "clusterName"
    value = var.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "false"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }
}

# External DNS
resource "helm_release" "external_dns" {
  name       = "external-dns"
  repository = "https://charts.bitnami.com/bitnami"
  chart      = "external-dns"
  namespace  = "external-dns"
  create_namespace = true
  version    = "6.18.0"

  set {
    name  = "provider"
    value = "aws"
  }

  set {
    name  = "aws.region"
    value = var.aws_region
  }

  set {
    name  = "txtOwnerId"
    value = var.cluster_name
  }

  set {
    name  = "domainFilter[0]"
    value = "erin.io"
  }

  set {
    name  = "policy"
    value = "sync"
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }