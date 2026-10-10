variable "aws_region" {
  description = "The AWS region to deploy in"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "The size of the EC2 instance (t3.medium is good for FastAPI + Postgres)"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "The name of your AWS SSH Key Pair to access the server"
  type        = string
}