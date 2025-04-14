import psycopg2

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
    
    # Получаем список таблиц
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [table[0] for table in cursor.fetchall()]
    print(f"Таблицы в базе данных: {tables}")
    
    # Проверим структуру таблиц
    for table_name in tables:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
        columns = [col[0] for col in cursor.fetchall()]
        print(f"Колонки в таблице '{table_name}': {columns}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Ошибка при работе с PostgreSQL: {e}") 