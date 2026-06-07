$REGION = "us-east-1"

# 1. Create IAM role
Write-Host "--- Creating IAM role ---"
aws iam create-role --role-name praan-apprunner-role --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name praan-apprunner-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

Start-Sleep -Seconds 10

# 2. Get role ARN
$ROLE_ARN = (aws iam get-role --role-name praan-apprunner-role | ConvertFrom-Json).Role.Arn
Write-Host "Role ARN: $ROLE_ARN"

# 3. Patch the config file with real role ARN
(Get-Content apprunner_config.json) -replace "ROLE_ARN_PLACEHOLDER", $ROLE_ARN | Set-Content apprunner_config.json

# 4. Create App Runner service
Write-Host "--- Creating App Runner service ---"
$RESULT = aws apprunner create-service --cli-input-json file://apprunner_config.json --region $REGION | ConvertFrom-Json
Write-Host "Service URL: https://$($RESULT.Service.ServiceUrl)"
Write-Host "Status: $($RESULT.Service.Status)"
