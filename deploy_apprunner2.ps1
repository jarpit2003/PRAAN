$REGION = "us-east-1"
$ACCOUNT_ID = "241304350951"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/praan-backend:latest"
$RDS_URL = "postgresql://praan:Praan2024Secure@praan-db.ccr6wmsy02xc.us-east-1.rds.amazonaws.com:5432/praan_db"

$ROLE_ARN = (aws iam get-role --role-name praan-apprunner-role | ConvertFrom-Json).Role.Arn
Write-Host "Role ARN: $ROLE_ARN"

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

Write-Host "Config:"
Write-Host $CONFIG

$CONFIG | Out-File -FilePath apprunner_config.json -Encoding utf8
aws apprunner create-service --cli-input-json file://apprunner_config.json --region $REGION
