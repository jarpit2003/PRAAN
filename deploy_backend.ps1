$REGION = "us-east-1"
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_REPO = "praan-backend"
$IMAGE_TAG = "latest"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"

Write-Host "Account ID: $ACCOUNT_ID"
Write-Host "ECR URI: $ECR_URI"

# 1. Create ECR repository
Write-Host "`n--- Creating ECR repository ---"
aws ecr create-repository --repository-name $ECR_REPO --region $REGION 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Repository may already exist, continuing..." }

# 2. Login to ECR
Write-Host "`n--- Logging in to ECR ---"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# 3. Build Docker image
Write-Host "`n--- Building Docker image ---"
Set-Location backend
docker build -t $ECR_REPO .

# 4. Tag and push
Write-Host "`n--- Pushing to ECR ---"
docker tag "${ECR_REPO}:latest" "${ECR_URI}:${IMAGE_TAG}"
docker push "${ECR_URI}:${IMAGE_TAG}"

Write-Host "`n✅ Done! Image pushed to: ${ECR_URI}:${IMAGE_TAG}"
Write-Host "Note this URI - you will need it for App Runner setup."
