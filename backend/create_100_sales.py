#!/usr/bin/env python3
"""
Script to generate 100 sales user accounts
Tạo 100 tài khoản sales cho hệ thống Territory Design
"""
from database import SessionLocal, engine, Base
from models import User
from sqlalchemy import text
from auth import hash_password 
import random

# Ensure tables exist
Base.metadata.create_all(bind=engine)

# Create database session
db = SessionLocal()

try:
    # Optional: Clear old sales accounts (uncomment if you want to start fresh)
    # old_sales = db.query(User).filter(User.role == 'sales').delete()
    # db.commit()
    # print(f"Deleted {old_sales} old sales accounts")

    # Generate 100 sales accounts
    sales_accounts = []
    for i in range(1, 101):
        username = f"sales{i:03d}"  # sales001, sales002, ..., sales100
        email = f"sales{i:03d}@example.com"
        password = f"Sales{i:03d}!@"  # Password format: Sales001!@, Sales002!@, etc.
        full_name = f"Sales Representative {i}"
        phone = f"0{9}{''.join([str(random.randint(0, 9)) for _ in range(8)])}"  # Random phone
        
        sales_accounts.append({
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name,
            "phone": phone,
            "role": "sales"
        })

    # Create accounts in database
    created_count = 0
    skipped_count = 0
    
    for acc in sales_accounts:
        try:
            # Check if username already exists
            existing = db.query(User).filter(User.username == acc["username"]).first()
            if existing:
                skipped_count += 1
                print(f"⊘ Skipped {acc['username']} (already exists)")
                continue
            
            user = User(
                username=acc["username"],
                email=acc["email"],
                password=hash_password(acc["password"]),
                role=acc["role"],
                full_name=acc["full_name"],
                phone=acc["phone"],
                is_approved=True  # Auto-approve sales for testing
            )
            db.add(user)
            created_count += 1
            
            # Print progress every 10 accounts
            if created_count % 10 == 0:
                print(f"✓ Created {created_count} accounts...")
        
        except Exception as e:
            db.rollback()
            print(f"✗ Error creating {acc['username']}: {str(e)}")
            continue

    db.commit()
    db.close()
    
    print(f"\n{'='*50}")
    print(f"✓ Successfully created {created_count} sales accounts!")
    print(f"⊘ Skipped {skipped_count} duplicate accounts")
    print(f"Total: {created_count + skipped_count} accounts processed")
    print(f"{'='*50}")
    
    print("\nAccount Format:")
    print("  Username: sales001, sales002, ..., sales100")
    print("  Email: sales001@example.com, sales002@example.com, ...")
    print("  Password: Sales001!@, Sales002!@, ..., Sales100!@")
    print("  Status: All auto-approved for testing")
    
    # Optional: Show first 5 and last 5 accounts info
    print("\nSample Accounts (First 5):")
    for acc in sales_accounts[:5]:
        print(f"  {acc['username']} / {acc['password']}")
    
    print("\nSample Accounts (Last 5):")
    for acc in sales_accounts[-5:]:
        print(f"  {acc['username']} / {acc['password']}")

except Exception as e:
    print(f"\n✗ Fatal error: {str(e)}")
    db.rollback()
    db.close()
    raise
