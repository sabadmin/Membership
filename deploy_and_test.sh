#!/bin/bash

# Membership System Deployment and Testing Script
# Run this script on the Linode server after pushing changes to GitHub

set -e  # Exit on any error

echo "=========================================="
echo "MEMBERSHIP SYSTEM DEPLOYMENT & TESTING"
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

# Check if we're in the right directory
if [ ! -f "app.py" ] && [ ! -f "app/__init__.py" ]; then
    print_error "Not in the correct application directory. Please cd to /var/www/member"
    exit 1
fi

print_status "Starting deployment process..."

# Step 1: Pull latest changes
echo ""
echo "Step 1: Pulling latest changes from GitHub..."
if git pull origin main; then
    print_status "Successfully pulled latest changes"
else
    print_error "Failed to pull changes from GitHub"
    exit 1
fi

# Step 2: Stop application if running
echo ""
echo "Step 2: Stopping application..."
if systemctl is-active --quiet gunicorn; then
    echo "Stopping gunicorn service..."
    sudo systemctl stop gunicorn
    print_status "Gunicorn service stopped"
elif pgrep -f gunicorn > /dev/null; then
    echo "Stopping gunicorn processes..."
    pkill -f gunicorn
    sleep 2
    print_status "Gunicorn processes stopped"
else
    print_warning "No running gunicorn processes found"
fi

# Step 3: Activate virtual environment
echo ""
echo "Step 3: Activating virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    print_status "Virtual environment activated"
else
    print_error "Virtual environment not found at venv/bin/activate"
    exit 1
fi

# Step 4: Install/update dependencies (optional)
echo ""
echo "Step 4: Checking dependencies..."
if [ -f "requirements.txt" ]; then
    echo "Installing/updating Python dependencies..."
    pip install -r requirements.txt --quiet
    print_status "Dependencies updated"
else
    print_warning "No requirements.txt found, skipping dependency installation"
fi

# Step 5: Run database schema fix
echo ""
echo "Step 5: Running database schema fix..."
if python3 fix_database_schema.py; then
    print_status "Database schema fix completed successfully"
else
    print_error "Database schema fix failed"
    exit 1
fi

# Step 6: Run application tests
echo ""
echo "Step 6: Running application tests..."
if python3 test_application.py; then
    print_status "All application tests passed"
else
    print_error "Application tests failed"
    exit 1
fi

# Step 7: Start application
echo ""
echo "Step 7: Starting application..."
if systemctl list-unit-files | grep -q "gunicorn.service"; then
    echo "Starting gunicorn service..."
    sudo systemctl start gunicorn
    sleep 3
    if systemctl is-active --quiet gunicorn; then
        print_status "Gunicorn service started successfully"
    else
        print_error "Failed to start gunicorn service"
        echo "Checking service status..."
        sudo systemctl status gunicorn --no-pager
        exit 1
    fi
else
    print_warning "No gunicorn systemd service found"
    echo "Starting gunicorn manually..."
    nohup gunicorn --bind 127.0.0.1:5000 'app:create_app()' > gunicorn.log 2>&1 &
    sleep 3
    if pgrep -f gunicorn > /dev/null; then
        print_status "Gunicorn started manually"
    else
        print_error "Failed to start gunicorn manually"
        exit 1
    fi
fi

# Step 8: Basic web functionality test
echo ""
echo "Step 8: Testing web functionality..."
sleep 2

# Test if the application is responding
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/ | grep -q "200\|302"; then
    print_status "Web application is responding"
else
    print_warning "Web application may not be responding correctly"
    echo "Checking gunicorn logs..."
    if [ -f "gunicorn.log" ]; then
        tail -10 gunicorn.log
    fi
fi

# Final summary
echo ""
echo "=========================================="
echo "DEPLOYMENT SUMMARY"
echo "=========================================="
print_status "Code updated from GitHub"
print_status "Database schema fixed"
print_status "Application tests passed"
print_status "Application started"

echo ""
echo "Next steps:"
echo "1. Open your browser and test the application"
echo "2. Try registering a new user"
echo "3. Test login functionality"
echo "4. Check admin panel if applicable"

echo ""
echo "If you encounter issues:"
echo "- Check gunicorn logs: journalctl -u gunicorn -f"
echo "- Or check manual logs: tail -f gunicorn.log"
echo "- Review the testing guide: README_TESTING.md"

echo ""
print_status "Deployment completed successfully!"
