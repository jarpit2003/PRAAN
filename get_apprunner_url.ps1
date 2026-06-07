$REGION = "us-east-1"
$SVC = aws apprunner list-services --region $REGION | ConvertFrom-Json
$SVC.ServiceSummaryList | ForEach-Object {
    Write-Host "Name: $($_.ServiceName) | URL: https://$($_.ServiceUrl) | Status: $($_.Status)"
}
