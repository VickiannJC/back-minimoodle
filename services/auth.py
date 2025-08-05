from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List
from models.schemas import TokenData, Role
from core.config import SECRET_KEY, ALGORITHM

# Ya no se necesita passlib. Se mantiene OAuth2PasswordBearer para la estructura de seguridad.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login/select-user")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Esta función no cambia. Sigue decodificando el token para proteger los endpoints."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        rol: str = payload.get("rol")
        if user_id is None or rol is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, rol=Role(rol))
    except (JWTError, ValueError):
        raise credentials_exception
    return token_data

def role_checker(required_roles: List[Role]):
    """Esta función no cambia. Sigue verificando los roles."""
    def check_user_role(current_user: TokenData = Depends(get_current_user)):
        if current_user.rol not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción"
            )
        return current_user
    return check_user_role