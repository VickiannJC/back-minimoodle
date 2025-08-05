from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class Role(str, Enum):
    admin = "administrador"
    teacher = "docente"
    student = "estudiante"

class UserBase(BaseModel):
    nombre: str

class UserCreate(UserBase):
    # Ya no se necesita email ni contraseña para crear un usuario
    rol: Role

class UserInDB(UserBase):
    user_id: str
    rol: Role

class UserForList(UserInDB):
    # Modelo para devolver en la lista de usuarios
    pass

class UserSelect(BaseModel):
    user_id: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    rol: Optional[Role] = None

class Subject(BaseModel):
    subject_id: Optional[str] = None
    nombre_materia: str
    descripcion: str

class Task(BaseModel):
    task_id: Optional[str] = None
    subject_id: str
    titulo: str
    fecha_entrega: str

class Enrollment(BaseModel):
    user_id: str
    subject_id: str