variable "region" { default = "ap-northeast-2" }
variable "ssh_cidr" { default = ["0.0.0.0/0"] }
variable "db_name" { default = "chatdb" }
variable "db_user" { default = "django" }
variable "db_password" { default = "django" }
variable "mysql_version" { default = "8.0" }
variable "mysql_instance_class" { default = "db.t3.micro" }
variable "s3_bucket" { description = "S3 bucket name for uploads" }
variable "ami" { description = "EC2 AMI id" }
variable "instance_type" { default = "t3.small" }

