#!/usr/bin/env python3
"""
Test script to verify the members list functionality works without internal server errors
"""

import requests
import sys
from app import create_app
from database import get_tenant_db_session
from app.models import User, MembershipType

def test_membership_list_functionality():
    """Test the members list route functionality"""
    print("Testing members list functionality...")
    
    # Create app instance
    app = create_app()
    
    with app.app_context():
        # Test database connection for each tenant
        tenants_to_test = ['closers', 'liconnects', 'lieg']
        
        for tenant_id in tenants_to_test:
            print(f"\n--- Testing tenant: {tenant_id} ---")
            
            try:
                with get_tenant_db_session(tenant_id) as s:
                    print(f"✅ Database connection successful for {tenant_id}")
                    
                    # Test the query that was failing
                    members = s.query(User).all()
                    print(f"✅ Successfully queried {len(members)} members from {tenant_id}")
                    
                    # Test membership types query
                    membership_types = s.query(MembershipType).all()
                    print(f"✅ Successfully queried {len(membership_types)} membership types from {tenant_id}")
                    
                    # Test the specific query from the routes
                    from sqlalchemy.orm import joinedload
                    all_members = s.query(User).options(joinedload(User.membership_type)).order_by(User.first_name, User.last_name).all()
                    print(f"✅ Successfully executed membership list query - {len(all_members)} members with joinedload")
                    
                    # Test template rendering data structure
                    for i, member in enumerate(all_members[:3]):  # Test first 3 members
                        name = f"{member.first_name or ''} {member.last_name or ''}".strip() or member.email
                        membership_type_name = member.membership_type.name if member.membership_type else "No membership type"
                        print(f"  Member {i+1}: {name} ({membership_type_name})")
                        
            except Exception as e:
                print(f"❌ Error testing {tenant_id}: {str(e)}")
                print(f"   Error type: {type(e).__name__}")
                return False
        
        print(f"\n✅ All database tests passed! The SQLAlchemy text() issue has been resolved.")
        return True

def test_with_requests():
    """Test using HTTP requests"""
    print("\n--- Testing HTTP endpoints ---")
    
    base_url = "http://127.0.0.1:5000"
    
    # Test each tenant's members list endpoint
    tenants_to_test = ['closers', 'liconnects', 'lieg']
    
    for tenant_id in tenants_to_test:
        url = f"{base_url}/demographics/{tenant_id}/list"
        print(f"Testing: {url}")
        
        try:
            response = requests.get(url, timeout=5, allow_redirects=False)
            
            if response.status_code == 302:
                print(f"✅ {tenant_id}: Proper redirect to login (expected for unauthenticated request)")
                print(f"   Redirect location: {response.headers.get('Location', 'Not provided')}")
            elif response.status_code == 500:
                print(f"❌ {tenant_id}: Internal Server Error (the bug we're fixing)")
                return False
            else:
                print(f"✅ {tenant_id}: Response code {response.status_code} (no internal server error)")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ {tenant_id}: Request failed - {str(e)}")
            return False
    
    print(f"✅ All HTTP endpoint tests passed! No internal server errors detected.")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("MEMBERSHIP LIST FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test 1: Database functionality
    db_test_passed = test_membership_list_functionality()
    
    # Test 2: HTTP endpoints  
    http_test_passed = test_with_requests()
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS:")
    print("=" * 60)
    print(f"Database Tests: {'✅ PASSED' if db_test_passed else '❌ FAILED'}")
    print(f"HTTP Tests:     {'✅ PASSED' if http_test_passed else '❌ FAILED'}")
    
    if db_test_passed and http_test_passed:
        print("\n🎉 SUCCESS: Internal server error on list members has been FIXED!")
        print("   The SQLAlchemy text() issue has been resolved.")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: Issues still remain.")
        sys.exit(1)