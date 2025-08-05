import os
SECRET_KEY = "tu-super-secreto-string-aleatorio-diferente"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
AWS_REGION = "us-east-1"
DYNAMODB_TABLE_USERS = "Minimoodle-Usuarios"
DYNAMODB_TABLE_SUBJECTS = "Minimoodle-Materias"
DYNAMODB_TABLE_TASKS = "Minimoodle-Tareas"
DYNAMODB_TABLE_ENROLLMENTS = "Minimoodle-Inscripciones"
S3_BUCKET_TASKS = "minimoodle-tareas-bucket-nombre-unico-global"