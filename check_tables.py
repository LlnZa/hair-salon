from app import app, db
from models import Филиалы, Услуги, Клиенты, Сотрудники, Оплата, Расходы, Записи, Зарплаты
from insert_test_data import add_appointments_and_payments, add_expenses, add_salaries

def check_tables():
    with app.app_context():
        print("Проверка таблиц в базе данных:")
        print(f"Филиалы: {Филиалы.query.count()} записей")
        print(f"Услуги: {Услуги.query.count()} записей")
        print(f"Сотрудники: {Сотрудники.query.count()} записей")
        print(f"Клиенты: {Клиенты.query.count()} записей")
        print(f"Записи: {Записи.query.count()} записей")
        print(f"Оплата: {Оплата.query.count()} записей")
        print(f"Расходы: {Расходы.query.count()} записей")
        print(f"Зарплаты: {Зарплаты.query.count()} записей")

        # Принудительное добавление данных в пустые таблицы
        if Записи.query.count() == 0 or Оплата.query.count() == 0:
            print("\nДобавление записей и оплат...")
            add_appointments_and_payments()
        
        if Расходы.query.count() == 0:
            print("\nДобавление расходов...")
            add_expenses()
        
        if Зарплаты.query.count() == 0:
            print("\nДобавление зарплат...")
            add_salaries()

if __name__ == "__main__":
    check_tables() 