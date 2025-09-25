#!/bin/bash

# Membership System Restart Script
# This script safely restarts the membership system services

set -e  # Exit on any error

echo "=========================================="
echo "MEMBERSHIP SYSTEM RESTART"
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

print_status "Starting service restart process..."

# Step 1: Stop services in correct order
echo ""
echo "Step 1: Stopping services..."
if systemctl is-active --quiet nginx; then
    echo "Stopping nginx..."
    systemctl stop nginx
    print_status "Nginx stopped"
else
    print_warning "Nginx was not running"
fi

if systemctl is-active --quiet gunicorn; then
    echo "Stopping gunicorn..."
    systemctl stop gunicorn
    print_status "Gunicorn stopped"
else
    print_warning "Gunicorn was not running"
fi

# Step 2: Ensure socket directory exists with correct permissions
echo ""
echo "Step 2: Ensuring socket directory..."
if [ ! -d "/var/www/member/tmp" ]; then
    mkdir -p /var/www/member/tmp
    print_status "Created socket directory"
fi

chown myappuser:myappgroup /var/www/member/tmp
chmod 755 /var/www/member/tmp
print_status "Socket directory permissions set"

# Step 3: Reload systemd daemon (in case service files changed)
echo ""
echo "Step 3: Reloading systemd daemon..."
systemctl daemon-reload
print_status "Systemd daemon reloaded"

# Step 4: Start services in correct order
echo ""
echo "Step 4: Starting services..."

echo "Starting gunicorn..."
systemctl start gunicorn
sleep 3  # Give gunicorn time to start

if systemctl is-active --quiet gunicorn; then
    print_status "Gunicorn started successfully"
else
    print_error "Failed to start gunicorn"
    echo "Checking gunicorn status..."
    systemctl status gunicorn --no-pager
    exit 1
fi

echo "Starting nginx..."
systemctl start nginx

if systemctl is-active --quiet nginx; then
    print_status "Nginx started successfully"
else
    print_error "Failed to start nginx"
    echo "Checking nginx status..."
    systemctl status nginx --no-pager
    exit 1
fi

# Step 5: Test all tenant domains
echo ""
echo "Step 5: Testing tenant domains..."

# Array of domains to test
domains=("liconnects.unfc.it" "lieg.unfc.it" "closers.unfc.it" "member.unfc.it")
all_passed=true

for domain in "${domains[@]}"; do
    echo -n "Testing $domain... "
    status_code=$(curl -s -o /dev/null -w "%{http_code}" https://$domain/ 2>/dev/null)

    if [ "$status_code" = "200" ]; then
        echo -e "${GREEN}✅ $status_code${NC}"
    else
        echo -e "${RED}❌ $status_code${NC}"
        all_passed=false
    fi
done

# Final summary
echo ""
echo "=========================================="
echo "RESTART SUMMARY"
echo "=========================================="

if $all_passed; then
    print_status "All services restarted successfully!"
    print_status "All tenant domains are responding"
    echo ""
    echo "The membership system is ready at:"
    echo "  • https://liconnects.unfc.it"
    echo "  • https://lieg.unfc.it"
    echo "  • https://closers.unfc.it"
    echo "  • https://member.unfc.it"
else
    print_warning "Some domains may not be responding correctly"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check gunicorn logs: sudo journalctl -u gunicorn -n 20"
    echo "2. Check nginx logs: sudo tail -20 /var/log/nginx/error.log"
    echo "3. Verify socket file: ls -la /var/www/member/tmp/"
fi

print_status "Restart process completed!"
