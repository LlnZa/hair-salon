import os
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/barbershop_db')
if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key')
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.yandex.ru')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '465'))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'dovar.m@yandex.ru')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'hewnpqcyawexnqvy')
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'

class Config:
    SECRET_KEY = SECRET_KEY
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки для отправки email
    MAIL_SERVER = MAIL_SERVER
    MAIL_PORT = MAIL_PORT
    MAIL_USE_SSL = False
    MAIL_USERNAME = MAIL_USERNAME
    MAIL_PASSWORD = MAIL_PASSWORD
    MAIL_DEFAULT_SENDER = 'dovar.m@yandex.ru' 