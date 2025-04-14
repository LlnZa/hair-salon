from datetime import datetime
from app import app, db
from models import Филиалы, Сотрудники, Клиенты, Услуги, Записи, Оплата, Расходы, Зарплаты, Отзывы

def recreate_database():
    with app.app_context():
        # Удаляем все таблицы
        db.drop_all()
        print('Все таблицы удалены')
        
        # Создаем все таблицы заново
        db.create_all()
        print('Все таблицы созданы заново')
        
        # Создаем тестовые данные
        main_branch = Филиалы(
            название='Главный филиал',
            адрес='Основной адрес',
            телефон='+7 (999) 123-45-67'
        )
        db.session.add(main_branch)
        db.session.commit()
        print('Создан главный филиал')
        
        # Создаем тестового администратора
        admin = Сотрудники(
            филиал_id=main_branch.филиал_id,
            логин='admin',
            имя='Admin',
            фамилия='Admin',
            должность='Администратор',
            телефон='+7 (999) 123-45-67',
            роль='admin',
            дата_приёма=datetime.now().date()
        )
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print('Создан тестовый администратор')

if __name__ == '__main__':
    recreate_database() 