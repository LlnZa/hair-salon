from app import app, db
from models import Филиалы, Услуги, Клиенты, Сотрудники, Оплата, Расходы, Записи, Зарплаты

with app.app_context():
    print("\nПроверка данных в базе данных PostgreSQL:")
    
    # Проверяем филиалы
    branches = Филиалы.query.all()
    print(f"Филиалы: {len(branches)}")
    if branches:
        for branch in branches[:3]:  # Показываем первые 3 для примера
            print(f"  - {branch.название}")
    
    # Проверяем услуги
    services = Услуги.query.all()
    print(f"Услуги: {len(services)}")
    if services:
        for service in services[:3]:
            print(f"  - {service.название_услуги} ({service.базовая_цена})")
    
    # Проверяем сотрудников
    employees = Сотрудники.query.all()
    print(f"Сотрудники: {len(employees)}")
    if employees:
        for employee in employees[:3]:
            print(f"  - {employee.имя} {employee.фамилия} ({employee.роль})")
    
    # Проверяем клиентов
    clients = Клиенты.query.all()
    print(f"Клиенты: {len(clients)}")
    if clients:
        for client in clients[:3]:
            print(f"  - {client.имя} {client.фамилия}")
    
    # Проверяем записи
    appointments = Записи.query.all()
    print(f"Записи: {len(appointments)}")
    if appointments:
        for appointment in appointments[:3]:
            print(f"  - Дата: {appointment.дата_визита}, Услуга: {appointment.услуга.название_услуги if appointment.услуга else 'Н/Д'}")
    
    # Проверяем оплаты
    payments = Оплата.query.all()
    print(f"Оплаты: {len(payments)}")
    if payments:
        for payment in payments[:3]:
            print(f"  - Сумма: {payment.сумма}, Дата: {payment.дата_оплаты}")
    
    # Проверяем расходы
    expenses = Расходы.query.all()
    print(f"Расходы: {len(expenses)}")
    if expenses:
        for expense in expenses[:3]:
            print(f"  - {expense.тип}: {expense.сумма} ({expense.дата})")
    
    # Проверяем зарплаты
    salaries = Зарплаты.query.all()
    print(f"Зарплаты: {len(salaries)}")
    if salaries:
        for salary in salaries[:3]:
            emp_name = f"{salary.сотрудник.имя} {salary.сотрудник.фамилия}" if salary.сотрудник else "Н/Д"
            print(f"  - {emp_name}: {salary.базовая_ставка} + {salary.процент_от_выручки}%") 