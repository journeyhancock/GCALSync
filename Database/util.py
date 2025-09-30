import psycopg2

def start_connection():
    return psycopg2.connect(
        dbname="gcalsync",
        user="gcalsync_user",
        password="user",
        host="localhost",
        port="5432"
    )