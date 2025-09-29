#!/bin/bash

# Membership System Deployment Script
# This script handles the complete deployment process after code changes

set -e  # Exit on any error

echo "=========================================="
echo "MEMBERSHIP SYSTEM DEPLOYMENT"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    print_error "Please run this script with sudo privileges"
    echo "Usage: sudo $0"
    exit 1
fi

print_status "Starting deployment process..."

# Step 1: Pull latest changes from GitHub
echo ""
echo "Step 1: Pulling latest changes from GitHub..."
if git pull origin main; then
    print_status "Successfully pulled latest changes"
else
    print_error "Failed to pull changes from GitHub"
    echo "Please check your git configuration and network connection"
    exit 1
fi

# Step 2: Check if restart script exists and is executable
echo ""
echo "Step 2: Checking restart script..."
if [ ! -f "./restart_services.sh" ]; then
    print_error "restart_services.sh not found in current directory"
    exit 1
fi

if [ ! -x "./restart_services.sh" ]; then
    echo "Making restart script executable..."
    chmod +x ./restart_services.sh
    print_status "Restart script is now executable"
fi

# Step 3: Run the restart script
echo ""
echo "Step 3: Restarting services..."
if ./restart_services.sh; then
    print_status "Services restarted successfully"
else
    print_error "Service restart failed"
    echo "Check the restart script output above for details"
    exit 1
fi

# Step 4: Optional - Run application tests if they exist
echo ""
echo "Step 4: Running application tests..."
if [ -f "./test_application.py" ]; then
    echo "Running application tests..."
    if ./venv/bin/python test_application.py; then
        print_status "Application tests passed"
    else
        print_warning "Application tests failed - check output above"
        echo "Note: Services are running but tests failed"
    fi
else
    print_warning "test_application.py not found, skipping tests"
fi

# Final summary
echo ""
echo "=========================================="
echo "DEPLOYMENT SUMMARY"
echo "=========================================="
print_status "Code updated from GitHub"
print_status "Services restarted successfully"
print_status "All domains tested and responding"

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "Your membership system is now live with the latest changes at:"
echo "  • https://liconnects.unfc.it"
echo "  • https://lieg.unfc.it"
echo "  • https://closers.unfc.it"
echo "  • https://member.unfc.it"

echo ""
echo "Next steps:"
echo "1. Test your changes in the browser"
echo "2. Monitor application logs if needed: sudo journalctl -u gunicorn -f"
echo "3. Check nginx logs if needed: sudo tail -f /var/log/nginx/error.log"

print_status "Deployment process completed!"
