module "eks" {
  source = "../../modules/eks"

  cluster_name    = "erin-dev"
  environment     = "development"
  kubernetes_version = "1.28"
  aws_region      = "us-east-1"

  vpc_cidr = "10.2.0.0/16"

  availability_zones = [
    "us-east-1a",
    "us-east-1b"
  ]

  private_subnets = [
    "10.2.1.0/24",
    "10.2.2.0/24"
  ]

  public_subnets = [
    "10.2.101.0/24",
    "10.2.102.0/24"
  ]