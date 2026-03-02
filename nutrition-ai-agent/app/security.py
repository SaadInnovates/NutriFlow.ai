from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.db.mongodb import get_collection


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
	return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
	return pwd_context.hash(password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
	settings = get_settings()
	expire = datetime.now(timezone.utc) + (
		expires_delta
		if expires_delta
		else timedelta(minutes=settings.jwt_access_token_expire_minutes)
	)
	to_encode = {"sub": subject, "exp": expire}
	return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
	settings = get_settings()
	credentials_exception = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Could not validate credentials",
		headers={"WWW-Authenticate": "Bearer"},
	)

	try:
		payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
		email = payload.get("sub")
		if not email:
			raise credentials_exception
	except JWTError as error:
		raise credentials_exception from error

	users = get_collection("users")
	user = users.find_one({"email": email}, {"_id": 0, "password": 0})
	if not user:
		raise credentials_exception

	return user
