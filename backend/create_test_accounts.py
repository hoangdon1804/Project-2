#!/usr/bin/env python3
from database import SessionLocal, engine, Base
from models import User
from sqlalchemy import text
from auth import hash_password 

# Ensure tables exist (creates missing tables)
Base.metadata.create_all(bind=engine)

# Ensure `email` column exists in `users` table for older DBs
with engine.connect() as conn:
    res = conn.execute(text("PRAGMA table_info('users')")).fetchall()
    cols = [row[1] for row in res]
    if 'email' not in cols:
        # Add a nullable email column; existing rows will have NULL
        conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
        conn.commit()


# Create database session
db = SessionLocal()

# Clear old users first
db.query(User).delete()
db.commit()

# Test accounts
accounts = [
    {
        "username": "admin1",
        "email": "admin@example.com",
        "password": "Admin123!",
        "role": "admin",
        "full_name": "Admin User",
        "phone": "0123456789",
        "is_approved": True
    },
    {
        "username": "sales1",
        "email": "sales@example.com",
        "password": "Sales123!",
        "role": "sales",
        "full_name": "Sales User",
        "phone": "0987654321",
        "is_approved": True  # Auto-approve for testing
    },
    {
        "username": "customer1",
        "email": "customer@example.com",
        "password": "Customer123!",
        "role": "customer",
        "full_name": "Customer User",
        "phone": "0912345678",
        "is_approved": True
    }
]

# Create accounts
for acc in accounts:
    user = User(
        username=acc["username"],
        email=acc["email"],
        password=hash_password(acc["password"]),
        role=acc["role"],
        full_name=acc["full_name"],
        phone=acc["phone"],
        is_approved=acc["is_approved"]
    )
    db.add(user)
    print(f"✓ Created {acc['username']} ({acc['role']})")

db.commit()
db.close()

print("\n✓ All test accounts created successfully!")
print("\nTest Credentials:")
print("Admin: admin1 / Admin123!")
print("Sales: sales1 / Sales123!")
print("Customer: customer1 / Customer123!")
