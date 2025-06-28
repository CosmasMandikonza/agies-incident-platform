#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -d "src" ]; then
    print_error "This script must be run from the aegis-incident-platform root directory"
    exit 1
fi

print_status "Initializing Aegis Incident Platform repository..."

# Initialize git repository
if [ ! -d ".git" ]; then
    print_status "Initializing git repository..."
    git init
    git branch -M main
else
    print_status "Git repository already initialized"
fi

# Create feature branch structure
print_status "Setting up branch structure..."
git checkout -b develop || git checkout develop
git checkout main

# Set up git flow
print_status "Configuring git flow..."
cat > .gitflow <<EOF
[gitflow "branch"]
    master = main
    develop = develop
[gitflow "prefix"]
    feature = feature/
    release = release/
    hotfix = hotfix/
    support = support/
    versiontag = v
EOF

# Configure git
print_status "Configuring git settings..."
git config core.autocrlf input
git config core.ignorecase false
git config pull.rebase true

# Create initial commit
if [ -z "$(git log --oneline -1 2>/dev/null || true)" ]; then
    print_status "Creating initial commit..."
    git add .
    git commit -m "feat: initial commit - Aegis incident management platform

- Complete project structure
- CI/CD workflows for GitHub Actions
- AWS SAM infrastructure templates
- Frontend React application setup
- Comprehensive documentation
- Testing framework configuration"
fi

# Set up GitHub CLI if available
if command -v gh &> /dev/null; then
    print_status "GitHub CLI detected. Creating repository..."
    
    # Check if already logged in
    if ! gh auth status &> /dev/null; then
        print_warning "Please login to GitHub CLI first:"
        gh auth login
    fi
    
    # Create repository
    read -p "Enter GitHub repository name (default: aegis-incident-platform): " REPO_NAME
    REPO_NAME=${REPO_NAME:-aegis-incident-platform}
    
    read -p "Make repository private? (y/N): " PRIVATE_REPO
    VISIBILITY="public"
    if [[ $PRIVATE_REPO =~ ^[Yy]$ ]]; then
        VISIBILITY="private"
    fi
    
    if gh repo create "$REPO_NAME" --$VISIBILITY --description "Event-driven incident management platform for AWS Lambda Hackathon" --source=. --remote=origin --push; then
        print_status "Repository created successfully!"
    else
        print_warning "Repository creation failed. You may need to create it manually."
    fi
else
    print_warning "GitHub CLI not found. Please install it for automatic repository creation."
    print_status "To install: https://cli.github.com/"
fi

# Set up branch protection rules
print_status "Setting up branch protection rules..."
cat > .github/branch-protection.json <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "lint-python",
      "lint-frontend", 
      "test-python",
      "test-frontend",
      "security-scan",
      "validate-cloudformation"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

# Create GitHub issue templates
print_status "Creating issue templates..."
mkdir -p .github/ISSUE_TEMPLATE

cat > .github/ISSUE_TEMPLATE/bug_report.md <<EOF
---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
 - OS: [e.g. Ubuntu 22.04]
 - Browser [e.g. chrome, safari]
 - Version [e.g. 22]

**Additional context**
Add any other context about the problem here.
EOF

cat > .github/ISSUE_TEMPLATE/feature_request.md <<EOF
---
name: Feature request
about: Suggest an idea for this project
title: '[FEATURE] '
labels: enhancement
assignees: ''
---

**Is your feature request related to a problem? Please describe.**
A clear and concise description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context or screenshots about the feature request here.
EOF

# Create pull request template
cat > .github/pull_request_template.md <<EOF
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
- [ ] Unit tests pass locally
- [ ] Integration tests pass locally
- [ ] Manual testing completed
- [ ] Added new tests for new functionality

## Checklist
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] Any dependent changes have been merged and published

## Screenshots (if applicable)
Add screenshots to help explain your changes.

## Additional Notes
Add any additional notes or context here.
EOF

# Create CODEOWNERS file
cat > .github/CODEOWNERS <<EOF
# Default code owners for the entire repository
* @yourusername

# Infrastructure code owners
/infrastructure/ @yourusername
/infrastructure/template.yaml @yourusername

# Lambda functions
/src/ @yourusername

# Frontend application
/frontend/ @yourusername

# Documentation
/docs/ @yourusername
README.md @yourusername

# CI/CD
/.github/ @yourusername
EOF

# Create initial documentation structure
print_status "Creating documentation structure..."
mkdir -p docs/{architecture,api,deployment,guides}

cat > docs/architecture/README.md <<EOF
# Aegis Architecture Documentation

## Overview
This directory contains the architectural documentation for the Aegis incident management platform.

## Contents
- [System Architecture](system-architecture.md)
- [Data Flow](data-flow.md)
- [Security Architecture](security.md)
- [Scalability Patterns](scalability.md)
- [Resilience Patterns](resilience.md)
EOF

# Set up pre-commit hooks
print_status "Installing pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit install
    pre-commit install --hook-type commit-msg
    print_status "Pre-commit hooks installed successfully"
else
    print_warning "pre-commit not found. Install it with: pip install pre-commit"
fi

# Create secrets baseline for detect-secrets
print_status "Creating secrets baseline..."
if command -v detect-secrets &> /dev/null; then
    detect-secrets scan > .secrets.baseline
else
    print_warning "detect-secrets not found. Install it with: pip install detect-secrets"
fi

# Final setup steps
print_status "Repository initialization complete!"
echo ""
print_status "Next steps:"
echo "  1. Update .env with your configuration"
echo "  2. Configure AWS credentials"
echo "  3. Set up GitHub secrets for CI/CD"
echo "  4. Run 'make install' to install dependencies"
echo "  5. Run 'make test' to verify setup"
echo ""
print_status "Happy coding! 🚀"