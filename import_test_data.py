import psycopg2
import sys

def import_test_data():
    # Параметры подключения
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'dbname': 'barbershop_db',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    try:
        # Подключение к PostgreSQL
        print("Подключение к PostgreSQL...")
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Открываем SQL-файл
        print("Чтение SQL-файла...")
        with open('test_data.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Разделяем скрипт на отдельные команды
        # Предполагаем, что каждая команда заканчивается точкой с запятой
        sql_commands = sql_script.split(';')
        
        # Выполняем каждую команду
        print("Выполнение SQL-команд...")
        for command in sql_commands:
            if command.strip():
                try:
                    cursor.execute(command)
                    print(f"Успешно выполнена команда: {command[:50]}...")
                except Exception as e:
                    print(f"Ошибка при выполнении команды: {command[:50]}...")
                    print(f"Ошибка: {e}")
        
        # Фиксируем изменения
        conn.commit()
        print("Данные успешно импортированы!")
        
    except Exception as e:
        print(f"Ошибка при импорте данных: {e}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return False
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    return True

if __name__ == "__main__":
    print("Запуск импорта тестовых данных...")
    result = import_test_data()
    if result:
        print("Импорт успешно завершен")
        sys.exit(0)
    else:
        print("Импорт завершился с ошибками")
        sys.exit(1) 