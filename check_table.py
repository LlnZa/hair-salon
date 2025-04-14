import psycopg2

# Таблица для проверки
table_name = "Записи"

# Параметры подключения к PostgreSQL
conn_params = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'barbershop_db',
    'user': 'postgres',
    'password': 'postgres'
}

try:
    # Подключаемся к PostgreSQL
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor()
    
    # Получаем колонки таблицы
    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
    columns = [col[0] for col in cursor.fetchall()]
    print(f"Колонки в таблице '{table_name}': {columns}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Ошибка при работе с PostgreSQL: {e}") 