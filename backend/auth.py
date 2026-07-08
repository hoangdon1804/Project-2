from jose import jwt
import bcrypt

SECRET = "SECRET_KEY"


def hash_password(password):
    # Bcrypt chỉ hỗ trợ tối đa 72 bytes sau khi encode.
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password, hashed):
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))


def create_token(data):

    return jwt.encode(data, SECRET, algorithm="HS256")
