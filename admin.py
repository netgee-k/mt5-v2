# reset_db.py
import sys
import os
sys.path.insert(0, '.')

# Delete any existing database file
db_file = "mt5_trades.db"
if os.path.exists(db_file):
    os.remove(db_file)
    print(f"✅ Deleted old database: {db_file}")

from app.database import engine, Base
from app.models import User, Trade
import hashlib

# Create all tables
Base.metadata.create_all(bind=engine)
print("✅ Created all database tables")

# Create session
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Create admin user (simple SHA256 hash)
password = "admin123"
hash_obj = hashlib.sha256(password.encode())
hex_hash = hash_obj.hexdigest()
hashed_password = f"sha256:{hex_hash}"

admin = User(
    username='admin',
    email='admin@mt5.com',
    hashed_password=hashed_password
)

# Add and commit
db.add(admin)
db.commit()

print("✅ Admin user created:")
print(f"   Username: admin")
print(f"   Password: admin123")
print(f"   Hash: {hashed_password[:50]}...")

# Verify it works
user = db.query(User).filter(User.username == 'admin').first()
print(f"✅ Verified user exists: {user.username}")

db.close()
print("\n🎉 Database reset complete! Ready to run the app.")