#!/bin/bash

set -e  # Exit on any error

echo "🚀 Starting MCP Server deployment..."

# Change to the script directory
cd "$(dirname "$0")"

# Check if AWS CLI is configured
echo "🔍 Checking AWS configuration..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Display current AWS account and region
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
echo "✅ AWS Account: $AWS_ACCOUNT"
echo "✅ AWS Region: $AWS_REGION"

# Check if CDK is installed
echo "🔍 Checking CDK installation..."
if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK not found. Installing..."
    npm install -g aws-cdk
fi

# Check if Docker is running
echo "🔍 Checking Docker..."
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Install dependencies
echo "📦 Installing CDK dependencies..."
npm ci

# Build the project
echo "🔨 Building CDK project..."
npm run build

# Validate CDK stack
echo "🔍 Validating CDK stack..."
if ! npx cdk synth --quiet > /dev/null; then
    echo "❌ CDK stack validation failed."
    exit 1
fi

# Bootstrap CDK (only needed once per account/region)
echo "🏗️  Bootstrapping CDK..."
if ! npx cdk bootstrap --quiet; then
    echo "❌ CDK bootstrap failed."
    exit 1
fi

# Deploy the stack
echo "🚀 Deploying MCP Server stack..."
echo "⏳ This may take 10-15 minutes..."
if npx cdk deploy --require-approval never --outputs-file cdk-outputs.json; then
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "📋 Deployment Summary:"
    if [ -f "cdk-outputs.json" ]; then
        echo "🌐 Application URL: $(cat cdk-outputs.json | jq -r '.McpServerStack.ApplicationUrl // "Not available"')"
        echo "🔗 API URL: $(cat cdk-outputs.json | jq -r '.McpServerStack.ApiUrl // "Not available"')"
        echo "❤️  Health Check: $(cat cdk-outputs.json | jq -r '.McpServerStack.HealthCheckUrl // "Not available"')"
    fi
    echo ""
    echo "🎉 Your MCP Server is now deployed and ready to use!"
else
    echo "❌ Deployment failed. Check the error messages above."
    exit 1
fi