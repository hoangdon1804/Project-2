from passlib.context import CryptContext
from jose import jwt

SECRET = "SECRET_KEY"

pwd_context = CryptContext(schemes=["bcrypt"])


def hash_password(password):
    # Bcrypt chỉ hỗ trợ tối đa 72 bytes
    password = password[:72]
    return pwd_context.hash(password)


def verify_password(password, hashed):
    # Truncate password khi verify để match với hash đã lưu
    password = password[:72]
    return pwd_context.verify(password, hashed)


def create_token(data):

    return jwt.encode(data, SECRET, algorithm="HS256")