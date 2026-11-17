module "eks" {
  source = "../../modules/eks"

  cluster_name    = "erin-staging"
  environment     = "staging"
  kubernetes_version = "1.28"
  aws_region      = "us-east-1"

  vpc_cidr = "10.1.0.0/16"

  availability_zones = [
    "us-east-1a",
    "us-east-1b"
  ]

  private_subnets = [
    "10.1.1.0/24",
    "10.1.2.0/24"
  ]

  public_subnets = [
    "10.1.101.0/24",
    "10.1.102.0/24"
  ]