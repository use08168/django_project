output "ec2_public_ip" { value = aws_instance.web.public_ip }
output "rds_endpoint" { value = aws_db_instance.mysql.address }
output "s3_bucket" { value = aws_s3_bucket.uploads.bucket }

