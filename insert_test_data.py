from app import app, db
from models import Филиалы, Услуги, Клиенты, Сотрудники, Оплата, Расходы, Записи, Зарплаты
from datetime import datetime, timedelta
from decimal import Decimal
import random

def add_services():
    """Добавление услуг"""
    services_data = [
        {'название': 'Стрижка мужская', 'цена': 1000, 'описание': 'Базовая мужская стрижка', 'категория': 'М'},
        {'название': 'Стрижка женская', 'цена': 1500, 'описание': 'Базовая женская стрижка', 'категория': 'Ж'},
        {'название': 'Окрашивание', 'цена': 3000, 'описание': 'Окрашивание волос', 'категория': 'Ж'},
        {'название': 'Укладка', 'цена': 800, 'описание': 'Укладка волос', 'категория': 'Ж'},
        {'название': 'Маникюр', 'цена': 1200, 'описание': 'Маникюр с покрытием', 'категория': 'Ж'},
        {'название': 'Педикюр', 'цена': 1500, 'описание': 'Педикюр с покрытием', 'категория': 'Ж'},
        {'название': 'Бритье бороды', 'цена': 700, 'описание': 'Королевское бритье', 'категория': 'М'},
        {'название': 'Массаж головы', 'цена': 500, 'описание': 'Расслабляющий массаж', 'категория': 'УН'},
    ]
    
    for service_data in services_data:
        service = Услуги(
            название_услуги=service_data['название'],
            описание=service_data['описание'],
            базовая_цена=service_data['цена'],
            категория_пола=service_data['категория']
        )
        db.session.add(service)
    
    db.session.commit()
    print(f"Добавлено {len(services_data)} услуг")

def add_clients():
    """Добавление клиентов"""
    clients_data = [
        {'имя': 'Иван', 'фамилия': 'Иванов', 'телефон': '+7(123)456-78-90'},
        {'имя': 'Мария', 'фамилия': 'Петрова', 'телефон': '+7(123)456-78-91'},
        {'имя': 'Алексей', 'фамилия': 'Сидоров', 'телефон': '+7(123)456-78-92'},
        {'имя': 'Екатерина', 'фамилия': 'Смирнова', 'телефон': '+7(123)456-78-93'},
        {'имя': 'Дмитрий', 'фамилия': 'Козлов', 'телефон': '+7(123)456-78-94'},
    ]
    
    for i, client_data in enumerate(clients_data):
        client = Клиенты(
            логин=f'client{i+1}',
            email=f'client{i+1}@example.com',
            телефон=client_data['телефон'],
            имя=client_data['имя'],
            фамилия=client_data['фамилия'],
            отчество='',
            пол='М' if i % 2 == 0 else 'Ж',
            дата_рождения=datetime.now() - timedelta(days=365*30 + i*100),
            дата_регистрации=datetime.now() - timedelta(days=30)
        )
        client.set_password(f'client{i+1}')
        db.session.add(client)
    
    db.session.commit()
    print(f"Добавлено {len(clients_data)} клиентов")

def add_employees():
    """Добавление сотрудников"""
    branch = Филиалы.query.first()
    
    employees_data = [
        {'имя': 'Андрей', 'фамилия': 'Мастеров', 'должность': 'Парикмахер', 'роль': 'employee'},
        {'имя': 'Ольга', 'фамилия': 'Стилистова', 'должность': 'Стилист', 'роль': 'employee'},
        {'имя': 'Наталья', 'фамилия': 'Маникюрова', 'должность': 'Мастер маникюра', 'роль': 'employee'},
    ]
    
    for i, emp_data in enumerate(employees_data):
        employee = Сотрудники(
            логин=f'employee{i+1}',
            имя=emp_data['имя'],
            фамилия=emp_data['фамилия'],
            должность=emp_data['должность'],
            роль=emp_data['роль'],
            телефон=f'+7(987)654-32-{i+10}',
            дата_приёма=datetime.now() - timedelta(days=i*30),
            филиал_id=branch.филиал_id
        )
        employee.set_password(f'employee{i+1}')
        db.session.add(employee)
    
    db.session.commit()
    print(f"Добавлено {len(employees_data)} сотрудников")

def add_appointments_and_payments():
    """Добавление записей и оплат"""
    clients = Клиенты.query.all()
    employees = Сотрудники.query.filter_by(роль='employee').all()
    services = Услуги.query.all()
    branch = Филиалы.query.first()
    
    # Генерируем записи и оплаты за последние 6 месяцев
    now = datetime.now()
    for month in range(6):
        # Для каждого месяца создаем несколько записей
        month_date = now - timedelta(days=month*30)
        for i in range(10):  # 10 записей в месяц
            # Выбираем случайных клиента, сотрудника и услугу
            client = random.choice(clients)
            employee = random.choice(employees)
            service = random.choice(services)
            
            # Создаем запись
            appointment_date = month_date - timedelta(days=random.randint(1, 28))
            appointment = Записи(
                клиент_id=client.клиент_id,
                сотрудник_id=employee.сотрудник_id,
                филиал_id=branch.филиал_id,
                услуга_id=service.услуга_id,
                дата_визита=appointment_date,
                статус='completed',
                примечание=f'Тестовая запись {i+1} за {month_date.strftime("%B %Y")}'
            )
            db.session.add(appointment)
            db.session.flush()  # Чтобы получить appointment.запись_id
            
            # Создаем оплату для этой записи
            payment = Оплата(
                запись_id=appointment.запись_id,
                сумма=service.базовая_цена,
                дата_оплаты=appointment_date,
                способ_оплаты='card' if random.random() > 0.5 else 'cash',
                статус_оплаты='completed'
            )
            db.session.add(payment)
    
    db.session.commit()
    print(f"Добавлено 60 записей и оплат")

def add_expenses():
    """Добавление расходов"""
    branch = Филиалы.query.first()
    
    expense_types = ['Материалы', 'Коммунальные', 'Аренда', 'Реклама', 'Прочее']
    now = datetime.now()
    
    # Создаем расходы за последние 6 месяцев
    for month in range(6):
        month_date = now - timedelta(days=month*30)
        for i in range(5):  # 5 расходов в месяц
            expense_type = random.choice(expense_types)
            
            # Сумма расхода зависит от типа
            amount = random.randint(1000, 5000)
            if expense_type == 'Аренда':
                amount = random.randint(15000, 20000)
            elif expense_type == 'Коммунальные':
                amount = random.randint(3000, 7000)
            
            expense = Расходы(
                тип=expense_type,
                сумма=amount,
                дата=month_date - timedelta(days=random.randint(1, 28)),
                описание=f'{expense_type} за {month_date.strftime("%B %Y")}',
                филиал_id=branch.филиал_id
            )
            db.session.add(expense)
    
    db.session.commit()
    print(f"Добавлено 30 расходов")

def add_salaries():
    """Добавление зарплат"""
    employees = Сотрудники.query.filter_by(роль='employee').all()
    now = datetime.now()
    
    # Создаем зарплаты за последние 6 месяцев
    for month in range(6):
        month_date = now.replace(day=1) - timedelta(days=month*30)
        month_end = (month_date.replace(day=28) if month_date.month != 2 else 
                    month_date.replace(day=29 if month_date.year % 4 == 0 else 28))
        
        for employee in employees:
            base_salary = random.randint(30000, 50000)
            commission = random.randint(3, 10)
            
            salary = Зарплаты(
                сотрудник_id=employee.сотрудник_id,
                базовая_ставка=base_salary,
                процент_от_выручки=commission,
                дата_начала=month_date,
                дата_окончания=month_end
            )
            db.session.add(salary)
    
    db.session.commit()
    print(f"Добавлено {len(employees) * 6} записей о зарплатах")

def insert_test_data():
    with app.app_context():
        # Проверяем, есть ли уже данные
        if Услуги.query.count() > 0:
            print("В базе уже есть услуги. Пропускаем добавление тестовых данных.")
            return
        
        # Добавляем тестовые данные
        add_services()
        add_clients()
        add_employees()
        add_appointments_and_payments()
        add_expenses()
        add_salaries()
        
        print("Тестовые данные успешно добавлены!")

if __name__ == "__main__":
    insert_test_data() 