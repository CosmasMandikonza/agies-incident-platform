# Aegis Quick Start Guide

Get Aegis up and running in 10 minutes!

## Prerequisites Checklist

- [ ] AWS Account with appropriate permissions
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] AWS SAM CLI installed (`brew install aws-sam-cli` or [download](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- [ ] Docker Desktop installed and running
- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed

## 🚀 Quick Deployment (Development)

### 1. Clone and Setup (2 minutes)
```bash
# Clone the repository
git clone <your-repo-url>
cd aegis-incident-platform

# Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure Environment (1 minute)
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings (optional)
# The defaults will work for local development
```

### 3. Build Lambda Layers (2 minutes)
```bash
cd infrastructure/layers
chmod +x build-layers.sh
./build-layers.sh
cd ../..
```

### 4. Deploy to AWS (5 minutes)
```bash
# Create S3 bucket for SAM artifacts (one-time setup)
aws s3 mb s3://aegis-sam-artifacts-$(aws sts get-caller-identity --query Account --output text)

# Build and deploy
sam build --template infrastructure/template.yaml
sam deploy --guided
```

When prompted by `sam deploy --guided`:
- Stack Name: `aegis-dev`
- AWS Region: `us-east-1` (or your preferred region)
- Parameter Environment: `dev`
- Parameter LogLevel: `DEBUG`
- Parameter AlarmEmail: `your-email@example.com`
- Confirm changes before deploy: `Y`
- Allow SAM to create IAM roles: `Y`
- Save parameters to samconfig.toml: `Y`

## 🖥️ Local Development Setup

### Start Local Services
```bash
# Start DynamoDB and other services
docker-compose up -d

# Set up local DynamoDB tables
python scripts/setup-local-dynamodb.py

# Start SAM local API
sam local start-api --env-vars tests/local/env.json
```

### Start Frontend Development Server
```bash
cd frontend
npm start
```

Visit http://localhost:3000 to see the Aegis dashboard!

## 📝 Test the Deployment

### 1. Get your API endpoint
```bash
aws cloudformation describe-stacks \
    --stack-name aegis-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text
```

### 2. Create a test incident
```bash
curl -X POST <your-api-url>/incidents \
    -H "Content-Type: application/json" \
    -d '{
        "title": "Test Incident",
        "description": "Testing Aegis deployment",
        "severity": "P2",
        "source": "Manual"
    }'
```

## 🎯 Next Steps

1. **Set up authentication**: Configure Cognito users
2. **Connect monitoring**: Integrate with CloudWatch alarms
3. **Configure notifications**: Add Slack webhook to Secrets Manager
4. **Run tests**: `make test`
5. **Deploy frontend**: See [Frontend Deployment Guide](docs/deployment/frontend.md)

## 🆘 Troubleshooting

### SAM deployment fails
- Ensure Docker is running
- Check AWS credentials: `aws sts get-caller-identity`
- Verify S3 bucket exists and is accessible

### Local API doesn't start
- Check port 3000 is not in use
- Ensure Docker containers are running: `docker ps`
- Check logs: `docker-compose logs`

### DynamoDB setup fails
- Verify DynamoDB Local is running: `curl http://localhost:8000`
- Check Docker logs: `docker logs aegis-dynamodb`

## 📚 Documentation

- [Architecture Overview](docs/architecture/README.md)
- [API Reference](docs/api/README.md)
- [Development Guide](docs/guides/development.md)
- [Production Deployment](docs/deployment/production.md)

## 🤝 Getting Help

- Check the [FAQ](docs/FAQ.md)
- Open an [issue](https://github.com/yourusername/aegis-incident-platform/issues)
- Join our [Slack channel](#aegis-support)

---

**Ready to handle incidents like a pro? Let's go! 🚀**