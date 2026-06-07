$REGION = "us-east-1"

# 1. Create security group
Write-Host "--- Creating security group ---"
$SG = aws ec2 create-security-group --group-name praan-rds-sg --description "PRAAN RDS" --region $REGION | ConvertFrom-Json
$SG_ID = $SG.GroupId
Write-Host "Security Group ID: $SG_ID"

# 2. Allow inbound on port 5432
Write-Host "--- Opening port 5432 ---"
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 5432 --cidr 0.0.0.0/0 --region $REGION

# 3. Create RDS instance
Write-Host "--- Creating RDS PostgreSQL instance (takes 5-10 min) ---"
aws rds create-db-instance `
  --db-instance-identifier praan-db `
  --db-instance-class db.t3.micro `
  --engine postgres `
  --engine-version 15 `
  --master-username praan `
  --master-user-password Praan2024Secure `
  --allocated-storage 20 `
  --publicly-accessible `
  --no-multi-az `
  --vpc-security-group-ids $SG_ID `
  --region $REGION

Write-Host "--- RDS is being created, waiting for it to become available ---"
aws rds wait db-instance-available --db-instance-identifier praan-db --region $REGION

# 4. Get endpoint
$ENDPOINT = aws rds describe-db-instances --db-instance-identifier praan-db --region $REGION | ConvertFrom-Json
$HOST = $ENDPOINT.DBInstances[0].Endpoint.Address
Write-Host ""
Write-Host "RDS Endpoint: $HOST"
Write-Host "Connection string: postgresql://praan:Praan2024Secure@${HOST}:5432/postgres"
