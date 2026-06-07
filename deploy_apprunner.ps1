$REGION = "us-east-1"
$ACCOUNT_ID = "241304350951"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/praan-backend:latest"
$RDS_URL = "postgresql://praan:Praan2024Secure@praan-db.ccr6wmsy02xc.us-east-1.rds.amazonaws.com:5432/praan_db"

# 1. Create IAM role for App Runner to access ECR
Write-Host "--- Creating IAM role for App Runner ---"
$TRUST = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
$TRUST | Out-File -FilePath trust.json -Encoding utf8
aws iam create-role --role-name praan-apprunner-role --assume-role-policy-document file://trust.json 2>$null
aws iam attach-role-policy --role-name praan-apprunner-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
$ROLE_ARN = (aws iam get-role --role-name praan-apprunner-role | ConvertFrom-Json).Role.Arn
Write-Host "Role ARN: $ROLE_ARN"

Start-Sleep -Seconds 10

# 2. Create App Runner service
Write-Host "--- Creating App Runner service ---"
$CONFIG = @"
{
  "ServiceName": "praan-backend",
  "SourceConfiguration": {
    "ImageRepository": {
      "ImageIdentifier": "$ECR_URI",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "DATABASE_URL": "$RDS_URL",
          "AWS_REGION": "us-east-1",
          "BEDROCK_MODEL": "amazon.nova-micro-v1:0",
          "SMTP_HOST": "smtp.gmail.com",
          "SMTP_PORT": "587",
          "SMTP_USER": "shivane5600@gmail.com",
          "SMTP_PASS": "REPLACE_WITH_APP_PASSWORD",
          "BLOOD_BANK_EMAIL": "lloydtv43@gmail.com",
          "FROM_EMAIL": "shivane5600@gmail.com"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AuthenticationConfiguration": {
      "AccessRoleArn": "$ROLE_ARN"
    },
    "AutoDeploymentsEnabled": false
  },
  "InstanceConfiguration": {
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB"
  }
}
"@
$CONFIG | Out-File -FilePath apprunner_config.json -Encoding utf8

$RESULT = aws apprunner create-service --cli-input-json file://apprunner_config.json --region $REGION | ConvertFrom-Json
$SERVICE_URL = $RESULT.Service.ServiceUrl
Write-Host ""
Write-Host "App Runner service created!"
Write-Host "Service URL: https://$SERVICE_URL"
Write-Host "Status: $($RESULT.Service.Status) (will take 2-3 min to deploy)"
