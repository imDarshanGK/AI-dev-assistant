terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 1. Firewall Rules: Only allow Web Traffic and SSH
resource "aws_security_group" "ai_dev_sg" {
  name        = "ai-dev-assistant-sg"
  description = "Allow HTTP, HTTPS, and SSH"

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP Web Traffic"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. The Server (EC2 Instance)
resource "aws_instance" "app_server" {
  ami           = "ami-0c7217cdde317cfec" # Standard Ubuntu 22.04 LTS in us-east-1
  instance_type = var.instance_type
  key_name      = var.key_name

  vpc_security_group_ids = [aws_security_group.ai_dev_sg.id]

  # 3. Startup Script: Install Docker automatically when the server boots
  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y docker.io docker-compose git
              systemctl start docker
              systemctl enable docker
              usermod -aG docker ubuntu
              EOF

  tags = {
    Name = "AIDevAssistant-Production"
  }
}