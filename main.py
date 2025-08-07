from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uuid
from datetime import datetime, timedelta
from typing import List

# Importaciones de nuestro proyecto
from models.schemas import *
from services.auth import create_access_token, role_checker, get_current_user
from services.storage import *
from core.config import *

app = FastAPI(title="Minimoodle API - Funcionalidad Completa")

# --- Configuración de CORS ---
origins = [
    "http://frontend-alb-1505177366.us-east-1.elb.amazonaws.com",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- Endpoints de Utilidad ---
@app.get("/", status_code=status.HTTP_200_OK)
def health_check(): return {"status": "ok"}

# --- Endpoints de Autenticación ---
@app.get("/users", response_model=List[UserForList])
def get_user_list(): return scan_items(DYNAMODB_TABLE_USERS)

@app.post("/login/select-user", response_model=Token)
async def login_via_selection(selected_user: UserSelect):
    user_dict = get_item(DYNAMODB_TABLE_USERS, {'user_id': selected_user.user_id})
    if not user_dict: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user = UserInDB(**user_dict)
    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": user.user_id, "rol": user.rol.value}, expires_delta=expires)
    return {"access_token": token, "token_type": "bearer"}

# --- Endpoints de Estudiante ---
@app.get("/student/tasks", response_model=List[StudentTask], dependencies=[Depends(role_checker([Role.student]))])
def get_student_tasks(current_user: TokenData = Depends(get_current_user)):
    student_subjects = get_student_subjects(current_user.user_id)
    all_tasks = []
    for enrollment in student_subjects:
        subject_tasks = get_tasks_for_subject(enrollment['subject_id'])
        for task_data in subject_tasks:
            task = TaskInDB(**get_task_by_id_from_db(task_data['task_id']))
            submission = get_submission(current_user.user_id, task.task_id)
            
            status = SubmissionStatus.pendiente
            now = datetime.utcnow()
            if submission:
                status = SubmissionStatus.entregado
            elif now > task.fecha_caducidad:
                status = SubmissionStatus.inactivo
            elif now > task.fecha_entrega:
                status = SubmissionStatus.caducado

            all_tasks.append(StudentTask(**task.dict(), status=status, submission=submission))
    return all_tasks

@app.post("/tasks/{file_name}/{task_id}/upload-url", 
            dependencies=[Depends(get_current_user)])
def get_upload_url(task_id: str, file_name: str, request_body: UploadURLRequest, current_user: TokenData = Depends(get_current_user)):
    """
    Genera una URL segura para que CUALQUIER usuario autenticado suba un archivo.
    Ahora recibe el content_type desde el frontend.
    """
    
    # 1. Obtener la tarea de la base de datos
    task = get_task_by_id_from_db(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")

    # 2. Construir el nombre del objeto en S3
    object_name = f"entregas/{task['subject_id']}/{task_id}/{current_user.user_id}/{file_name}"
    
    # 3. Pasar el content_type a la función de storage para que la firma sea correcta
    url = create_presigned_url(S3_BUCKET_TASKS, object_name, content_type=request_body.content_type)
    
    if url is None:
        raise HTTPException(status_code=500, detail="No se pudo generar la URL de subida.")
        
    # 4. Registrar la entrega solo si el usuario es un estudiante
    if current_user.rol == Role.student:
        submission = SubmissionInDB(
            submission_id=str(uuid.uuid4()),
            task_id=task_id,
            user_id=current_user.user_id,
            subject_id=task['subject_id'],
            s3_object_name=object_name
        )
        create_submission_db(submission)
    
    return {"upload_url": url}

@app.delete("/student/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(role_checker([Role.student]))])
def delete_submission(submission_id: str, current_user: TokenData = Depends(get_current_user)):
    """Permite a un estudiante eliminar su propia entrega."""
    submission = get_item(DYNAMODB_TABLE_SUBMISSIONS, {'submission_id': submission_id})
    if not submission or submission['user_id'] != current_user.user_id:
        raise HTTPException(status_code=404, detail="Entrega no encontrada o no tienes permiso.")
    
    task = get_task_by_id_from_db(submission['task_id'])
    if datetime.utcnow() > task['fecha_caducidad']:
        raise HTTPException(status_code=403, detail="No se puede eliminar una entrega después de la fecha de caducidad.")

    delete_s3_object(S3_BUCKET_TASKS, submission['s3_object_name'])
    delete_submission_db(submission_id)
    return

@app.post("/student/enroll", status_code=status.HTTP_201_CREATED, dependencies=[Depends(role_checker([Role.student]))])
def student_enroll_in_subject(subject: Subject, current_user: TokenData = Depends(get_current_user)):
    """Permite a un estudiante inscribirse en una materia."""
    enrollment_data = {"user_id": current_user.user_id, "subject_id": subject.subject_id}
    if is_student_enrolled(**enrollment_data):
        raise HTTPException(status_code=409, detail="Ya estás inscrito en esta materia.")
    put_item(DYNAMODB_TABLE_ENROLLMENTS, enrollment_data)
    return {"message": "Inscripción exitosa."}

@app.get("/student/subjects", response_model=List[Subject], dependencies=[Depends(role_checker([Role.student]))])
def get_enrolled_subjects(current_user: TokenData = Depends(get_current_user)):
    """Devuelve las materias en las que un estudiante está inscrito."""
    enrollments = get_student_subjects(current_user.user_id)
    subjects = [get_item(DYNAMODB_TABLE_SUBJECTS, {'subject_id': en['subject_id']}) for en in enrollments]
    return [s for s in subjects if s] # Filtra por si alguna materia fue eliminada

@app.get("/student/tasks", response_model=List[StudentTask], dependencies=[Depends(role_checker([Role.student]))])
def get_student_tasks(current_user: TokenData = Depends(get_current_user)):
    """Devuelve todas las tareas de un estudiante, con su estado actual."""
    student_subjects = get_student_subjects(current_user.user_id)
    all_tasks = []
    for enrollment in student_subjects:
        subject_tasks = get_tasks_for_subject(enrollment['subject_id'])
        for task_data in subject_tasks:
            task = TaskInDB(**get_task_by_id_from_db(task_data['task_id']))
            submission = get_submission(current_user.user_id, task.task_id)
            
            status = SubmissionStatus.pendiente
            now = datetime.utcnow()
            if submission:
                status = SubmissionStatus.entregado
            elif now > task.fecha_caducidad:
                status = SubmissionStatus.inactivo
            elif now > task.fecha_entrega:
                status = SubmissionStatus.caducado

            all_tasks.append(StudentTask(**task.dict(), status=status, submission=submission))
    return all_tasks



# --- Endpoints de Docente y Administrador ---
@app.post("/tasks", response_model=TaskInDB, status_code=201, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def create_task(task: TaskCreate):
    if task.fecha_caducidad <= task.fecha_entrega:
        raise HTTPException(status_code=400, detail="La fecha de caducidad debe ser posterior a la fecha de entrega.")
    new_task = TaskInDB(task_id=str(uuid.uuid4()), **task.dict())
    # Convertir datetimes a strings para DynamoDB
    task_dict = new_task.dict()
    task_dict['fecha_creacion'] = new_task.fecha_creacion.isoformat()
    task_dict['fecha_entrega'] = new_task.fecha_entrega.isoformat()
    task_dict['fecha_caducidad'] = new_task.fecha_caducidad.isoformat()
    created_task = put_item(DYNAMODB_TABLE_TASKS, task_dict)
    if not created_task: raise HTTPException(status_code=500, detail="No se pudo crear la tarea.")
    return new_task

@app.post("/enrollments", status_code=status.HTTP_201_CREATED, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def enroll_student(enrollment: Enrollment):
    """Permite a un admin/docente inscribir a un estudiante en una materia."""
    if is_student_enrolled(enrollment.user_id, enrollment.subject_id):
        raise HTTPException(status_code=409, detail="El estudiante ya está inscrito en esta materia.")
    put_item(DYNAMODB_TABLE_ENROLLMENTS, enrollment.dict())
    return {"message": "Estudiante inscrito con éxito."}

@app.get("/subjects/{subject_id}/students", response_model=List[UserInDB], dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def get_subject_students(subject_id: str):
    """Devuelve los estudiantes inscritos en una materia."""
    enrollments = get_students_for_subject(subject_id)
    users = [get_item(DYNAMODB_TABLE_USERS, {'user_id': en['user_id']}) for en in enrollments]
    return [u for u in users if u] # Filtra por si algún usuario fue eliminado


# --- Endpoints Exclusivos de Administrador (CRUD completo) ---
@app.post("/admin/users", response_model=UserInDB, status_code=201, dependencies=[Depends(role_checker([Role.admin]))])
def admin_create_user(user: UserCreate):
    user_id = str(uuid.uuid4())
    user_in_db = UserInDB(user_id=user_id, **user.dict())
    return put_item(DYNAMODB_TABLE_USERS, user_in_db.dict())

@app.delete("/admin/users/{user_id}", status_code=204, dependencies=[Depends(role_checker([Role.admin]))])
def admin_delete_user(user_id: str):
    delete_item(DYNAMODB_TABLE_USERS, {'user_id': user_id})
    return

@app.post("/admin/subjects", response_model=Subject, status_code=201, dependencies=[Depends(role_checker([Role.admin]))])
def admin_create_subject(subject: Subject):
    subject.subject_id = str(uuid.uuid4())
    return put_item(DYNAMODB_TABLE_SUBJECTS, subject.dict())

@app.get("/admin/subjects", response_model=List[Subject], dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def admin_get_all_subjects():
    return scan_items(DYNAMODB_TABLE_SUBJECTS)

@app.get("/admin/subjects/{subject_id}", response_model=Subject, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def admin_get_subject(subject_id: str):
    subject = get_item(DYNAMODB_TABLE_SUBJECTS, {'subject_id': subject_id})
    if not subject: raise HTTPException(status_code=404, detail="Materia no encontrada")
    return subject

@app.put("/admin/subjects/{subject_id}", response_model=Subject, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def admin_update_subject(subject_id: str, subject: Subject):
    subject.subject_id = subject_id # Asegurar que el ID sea el correcto
    return put_item(DYNAMODB_TABLE_SUBJECTS, subject.dict())

@app.delete("/admin/subjects/{subject_id}", status_code=204, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def admin_delete_subject(subject_id: str):
    delete_item(DYNAMODB_TABLE_SUBJECTS, {'subject_id': subject_id})
    return

@app.delete("/admin/tasks/{task_id}", status_code=204, dependencies=[Depends(role_checker([Role.admin, Role.teacher]))])
def admin_delete_task(task_id: str):
    # En una app real, también deberías eliminar las entregas asociadas
    delete_item(DYNAMODB_TABLE_TASKS, {'task_id': task_id})
    return

# --- Punto de entrada para Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
