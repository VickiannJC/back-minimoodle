import boto3
from botocore.exceptions import ClientError
from datetime import datetime

# Importaciones de nuestro proyecto
from models.schemas import UserInDB, TaskInDB, Enrollment, SubmissionInDB, SubmissionStatus
from core.config import (
    AWS_REGION, DYNAMODB_TABLE_USERS, DYNAMODB_TABLE_SUBJECTS,
    DYNAMODB_TABLE_TASKS, DYNAMODB_TABLE_ENROLLMENTS, S3_BUCKET_TASKS,
    DYNAMODB_TABLE_SUBMISSIONS # Necesitarás añadir esta tabla en config.py
)

# Inicializar clientes de AWS
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

# --- Funciones de S3 ---
def create_presigned_url(bucket_name: str, object_name: str, expiration=3600, method='put_object'):
    try:
        response = s3_client.generate_presigned_url(method,
                                                    Params={'Bucket': bucket_name, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        print(f"Error al generar URL prefirmada: {e}")
        return None
    return response

def delete_s3_object(bucket_name: str, object_name: str):
    """Elimina un objeto específico de un bucket de S3."""
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_name)
        return True
    except ClientError:
        return False

# --- Funciones de DynamoDB ---

# -- CRUD Genérico --
def get_item(table_name, key): return dynamodb.Table(table_name).get_item(Key=key).get('Item')
def scan_items(table_name): return dynamodb.Table(table_name).scan().get('Items', [])
def put_item(table_name, item): dynamodb.Table(table_name).put_item(Item=item); return item
def delete_item(table_name, key): dynamodb.Table(table_name).delete_item(Key=key); return True

# -- Lógica de Negocio --
def get_task_by_id_from_db(task_id: str):
    item = get_item(DYNAMODB_TABLE_TASKS, {'task_id': task_id})
    if item:
        item['fecha_creacion'] = datetime.fromisoformat(item['fecha_creacion'])
        item['fecha_entrega'] = datetime.fromisoformat(item['fecha_entrega'])
        item['fecha_caducidad'] = datetime.fromisoformat(item['fecha_caducidad'])
    return item

def is_student_enrolled(user_id: str, subject_id: str):
    return get_item(DYNAMODB_TABLE_ENROLLMENTS, {'subject_id': subject_id, 'user_id': user_id}) is not None

def get_student_subjects(user_id: str):
    table = dynamodb.Table(DYNAMODB_TABLE_ENROLLMENTS)
    response = table.query(
        IndexName='user-subject-index', # Necesitarás crear un GSI en esta tabla
        KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
    )
    return response.get('Items', [])

def get_tasks_for_subject(subject_id: str):
    table = dynamodb.Table(DYNAMODB_TABLE_TASKS)
    response = table.query(
        IndexName='subject-tasks-index', # Necesitarás crear un GSI en esta tabla
        KeyConditionExpression=boto3.dynamodb.conditions.Key('subject_id').eq(subject_id)
    )
    return response.get('Items', [])

def get_students_for_subject(subject_id: str):
    """Obtiene todos los user_id de los estudiantes inscritos en una materia."""
    table = dynamodb.Table(DYNAMODB_TABLE_ENROLLMENTS)
    try:
        # La clave de partición de la tabla base es subject_id, por lo que una query es eficiente.
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('subject_id').eq(subject_id)
        )
        return response.get('Items', [])
    except ClientError:
        return []

def get_submission(user_id: str, task_id: str):
    """Obtiene la entrega de un estudiante para una tarea específica."""
    table = dynamodb.Table(DYNAMODB_TABLE_SUBMISSIONS)
    try:
        # Se requiere un Índice Secundario Global (GSI) para esta consulta.
        response = table.query(
            IndexName='user-task-index', # Asegúrate de que este índice exista
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id) & boto3.dynamodb.conditions.Key('task_id').eq(task_id)
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except ClientError:
        return None

def create_submission_db(submission: SubmissionInDB):
    """Guarda un registro de entrega en DynamoDB."""
    table = dynamodb.Table(DYNAMODB_TABLE_SUBMISSIONS)
    try:
        item = submission.dict()
        item['fecha_entrega'] = item['fecha_entrega'].isoformat()
        table.put_item(Item=item)
        return item
    except ClientError:
        return None

def delete_submission_db(submission_id: str):
    """Elimina un registro de entrega de DynamoDB."""
    table = dynamodb.Table(DYNAMODB_TABLE_SUBMISSIONS)
    try:
        table.delete_item(Key={'submission_id': submission_id})
        return True
    except ClientError:
        return False