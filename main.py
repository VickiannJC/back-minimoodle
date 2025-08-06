from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uuid
from datetime import timedelta
from typing import List

from models.schemas import (
    UserCreate, Token, Subject, Enrollment, UserInDB, Role, TokenData,
    UserForList, UserSelect
)
from services.auth import create_access_token, role_checker, get_current_user
from services.storage import (
    get_all_users_from_db, get_user_by_id_from_db, create_db_user,
    create_presigned_url
)
from core.config import ACCESS_TOKEN_EXPIRE_MINUTES, S3_BUCKET_TASKS

app = FastAPI(title="Minimoodle API - Modo Selección de Usuario")


# ==============================================================================
# CONFIGURACIÓN DE CORS ESPECÍFICA
# ==============================================================================
# Define aquí los orígenes permitidos. Usa el DNS de tu Load Balancer del frontend.
origins = [
    "backend-alb-1881385286.us-east-1.elb.amazonaws.com",
    # Si pruebas localmente, puedes añadir la dirección de Vite:
    # "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # <-- Usamos la lista de orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
#  ENDPOINT DE HEALTH CHECK PARA EL LOAD BALANCER
# ==============================================================================
@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """
    Endpoint simple para que el Load Balancer verifique el estado de la aplicación.
    """
    return {"status": "ok"}


# --- Endpoints Públicos (Selección de Usuario) ---

@app.get("/users", response_model=List[UserForList])
def get_user_list():
    """Devuelve una lista de todos los usuarios para el menú desplegable."""
    users = get_all_users_from_db()
    return users

@app.post("/login/select-user", response_model=Token)
async def login_via_selection(selected_user: UserSelect):
    """
    "Inicia sesión" con un usuario seleccionado y devuelve un token de acceso.
    """
    user_dict = get_user_by_id_from_db(selected_user.user_id)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    
    user = UserInDB(**user_dict)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_id, "rol": user.rol.value},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# --- Endpoints de Administrador ---

@app.post("/admin/create-user", response_model=UserInDB, status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(role_checker([Role.admin]))])
def create_user(user: UserCreate):
    """Crea un nuevo usuario sin contraseña."""
    user_id = str(uuid.uuid4())
    
    user_in_db = UserInDB(
        user_id=user_id,
        nombre=user.nombre,
        rol=user.rol
    )
    created_user = create_db_user(user_in_db)
    if not created_user:
        raise HTTPException(status_code=500, detail="No se pudo crear el usuario.")
    return created_user


# --- Punto de entrada para Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

