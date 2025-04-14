from app import app, db
from models import Филиалы

def update_database():
    with app.app_context():
        # Получаем метаданные таблицы
        metadata = db.metadata
        table = metadata.tables['филиалы']
        
        # Проверяем существование столбца id
        if 'id' in table.columns:
            # Переименовываем столбец
            db.engine.execute('ALTER TABLE филиалы RENAME COLUMN id TO филиал_id')
            print('Столбец id успешно переименован в филиал_id')
        else:
            print('Столбец id не найден в таблице филиалы')
        
        # Проверяем существование столбца филиал_id
        if 'филиал_id' in table.columns:
            print('Столбец филиал_id уже существует')
        else:
            print('Столбец филиал_id не найден в таблице филиалы')

if __name__ == '__main__':
    update_database() 