# test_update.py
import sys
sys.path.append('.')

from app.database import get_db
from app.models import User

# Get database session
db_gen = get_db()
try:
    db = next(db_gen)
    
    # Find your user
    user = db.query(User).filter(User.email == 'networksandcircuits@gmail.com').first()
    
    if user:
        print(f"Before update:")
        print(f"  Server: {user.mt5_server}")
        print(f"  Login: {user.mt5_login}")
        
        # Update directly
        user.mt5_server = "JustMarkets-Live"
        user.mt5_login = 2050505598
        user.mt5_password = "test123"  # Your actual password
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"\nAfter update:")
        print(f"  Server: {user.mt5_server}")
        print(f"  Login: {user.mt5_login}")
        print(f"  Has password: {bool(user.mt5_password)}")
    else:
        print("User not found!")
        
finally:
    try:
        db_gen.close()
    except:
        pass