from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class Role(str, Enum):
    admin = "administrador"
    teacher = "docente"
    student = "estudiante"

# --- Modelos de Usuario ---
class UserBase(BaseModel):
    nombre: str

class UserCreate(UserBase):
    rol: Role

class UserInDB(UserBase):
    user_id: str
    rol: Role

class UploadURLRequest(BaseModel):
    content_type: str

# --- Modelos de Materia ---
class Subject(BaseModel):
    subject_id: Optional[str] = None
    nombre_materia: str
    descripcion: str

# --- Modelos de Tarea ---
class TaskBase(BaseModel):
    subject_id: str
    titulo: str
    fecha_entrega: datetime
    fecha_caducidad: datetime

class TaskCreate(TaskBase):
    pass

class TaskInDB(TaskBase):
    task_id: str
    fecha_creacion: datetime = Field(default_factory=datetime.utcnow)

# --- Modelo de Inscripción ---
class Enrollment(BaseModel):
    user_id: str
    subject_id: str

# --- Modelos de Entrega (NUEVO) ---
class SubmissionStatus(str, Enum):
    entregado = "entregado"
    pendiente = "pendiente"
    caducado = "caducado"
    inactivo = "inactivo"

class SubmissionInDB(BaseModel):
    submission_id: str
    task_id: str
    user_id: str
    subject_id: str
    fecha_entrega: datetime = Field(default_factory=datetime.utcnow)
    s3_object_name: str

# --- Modelos para Respuestas de API ---
class StudentTask(TaskInDB):
    status: SubmissionStatus
    submission: Optional[SubmissionInDB] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    rol: Optional[Role] = None

class UserForList(UserInDB):
    pass

class UserSelect(BaseModel):
    user_id: str