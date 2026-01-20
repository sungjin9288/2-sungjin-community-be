
import bcrypt


def hash_password(password: str) -> str:

    password_bytes = password.encode('utf-8')
    

    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    

    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    

    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:

    try:
        password_bytes = password.encode('utf-8')
        

        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        hash_bytes = password_hash.encode('utf-8')
        
 
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        return False