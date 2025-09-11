#!/bin/bash

# Apply Database Schema Fix to All Tenant Databases
# Run this script on the Linode server to fix the missing password_hash column

set -e  # Exit on any error

echo "=========================================="
echo "DATABASE SCHEMA FIX FOR MEMBERSHIP SYSTEM"
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

# Database connection details (adjust these as needed)
DB_HOST="localhost"
DB_USER="sabadmin"
DB_PASSWORD="Bellm0re"

# List of tenant databases to fix
TENANT_DATABASES=(
    "tenant1_db"
    "tenant2_db" 
    "website_db"
    "closers_db"
    "liconnects_db"
    "lieg_db"
)

echo "This script will add the missing password_hash column to user_auth_details table"
echo "for all tenant databases."
echo ""

# Check if PostgreSQL is running
if ! systemctl is-active --quiet postgresql; then
    print_error "PostgreSQL is not running. Please start it first:"
    echo "sudo systemctl start postgresql"
    exit 1
fi

print_status "PostgreSQL is running"

# Apply fix to each tenant database
for db_name in "${TENANT_DATABASES[@]}"; do
    echo ""
    echo "Fixing database: $db_name"
    echo "----------------------------------------"
    
    # Check if database exists
    if psql -h $DB_HOST -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $db_name; then
        print_status "Database $db_name exists"
        
        # Apply the SQL fix
        if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $db_name -f manual_database_fix.sql; then
            print_status "Successfully applied schema fix to $db_name"
        else
            print_error "Failed to apply schema fix to $db_name"
        fi
    else
        print_warning "Database $db_name does not exist, skipping"
    fi
done

echo ""
echo "=========================================="
echo "DATABASE SCHEMA FIX COMPLETED"
echo "=========================================="
print_status "All tenant databases have been processed"

echo ""
echo "Next steps:"
echo "1. Restart the gunicorn application"
echo "2. Test user registration"
echo "3. Verify that the password_hash column error is resolved"

echo ""
print_status "Database schema fix completed!"
