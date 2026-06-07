$REGION = "us-east-1"
$RDS = aws rds describe-db-instances --db-instance-identifier praan-db --region $REGION | ConvertFrom-Json
$RDS_HOST = $RDS.DBInstances[0].Endpoint.Address
Write-Host "RDS Endpoint: $RDS_HOST"
Write-Host "Connection string: postgresql://praan:Praan2024Secure@${RDS_HOST}:5432/postgres"
