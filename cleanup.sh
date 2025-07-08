#!/bin/bash

set -e  # Exit on any error

echo "🧹 Cleaning up MCP Server resources..."

# Change to the script directory
cd "$(dirname "$0")"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Display current AWS account
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "⚠️  This will destroy resources in AWS Account: $AWS_ACCOUNT"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled."
    exit 1
fi

# Destroy the stack
echo "🗑️  Destroying CDK stack..."
if npx cdk destroy --force; then
    echo "✅ Cleanup completed successfully!"
    echo "📋 All MCP Server resources have been removed."
else
    echo "❌ Cleanup failed. Check the error messages above."
    exit 1
fi