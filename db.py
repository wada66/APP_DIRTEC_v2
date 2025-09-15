from flask import current_app
import psycopg2

def get_db_connection():
    db_url = current_app.config.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError("DATABASE_URL não está configurado")
    return psycopg2.connect(db_url)
