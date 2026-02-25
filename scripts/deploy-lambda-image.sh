#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 6 ]]; then
  echo "Usage: $0 <aws-region> <aws-account-id> <ecr-repository> <lambda-function-name> [image-tag] [lambda-role-arn]"
  echo "Example: $0 ap-northeast-2 123456789012 community-be-lambda community-backend-lambda v1.0.0 arn:aws:iam::123456789012:role/lambda-exec-role"
  exit 1
fi

AWS_REGION="$1"
AWS_ACCOUNT_ID="$2"
ECR_REPOSITORY="$3"
LAMBDA_FUNCTION_NAME="$4"
IMAGE_TAG="${5:-$(date +%Y%m%d-%H%M%S)}"
LAMBDA_ROLE_ARN="${6:-${LAMBDA_ROLE_ARN:-}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

echo "[1/5] Ensure ECR repository exists: ${ECR_REPOSITORY}"
if ! aws ecr describe-repositories --region "$AWS_REGION" --repository-names "$ECR_REPOSITORY" >/dev/null 2>&1; then
  aws ecr create-repository --region "$AWS_REGION" --repository-name "$ECR_REPOSITORY" >/dev/null
fi

echo "[2/5] Login to ECR"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null

echo "[3/5] Build and push Lambda image: ${IMAGE_URI}"
docker buildx build \
  --platform linux/amd64 \
  --file "$PROJECT_ROOT/Dockerfile.lambda" \
  --tag "$IMAGE_URI" \
  --push \
  "$PROJECT_ROOT"

echo "[4/5] Create or update Lambda function: ${LAMBDA_FUNCTION_NAME}"
if aws lambda get-function --region "$AWS_REGION" --function-name "$LAMBDA_FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --region "$AWS_REGION" \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --image-uri "$IMAGE_URI" >/dev/null
else
  if [[ -z "$LAMBDA_ROLE_ARN" ]]; then
    echo "Lambda function does not exist and role ARN is not provided."
    echo "Provide the 6th argument or set LAMBDA_ROLE_ARN env."
    exit 1
  fi

  aws lambda create-function \
    --region "$AWS_REGION" \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --package-type Image \
    --code ImageUri="$IMAGE_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --architectures x86_64 \
    --timeout 30 \
    --memory-size 512 >/dev/null
fi

echo "[5/5] Wait until function update completes"
aws lambda wait function-updated --region "$AWS_REGION" --function-name "$LAMBDA_FUNCTION_NAME"

echo "Done"
echo "- Lambda: ${LAMBDA_FUNCTION_NAME}"
echo "- Image:  ${IMAGE_URI}"
