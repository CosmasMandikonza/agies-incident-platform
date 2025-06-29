#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    local missing_tools=()
    
    # Check for required tools
    command -v aws >/dev/null 2>&1 || missing_tools+=("aws-cli")
    command -v sam >/dev/null 2>&1 || missing_tools+=("sam-cli")
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v npm >/dev/null 2>&1 || missing_tools+=("npm")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo "Please install missing tools and try again."
        exit 1
    fi
    
    # Check Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity >/dev/null 2>&1; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_status "All prerequisites met"
}

# Create S3 buckets for SAM artifacts
create_sam_buckets() {
    print_info "Creating S3 buckets for SAM artifacts..."
    
    local environments=("dev" "staging" "prod")
    local region=$(aws configure get region)
    
    for env in "${environments[@]}"; do
        local bucket_name="aegis-sam-artifacts-${env}-$(aws sts get-caller-identity --query Account --output text)"
        
        if aws s3 ls "s3://${bucket_name}" 2>&1 | grep -q 'NoSuchBucket'; then
            print_info "Creating bucket: ${bucket_name}"
            aws s3 mb "s3://${bucket_name}" --region "${region}"
            
            # Enable versioning
            aws s3api put-bucket-versioning \
                --bucket "${bucket_name}" \
                --versioning-configuration Status=Enabled
            
            # Enable encryption
            aws s3api put-bucket-encryption \
                --bucket "${bucket_name}" \
                --server-side-encryption-configuration '{
                    "Rules": [{
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }]
                }'
            
            print_status "Bucket ${bucket_name} created"
        else
            print_warning "Bucket ${bucket_name} already exists"
        fi
    done
}

# Build Lambda layers
build_layers() {
    print_info "Building Lambda layers..."
    
    cd infrastructure/layers
    chmod +x build-layers.sh
    ./build-layers.sh
    cd ../..
    
    print_status "Lambda layers built successfully"
}

# Set up local development environment
setup_local_env() {
    print_info "Setting up local development environment..."
    
    # Start Docker services
    print_info "Starting Docker services..."
    docker-compose up -d
    
    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10
    
    # Initialize LocalStack
    if [ -f "scripts/localstack/init-aws.sh" ]; then
        chmod +x scripts/localstack/init-aws.sh
        docker exec aegis-localstack /docker-entrypoint-initaws.d/init-aws.sh || true
    fi
    
    # Set up DynamoDB tables
    print_info "Setting up DynamoDB tables..."
    python3 scripts/setup-local-dynamodb.py
    
    print_status "Local environment set up successfully"
}

# Validate SAM template
validate_template() {
    print_info "Validating SAM template..."
    
    sam validate --template infrastructure/template.yaml
    
    if [ $? -eq 0 ]; then
        print_status "SAM template is valid"
    else
        print_error "SAM template validation failed"
        exit 1
    fi
}

# Deploy to development environment
deploy_dev() {
    print_info "Deploying to development environment..."
    
    # Build the application
    sam build --template infrastructure/template.yaml
    
    # Deploy
    sam deploy \
        --config-file samconfig.toml \
        --config-env dev \
        --no-confirm-changeset \
        --no-fail-on-empty-changeset
    
    if [ $? -eq 0 ]; then
        print_status "Development deployment successful"
        
        # Get outputs
        local stack_name="aegis-dev"
        local api_url=$(aws cloudformation describe-stacks \
            --stack-name "${stack_name}" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
            --output text)
        
        print_info "API URL: ${api_url}"
    else
        print_error "Development deployment failed"
        exit 1
    fi
}

# Main menu
show_menu() {
    echo ""
    echo "Aegis Infrastructure Setup"
    echo "========================="
    echo "1. Check prerequisites"
    echo "2. Create S3 buckets"
    echo "3. Build Lambda layers"
    echo "4. Set up local environment"
    echo "5. Validate SAM template"
    echo "6. Deploy to development"
    echo "7. Run all setup steps"
    echo "8. Exit"
    echo ""
}

# Main function
main() {
    while true; do
        show_menu
        read -p "Select an option: " choice
        
        case $choice in
            1)
                check_prerequisites
                ;;
            2)
                create_sam_buckets
                ;;
            3)
                build_layers
                ;;
            4)
                setup_local_env
                ;;
            5)
                validate_template
                ;;
            6)
                deploy_dev
                ;;
            7)
                print_info "Running all setup steps..."
                check_prerequisites
                create_sam_buckets
                build_layers
                setup_local_env
                validate_template
                read -p "Deploy to development? (y/N): " deploy_choice
                if [[ $deploy_choice =~ ^[Yy]$ ]]; then
                    deploy_dev
                fi
                print_status "All setup steps completed!"
                ;;
            8)
                print_info "Exiting..."
                exit 0
                ;;
            *)
                print_error "Invalid option"
                ;;
        esac
    done
}

# Run main function
main