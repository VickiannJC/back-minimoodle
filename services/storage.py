import boto3
from botocore.exceptions import ClientError
from models.schemas import UserInDB # Importar el modelo
from core.config import (
    AWS_REGION, DYNAMODB_TABLE_USERS, DYNAMODB_TABLE_SUBJECTS,
    DYNAMODB_TABLE_ENROLLMENTS, S3_BUCKET_TASKS
)

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3_client = boto3.client('s3', region_name=AWS_REGION)

def create_presigned_url(bucket_name: str, object_name: str, expiration=3600):
    try:
        response = s3_client.generate_presigned_url('put_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        print(f"Error al generar URL prefirmada: {e}")
        return None
    return response

def get_all_users_from_db():
    """Obtiene todos los usuarios de DynamoDB para la lista desplegable."""
    table = dynamodb.Table(DYNAMODB_TABLE_USERS)
    try:
        response = table.scan() # Scan es aceptable para una cantidad moderada de usuarios
        return response.get('Items', [])
    except ClientError as e:
        print(f"Error al obtener todos los usuarios: {e}")
        return []

def get_user_by_id_from_db(user_id: str):
    """Obtiene un usuario específico por su ID."""
    table = dynamodb.Table(DYNAMODB_TABLE_USERS)
    try:
        response = table.get_item(Key={'user_id': user_id})
        return response.get('Item')
    except ClientError as e:
        print(f"Error al obtener usuario por ID: {e}")
        return None

def create_db_user(user: UserInDB):
    """Crea un usuario en DynamoDB sin contraseña."""
    table = dynamodb.Table(DYNAMODB_TABLE_USERS)
    try:
        # El modelo UserInDB ya no tiene 'hashed_password'
        table.put_item(Item=user.dict())
        return user
    except ClientError as e:
        print(f"Error al crear usuario: {e}")
        return None
