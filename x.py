# test_users.py
import sys
sys.path.append('.')
from app.database import SessionLocal
from app.models import User

db = SessionLocal()

# List all users
users = db.query(User).all()
print("=== All Users ===")
for user in users:
    print(f"- {user.email} (ID: {user.id}, OAuth: {user.is_oauth_user}, Provider: {user.oauth_provider})")

db.close()