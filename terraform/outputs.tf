output "server_public_ip" {
  description = "The public IP address of the production server"
  value       = aws_instance.app_server.public_ip
}