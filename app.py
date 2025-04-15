from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from config import Config
from models import db, Клиенты, Сотрудники, Филиалы, Услуги, Записи, История_цен, Оплата, Расходы, Зарплаты
from datetime import datetime, timedelta
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField, DateField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from werkzeug.security import generate_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz
import atexit
import random
import string
from werkzeug.utils import secure_filename
import pandas as pd
import io
from sqlalchemy import func
import xlsxwriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
from forms import AddEmployeeForm

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://hair_salon_user:ERa7fcyODXXoU7Nck30fEY9HJGejcSzN@dpg-cvue38a4d50c73atiucg-a/hair_salon_8vaf'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False




# Конфигурация Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.yandex.ru'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'dovar.m@yandex.ru'  
app.config['MAIL_PASSWORD'] = 'hewnpqcyawexnqvy'     
app.config['MAIL_DEFAULT_SENDER'] = 'dovar.m@yandex.ru'  

db.init_app(app)
migrate = Migrate(app, db)  # Добавляем поддержку миграций
login_manager = LoginManager(app)
mail = Mail(app)  
csrf = CSRFProtect(app)  # Инициализация CSRF-защиты
login_manager.login_view = 'login'

# Инициализация планировщика задач
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Moscow'))
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

def send_appointment_email(appointment, is_reminder=False):
    """Отправка email о записи или напоминания"""
    client = Клиенты.query.get(appointment.клиент_id)
    service = Услуги.query.get(appointment.услуга_id)
    employee = Сотрудники.query.get(appointment.сотрудник_id)
    branch = Филиалы.query.get(appointment.филиал_id)
    
    if is_reminder:
        subject = 'Напоминание о записи'
        template = 'email/appointment_reminder.html'
    else:
        subject = 'Подтверждение записи'
        template = 'email/appointment_confirmation.html'
    
    msg = Message(
        subject,
        recipients=[client.email]
    )
    msg.html = render_template(
        template,
        client=client,
        service=service,
        employee=employee,
        branch=branch,
        appointment=appointment
    )
    mail.send(msg)

def schedule_reminder(appointment):
    """Планирование отправки напоминания за 45 минут до записи"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    reminder_time = appointment.дата_визита - timedelta(minutes=45)
    
    # Преобразуем время в московский часовой пояс
    reminder_time = moscow_tz.localize(reminder_time)
    
    if reminder_time > datetime.now(moscow_tz):
        scheduler.add_job(
            send_appointment_email,
            trigger=DateTrigger(run_date=reminder_time),
            args=[appointment, True],
            id=f'reminder_{appointment.запись_id}'
        )

@login_manager.user_loader
def load_user(user_id):
    try:
        # Разбиваем строковый идентификатор на префикс и реальный id
        user_type, real_id = user_id.split('-', 1)
        if user_type == 'employee':
            return Сотрудники.query.get(int(real_id))
        elif user_type == 'client':
            return Клиенты.query.get(int(real_id))
        else:
            return None
    except Exception as e:
        return None


# Маршруты
@app.route('/')
def index():
    # Получаем популярные услуги (например, 6 самых дорогих)
    popular_services = Услуги.query.order_by(Услуги.базовая_цена.desc()).limit(6).all()
    
    # Временно убираем отзывы
    reviews = []
    
    if current_user.is_authenticated:
        if current_user.роль == 'accountant':
            return redirect(url_for('accountant_dashboard'))
        elif current_user.роль in ['admin', 'owner']:
            return redirect(url_for('admin_services'))
    
    services = Услуги.query.all()
    return render_template('services.html', services=services)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Сначала проверяем в таблице Сотрудники
        user = Сотрудники.query.filter_by(логин=username).first()
        if not user:
            # Если не нашли, проверяем в таблице Клиенты
            user = Клиенты.query.filter_by(логин=username).first()
        
        if not user:
            flash('Пользователь не найден')
            return render_template('auth/login.html')
            
        try:
            if user.check_password(password):
                login_user(user)
                flash('Вы успешно вошли в систему')
                
                # Перенаправляем пользователя в зависимости от его роли
                if hasattr(user, 'роль'):
                    if user.роль == 'owner':
                        return redirect(url_for('admin_employees'))
                    elif user.роль == 'admin':
                        return redirect(url_for('admin_employees'))
                    elif user.роль == 'accountant':
                        return redirect(url_for('reports'))
                    elif user.роль == 'employee':
                        return redirect(url_for('appointments'))
                # Для клиентов
                return redirect(url_for('index'))
            else:
                flash('Неверный пароль')
        except Exception as e:
            flash(f'Ошибка при проверке пароля: {str(e)}')
            print(f'Ошибка при проверке пароля: {str(e)}')
            
            # Обновляем пароль пользователя на временный, если возникла ошибка хеширования
            if 'unsupported hash type' in str(e):
                try:
                    user.set_password('temp_password123')
                    db.session.commit()
                    flash('Пароль был обновлен из-за ошибки. Пожалуйста, войдите с паролем: temp_password123')
                except Exception as e2:
                    flash(f'Ошибка при обновлении пароля: {str(e2)}')
            
    return render_template('auth/login.html')

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = Клиенты.query.filter_by(email=email).first()
        
        if user:
            try:
                # Generate token
                token = user.get_reset_password_token()
                
                # Send email with reset link
                send_password_reset_email(user, token)
                
                flash('На вашу почту отправлены инструкции по сбросу пароля.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                flash(f'Ошибка при отправке письма: {str(e)}', 'danger')
                print(f'Ошибка при отправке письма для сброса пароля: {str(e)}')
    else:
            flash('Клиент с таким email не найден.', 'danger')
    
    return render_template('auth/reset_password_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    user = Клиенты.verify_reset_password_token(token)
    if not user:
        flash('Недействительная или истекшая ссылка для сброса пароля.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password')
        password2 = request.form.get('password2')
        
        if not password or not password2:
            flash('Пожалуйста, заполните все поля.', 'danger')
            return redirect(url_for('reset_password', token=token))
        
        if password != password2:
            flash('Пароли не совпадают.', 'danger')
            return redirect(url_for('reset_password', token=token))
        
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов.', 'danger')
            return redirect(url_for('reset_password', token=token))
        
        user.set_password(password)
        db.session.commit()
        flash('Ваш пароль был успешно изменен.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html')

def send_password_reset_email(user, token):
    reset_url = url_for('reset_password', token=token, _external=True)
    try:
        msg = Message(
            'Сброс пароля в барбершопе',
            recipients=[user.email]
        )
        msg.body = f'''
Здравствуйте, {user.имя}!

Вы запросили сброс пароля для вашего аккаунта в барбершопе.
Чтобы сбросить пароль, перейдите по следующей ссылке:

{reset_url}

Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.

С уважением,
Команда барбершопа
'''
        mail.send(msg)
        print(f'Письмо для сброса пароля отправлено на {user.email}')
    except Exception as e:
        print(f'Ошибка при отправке письма: {str(e)}')

class RegistrationForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Телефон', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    last_name = StringField('Фамилия', validators=[DataRequired()])
    middle_name = StringField('Отчество')
    gender = SelectField('Пол', choices=[('М', 'Мужской'), ('Ж', 'Женский')])
    birth_date = DateField('Дата рождения', format='%Y-%m-%d', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password', message='Пароли должны совпадать')])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        client = Клиенты.query.filter_by(логин=username.data).first()
        if client:
            raise ValidationError('Этот логин уже занят. Пожалуйста, выберите другой.')

    def validate_email(self, email):
        client = Клиенты.query.filter_by(email=email.data).first()
        if client:
            raise ValidationError('Этот email уже зарегистрирован.')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Создаем форму
    form = RegistrationForm()
    print(f"Форма отправлена: {request.method}")
    print(f"Валидация формы: {form.validate_on_submit()}")
    
    # Проверяем, был ли отправлен POST-запрос и прошла ли форма валидацию
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                print("Форма прошла валидацию, создаем пользователя...")
                hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
                client = Клиенты(
                    логин=form.username.data,
                    email=form.email.data,
                    пароль_хеш=hashed_password,
                    имя=form.first_name.data,
                    фамилия=form.last_name.data,
                    отчество=form.middle_name.data,
                    телефон=form.phone.data,
                    пол=form.gender.data,
                    дата_рождения=form.birth_date.data,
                    дата_регистрации=datetime.now()
                )
                db.session.add(client)
                db.session.commit()
                
                flash('Регистрация успешно завершена! Теперь вы можете войти в систему.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при создании пользователя: {str(e)}")
                flash('Произошла ошибка при регистрации. Пожалуйста, попробуйте еще раз.', 'danger')
    
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/services')
def services():
    services = Услуги.query.all()
    return render_template('services.html', services=services)

def is_working_time(dt):
    # Проверяем день недели (0 - понедельник, 6 - воскресенье)
    weekday = dt.weekday()
    
    # Воскресенье - выходной
    if weekday == 6:
        return False
    
    # Получаем часы
    hour = dt.hour
    
    # Рабочие часы:
    # Пн-Пт: 10:00 - 21:00
    # Сб: 10:00 - 17:00
    if weekday == 5:  # Суббота
        return 10 <= hour < 17
    else:  # Пн-Пт
        return 10 <= hour < 21

@app.route('/book_service/<int:service_id>', methods=['GET', 'POST'])
def book_service(service_id):
    service = Услуги.query.get_or_404(service_id)

    if request.method == 'POST':
        # Получаем данные из формы
        visit_date = request.form.get('visit_date')
        note = request.form.get('note')
        branch_id = request.form.get('branch_id')
        employee_id = request.form.get('employee_id')
        
        # Если пользователь не авторизован, получаем данные для регистрации
        if not current_user.is_authenticated:
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            
            if not all([first_name, last_name, email]):
                flash('Пожалуйста, заполните все обязательные поля')
                return redirect(url_for('book_service', service_id=service_id))
            
            # Генерируем логин и пароль
            username = f"{first_name.lower()}{last_name.lower()}{datetime.now().strftime('%Y%m%d%H%M%S')}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            try:
                # Создаем нового клиента
                client = Клиенты(
                    логин=username,
                    email=email,
                    имя=first_name,
                    фамилия=last_name,
                    дата_регистрации=datetime.now()
                )
                client.set_password(password)
                db.session.add(client)
                db.session.commit()
                
                # Отправляем email с данными для входа
                msg = Message(
                    'Добро пожаловать в наш барбершоп!',
                    recipients=[email]
                )
                msg.body = f'''
                Здравствуйте, {first_name} {last_name}!
                
                Спасибо за регистрацию в нашем барбершопе.
                Ваши данные для входа:
                Логин: {username}
                Пароль: {password}
                
                Теперь вы можете войти в систему и управлять своими записями.
                
                С уважением,
                Команда барбершопа
                '''
                mail.send(msg)
                
                # Автоматически входим в систему
                login_user(client)
                
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при регистрации: {str(e)}')
                return redirect(url_for('book_service', service_id=service_id))
        
        try:
            visit_datetime = datetime.strptime(visit_date, '%Y-%m-%dT%H:%M')
            
            # Проверяем, что дата не в прошлом
            if visit_datetime < datetime.now():
                flash('Нельзя записаться на прошедшую дату')
                return redirect(url_for('book_service', service_id=service_id))
            
            # Проверяем рабочее время
            if not is_working_time(visit_datetime):
                flash('Выбранное время не входит в рабочие часы. Рабочие часы: Пн-Пт 10:00-21:00, Сб 10:00-17:00, Вс - выходной')
                return redirect(url_for('book_service', service_id=service_id))
            
            # Проверяем, нет ли уже записи на это время у выбранного сотрудника
            existing_appointment = Записи.query.filter_by(
                дата_визита=visit_datetime,
                сотрудник_id=employee_id
            ).first()
            
            if existing_appointment:
                flash('Это время уже занято. Пожалуйста, выберите другое время.')
                return redirect(url_for('book_service', service_id=service_id))
            
            # Создаем новую запись
            appointment = Записи(
                клиент_id=current_user.клиент_id,
                сотрудник_id=employee_id,
                филиал_id=branch_id,
                услуга_id=service_id,
                дата_визита=visit_datetime,
                примечание=note,
                статус='ожидает'
            )
            
            db.session.add(appointment)
            db.session.commit()
            
            # Отправляем email с подтверждением
            send_appointment_email(appointment)
            
            # Планируем отправку напоминания
            schedule_reminder(appointment)
            
            flash('Вы успешно записаны на услугу! На ваш email отправлено подтверждение.')
            return redirect(url_for('my_appointments'))
            
        except ValueError:
            flash('Неверный формат даты и времени')
            return redirect(url_for('book_service', service_id=service_id))
    
    # Получаем список филиалов и сотрудников для выбора
    branches = Филиалы.query.all()
    employees = Сотрудники.query.filter_by(роль='hairdresser').all()
    
    return render_template('book_service.html', 
                         service=service,
                         branches=branches,
                         employees=employees)

@app.route('/my_appointments')
@login_required
def my_appointments():
    # Проверяем, что пользователь является клиентом
    if not isinstance(current_user, Клиенты):
        flash('Эта страница доступна только клиентам')
        return redirect(url_for('index'))
    
    appointments = Записи.query\
        .filter_by(клиент_id=current_user.клиент_id)\
        .join(Услуги, Услуги.услуга_id == Записи.услуга_id)\
        .join(Сотрудники, Сотрудники.сотрудник_id == Записи.сотрудник_id)\
        .join(Филиалы, Филиалы.филиал_id == Записи.филиал_id)\
        .add_entity(Услуги)\
        .add_entity(Сотрудники)\
        .add_entity(Филиалы)\
        .order_by(Записи.дата_визита.desc())\
        .all()
    
    # Преобразуем результаты в более удобный формат
    formatted_appointments = []
    for appointment, service, employee, branch in appointments:
        appointment.service = service
        appointment.employee = employee
        appointment.branch = branch
        formatted_appointments.append(appointment)
    
    return render_template('my_appointments.html', appointments=formatted_appointments)

@app.route('/branches')
def branches():
    # Получаем все филиалы
    all_branches = Филиалы.query.all()
    return render_template('branches.html', branches=all_branches)

@app.route('/admin/employees')
@login_required
def admin_employees():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    employees = Сотрудники.query.all()
    branches = Филиалы.query.all()
    return render_template('admin/employees.html', employees=employees, branches=branches)

@app.route('/price_history')
@login_required
def price_history():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    history = db.session.query(История_цен, Услуги).join(Услуги).order_by(История_цен.дата_изменения.desc()).all()
    return render_template('admin/price_history.html', history=history)

@app.route('/appointments')
@login_required
def appointments():
    if current_user.роль not in ['admin', 'employee', 'owner', 'accountant']:  # Добавляем owner и accountant
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Для админа, владельца и бухгалтера показываем все записи, для сотрудника - только его записи
    if current_user.роль in ['admin', 'owner', 'accountant']:
        appointments = Записи.query.order_by(Записи.дата_визита.desc()).all()
    else:
        appointments = Записи.query.filter_by(сотрудник_id=current_user.сотрудник_id).order_by(Записи.дата_визита.desc()).all()
    
    return render_template('admin/appointments.html', appointments=appointments)

@app.route('/payments')
@login_required
def payments():
    if current_user.роль not in ['admin', 'employee', 'owner', 'accountant']:
    flash('У вас нет прав для доступа к этой странице')
    return redirect(url_for('index'))
    
    payments = db.session.query(Оплата, Записи).join(Записи).order_by(Оплата.дата_оплаты.desc()).all()
    return render_template('admin/payments.html', payments=payments)

@app.route('/cancel_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Записи.query.get_or_404(appointment_id)
    
    # Проверяем, что запись принадлежит текущему клиенту
    if appointment.клиент_id != current_user.клиент_id:
        flash('У вас нет прав для отмены этой записи')
        return redirect(url_for('my_appointments'))
    
    # Проверяем, что запись еще не отменена и не выполнена
    if appointment.статус in ['отменено', 'выполнено']:
        flash('Нельзя отменить эту запись')
        return redirect(url_for('my_appointments'))
    
    # Отменяем запись
    appointment.статус = 'отменено'
    db.session.commit()
    
    flash('Запись успешно отменена')
    return redirect(url_for('my_appointments'))

@app.route('/delete_account', methods=['GET', 'POST'])
@login_required
def delete_account():
    if request.method == 'POST':
        # Удаляем все записи пользователя
        Записи.query.filter_by(клиент_id=current_user.клиент_id).delete()
        
        # Удаляем пользователя
        db.session.delete(current_user)
        db.session.commit()
        
        # Выходим из системы
        logout_user()
        
        flash('Ваш аккаунт был успешно удален.', 'success')
        return redirect(url_for('index'))
    
    return render_template('delete_account.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.роль != 'client':
        flash('Эта страница доступна только клиентам')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Обновляем данные клиента
        current_user.фамилия = request.form.get('last_name')
        current_user.имя = request.form.get('first_name')
        current_user.отчество = request.form.get('middle_name')
        gender = request.form.get('gender')
        if gender not in ['М', 'Ж']:
            flash('Неверное значение для пола. Выберите "М" или "Ж".')
            return redirect(url_for('profile'))
        current_user.пол = gender
        current_user.телефон = request.form.get('phone')
        current_user.email = request.form.get('email')
        
        # Обновляем дату рождения, если она указана
        birth_date = request.form.get('birth_date')
        if birth_date:
            try:
                current_user.дата_рождения = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Неверный формат даты рождения')
                return redirect(url_for('profile'))
        
        db.session.commit()
        flash('Данные успешно обновлены')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    if current_user.роль != 'client':
        flash('Эта страница доступна только клиентам')
        return redirect(url_for('index'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_user.check_password(current_password):
        flash('Неверный текущий пароль')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('Новые пароли не совпадают')
        return redirect(url_for('profile'))
    
    current_user.set_password(new_password)
    db.session.commit()
    flash('Пароль успешно изменен')
    return redirect(url_for('profile'))

@app.route('/visit_history')
@login_required
def visit_history():
    if not isinstance(current_user, Клиенты):
        flash('Эта страница доступна только клиентам')
        return redirect(url_for('index'))
    
    # Получаем все записи клиента, отсортированные по дате (сначала новые)
    visits = Записи.query\
        .filter_by(клиент_id=current_user.клиент_id)\
        .join(Услуги, Услуги.услуга_id == Записи.услуга_id)\
        .join(Сотрудники, Сотрудники.сотрудник_id == Записи.сотрудник_id)\
        .join(Филиалы, Филиалы.филиал_id == Записи.филиал_id)\
        .add_entity(Услуги)\
        .add_entity(Сотрудники)\
        .add_entity(Филиалы)\
        .filter(Записи.дата_визита < datetime.now())\
        .order_by(Записи.дата_визита.desc())\
        .all()
    
    # Преобразуем результаты в более удобный формат
    formatted_visits = []
    for visit, service, employee, branch in visits:
        visit.service = service
        visit.employee = employee
        visit.branch = branch
        formatted_visits.append(visit)
    
    return render_template('visit_history.html', visits=formatted_visits)

@app.route('/admin/clients')
@login_required
def clients():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    clients = Клиенты.query.order_by(Клиенты.дата_регистрации.desc()).all()
    return render_template('admin/clients.html', clients=clients)

@app.route('/admin/clients/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if current_user.роль not in ['accountant', 'owner']:
    flash('У вас нет прав для доступа к этой странице')
    return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            client = Клиенты(
                логин=request.form.get('username'),
                email=request.form.get('email'),
                телефон=request.form.get('phone'),
                имя=request.form.get('first_name'),
                фамилия=request.form.get('last_name'),
                отчество=request.form.get('middle_name'),
                пол=request.form.get('gender'),
                дата_рождения=datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date(),
                дата_регистрации=datetime.now()
            )
            client.set_password(request.form.get('password'))
            
            db.session.add(client)
            db.session.commit()
            flash('Клиент успешно добавлен')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Ошибка при добавлении клиента: {str(e)}')
    
    return render_template('admin/add_client.html')

@app.route('/admin/clients/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    if current_user.роль != 'admin':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    client = Клиенты.query.get_or_404(client_id)
    
    if request.method == 'POST':
        try:
            client.логин = request.form.get('username')
            client.email = request.form.get('email')
            client.телефон = request.form.get('phone')
            client.имя = request.form.get('first_name')
            client.фамилия = request.form.get('last_name')
            client.отчество = request.form.get('middle_name')
            client.пол = request.form.get('gender')
            client.дата_рождения = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
            
            if request.form.get('password'):
                client.set_password(request.form.get('password'))
            
            db.session.commit()
            flash('Данные клиента успешно обновлены')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Ошибка при обновлении данных клиента: {str(e)}')
    
    return render_template('admin/edit_client.html', client=client)

@app.route('/clients/<int:client_id>/delete', methods=['POST'])
@login_required
def delete_client(client_id):
    if current_user.роль != 'admin':
        flash('У вас нет прав для выполнения этого действия', 'danger')
        return redirect(url_for('clients'))
    
    client = Клиенты.query.get_or_404(client_id)
    try:
        # First delete all related records
        Записи.query.filter_by(клиент_id=client_id).delete()
        db.session.delete(client)
        db.session.commit()
        flash('Клиент успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении клиента: {str(e)}', 'danger')
    
    return redirect(url_for('clients'))

@app.route('/admin/add_employee', methods=['GET', 'POST'])
@login_required
def add_employee():
    if current_user.роль not in ['admin', 'owner']:
    flash('У вас нет прав для доступа к этой странице', 'danger')
    return redirect(url_for('index'))
    
    form = AddEmployeeForm()
    form.branch_id.choices = [(b.филиал_id, b.название) for b in Филиалы.query.all()]
    
    if form.validate_on_submit():
        employee = Сотрудники(
            логин=form.username.data,
            пароль_хеш=generate_password_hash(form.password.data),
            имя=form.first_name.data,
            фамилия=form.last_name.data,
            должность=form.position.data,
            филиал_id=form.branch_id.data,
            дата_приема=form.hire_date.data,
            телефон=form.phone.data
        )
        db.session.add(employee)
        db.session.commit()
        flash('Сотрудник успешно добавлен', 'success')
        return redirect(url_for('employees'))
    
    return render_template('admin/add_employee.html', form=form)

@app.route('/admin/employees/<int:employee_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(employee_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    employee = Сотрудники.query.get_or_404(employee_id)
    
    if request.method == 'POST':
        try:
            new_role = request.form.get('role')
            
            # Проверка на изменение роли последнего администратора
            if employee.роль in ['admin', 'owner'] and new_role not in ['admin', 'owner']:
                # Подсчитываем количество оставшихся админов/владельцев
                admin_count = Сотрудники.query.filter(
                    Сотрудники.роль.in_(['admin', 'owner']),
                    Сотрудники.сотрудник_id != employee_id
                ).count()
                
                if admin_count == 0:
                    flash('Невозможно изменить роль последнего администратора/владельца')
                    return redirect(url_for('admin_employees'))
            
            # Проверка на защищенный аккаунт владельца
            if employee.логин == 'owner' and (
                request.form.get('role') != 'owner' or 
                request.form.get('position') != 'Владелец'
            ):
                flash('Невозможно изменить роль и должность защищенного аккаунта владельца')
                return redirect(url_for('admin_employees'))
            
            employee.имя = request.form.get('first_name')
            employee.фамилия = request.form.get('last_name')
            employee.должность = request.form.get('position')
            employee.роль = new_role
            employee.филиал_id = request.form.get('branch_id')
            
            if request.form.get('password'):
                employee.set_password(request.form.get('password'))
            
            db.session.commit()
            flash('Сотрудник успешно обновлен')
            return redirect(url_for('admin_employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении сотрудника: {str(e)}')
    
    branches = Филиалы.query.all()
    return render_template('admin/edit_employee.html', employee=employee, branches=branches)

@app.route('/admin/employees/<int:employee_id>/delete', methods=['POST'])
@login_required
def delete_employee(employee_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для выполнения этого действия')
        return redirect(url_for('index'))
    
    employee = Сотрудники.query.get_or_404(employee_id)
    
    # Проверка на удаление защищенного аккаунта владельца
    if employee.логин == 'owner':
        flash('Невозможно удалить защищенный аккаунт владельца')
        return redirect(url_for('admin_employees'))
    
    # Проверка на удаление последнего администратора
    if employee.роль in ['admin', 'owner']:
        admin_count = Сотрудники.query.filter(
            Сотрудники.роль.in_(['admin', 'owner']),
            Сотрудники.сотрудник_id != employee_id
        ).count()
        
        if admin_count == 0:
            flash('Невозможно удалить последнего администратора/владельца')
            return redirect(url_for('admin_employees'))
    
    try:
        # Сначала удаляем все связанные записи
        Записи.query.filter_by(сотрудник_id=employee_id).delete()
        # Удаляем записи о зарплатах
        Зарплаты.query.filter_by(сотрудник_id=employee_id).delete()
        # Затем удаляем самого сотрудника
        db.session.delete(employee)
        db.session.commit()
        flash('Сотрудник успешно удален')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении сотрудника: {str(e)}')
    
    return redirect(url_for('admin_employees'))

# Маршруты для управления записями
@app.route('/appointments/add', methods=['GET', 'POST'])
@login_required
def add_appointment():
    if current_user.роль not in ['admin', 'employee', 'owner']:  # Добавляем owner
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            appointment = Записи(
                клиент_id=request.form.get('клиент_id'),
                услуга_id=request.form.get('услуга_id'),
                сотрудник_id=request.form.get('сотрудник_id'),
                филиал_id=request.form.get('филиал_id'),
                дата_визита=datetime.strptime(f"{request.form.get('дата_визита')} {request.form.get('время_визита')}", '%Y-%m-%d %H:%M'),
                примечание=request.form.get('примечание')
            )
            db.session.add(appointment)
            db.session.commit()
            flash('Запись успешно добавлена')
            return redirect(url_for('appointments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении записи: {str(e)}')
    
    clients = Клиенты.query.all()
    services = Услуги.query.all()
    employees = Сотрудники.query.filter_by(роль='hairdresser').all()
    branches = Филиалы.query.all()
    
    return render_template('add_appointment.html', 
                         clients=clients,
                         services=services,
                         employees=employees,
                         branches=branches)

@app.route('/appointments/<int:appointment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_appointment(appointment_id):
    if current_user.роль not in ['admin', 'employee', 'owner']:  # Добавляем owner
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    appointment = Записи.query.get_or_404(appointment_id)
    
    if request.method == 'POST':
        try:
            appointment.клиент_id = request.form.get('клиент_id')
            appointment.услуга_id = request.form.get('услуга_id')
            appointment.сотрудник_id = request.form.get('сотрудник_id')
            appointment.филиал_id = request.form.get('филиал_id')
            appointment.дата_визита = datetime.strptime(f"{request.form.get('дата_визита')} {request.form.get('время_визита')}", '%Y-%m-%d %H:%M')
            appointment.примечание = request.form.get('примечание')
            
            db.session.commit()
            flash('Запись успешно обновлена')
            return redirect(url_for('appointments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении записи: {str(e)}')
    
    clients = Клиенты.query.all()
    services = Услуги.query.all()
    employees = Сотрудники.query.filter_by(роль='hairdresser').all()
    branches = Филиалы.query.all()
    
    return render_template('edit_appointment.html',
                         appointment=appointment,
                               clients=clients,
                         services=services,
                               employees=employees,
                         branches=branches)

@app.route('/appointments/<int:appointment_id>/delete', methods=['POST'])
@login_required
def delete_appointment(appointment_id):
    if current_user.роль not in ['admin', 'employee', 'owner']:  # Добавляем owner
        flash('У вас нет прав для выполнения этого действия')
        return redirect(url_for('index'))
    
    appointment = Записи.query.get_or_404(appointment_id)
    try:
        db.session.delete(appointment)
        db.session.commit()
        flash('Запись успешно удалена')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении записи: {str(e)}')
    
    return redirect(url_for('appointments'))

# Маршруты для управления платежами
@app.route('/admin/payments/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    if current_user.роль not in ['admin', 'employee']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            payment = Оплата(
                запись_id=request.form.get('запись_id'),
                сумма=float(request.form.get('сумма')),
                способ_оплаты=request.form.get('способ_оплаты'),
                дата_оплаты=datetime.strptime(request.form.get('дата_оплаты'), '%Y-%m-%d'),
                статус_оплаты='оплачено'
            )
            db.session.add(payment)
            
            # Update appointment status
            appointment = Записи.query.get(payment.запись_id)
            if appointment:
                appointment.статус = 'оплачено'
            
            db.session.commit()
            flash('Оплата успешно добавлена', 'success')
            return redirect(url_for('payments'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении оплаты: {str(e)}', 'danger')
    
    # Get appointments that don't have payments yet
    appointments = Записи.query.filter(~Записи.оплата_set.any()).all()
    return render_template('admin/add_payment.html', 
                         appointments=appointments,
                         now=datetime.now())

@app.route('/admin/payments/edit/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    if current_user.роль not in ['admin', 'employee']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Заглушка
    flash('Функция редактирования платежа еще не реализована')
    return redirect(url_for('payments'))

@app.route('/admin/payments/delete/<int:payment_id>', methods=['POST'])
@login_required
def delete_payment(payment_id):
    if current_user.роль not in ['admin', 'employee']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Заглушка
    flash('Функция удаления платежа еще не реализована')
    return redirect(url_for('payments'))

# Маршруты для управления ценами
@app.route('/admin/prices/add', methods=['GET', 'POST'])
@login_required
def add_price():
    if current_user.роль != 'admin':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Заглушка
    flash('Функция добавления новой цены еще не реализована')
    return redirect(url_for('price_history'))

@app.route('/register_simple', methods=['GET', 'POST'])
def register_simple():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Проверяем что пароли совпадают
        if request.form.get('password') != request.form.get('confirm_password'):
            flash('Пароли не совпадают', 'danger')
            return render_template('auth/register_simple.html')
        
        # Проверяем, что логин и email уникальны
        username = request.form.get('username')
        email = request.form.get('email')
        
        if Клиенты.query.filter_by(логин=username).first():
            flash('Этот логин уже занят. Пожалуйста, выберите другой.', 'danger')
            return render_template('auth/register_simple.html')
        
        if Клиенты.query.filter_by(email=email).first():
            flash('Этот email уже зарегистрирован.', 'danger')
            return render_template('auth/register_simple.html')
        
        try:
            # Создаем нового клиента
            hashed_password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
            
            # Преобразуем дату рождения из строки в объект datetime
            birth_date = datetime.strptime(request.form.get('birth_date'), '%Y-%m-%d').date()
            
            client = Клиенты(
                логин=username,
                email=email,
                пароль_хеш=hashed_password,
                имя=request.form.get('first_name'),
                фамилия=request.form.get('last_name'),
                отчество=request.form.get('middle_name'),
                телефон=request.form.get('phone'),
                пол=request.form.get('gender'),
                дата_рождения=birth_date,
                дата_регистрации=datetime.now()
            )
            
            db.session.add(client)
            db.session.commit()
            
            # Отправляем подтверждение на email
            try:
                msg = Message(
                    'Добро пожаловать в наш барбершоп!',
                    recipients=[email]
                )
                msg.body = f'''
                Здравствуйте, {request.form.get('first_name')} {request.form.get('last_name')}!
                
                Спасибо за регистрацию в нашем барбершопе.
                Ваш логин: {username}
                
                Теперь вы можете войти в систему и записаться на услуги.
                
                С уважением,
                Команда барбершопа
                '''
                mail.send(msg)
                flash('Регистрация успешна! На ваш email отправлено письмо с подтверждением.', 'success')
            except Exception as e:
                flash('Регистрация успешна, но не удалось отправить email с подтверждением.', 'warning')
                print(f'Ошибка отправки email: {str(e)}')
            
            # Автоматически входим в систему
            login_user(client)
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при регистрации: {str(e)}', 'danger')
            print(f'Ошибка при регистрации: {str(e)}')
    
    return render_template('auth/register_simple.html')

# Маршруты для управления филиалами
@app.route('/admin/branches')
@login_required
def admin_branches():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    branches = Филиалы.query.all()
    return render_template('admin/branches.html', branches=branches)

@app.route('/admin/branches/add', methods=['GET', 'POST'])
@login_required
def add_branch():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            branch = Филиалы(
                название=request.form.get('name'),
                адрес=request.form.get('address'),
                телефон=request.form.get('phone')
            )
            db.session.add(branch)
            db.session.commit()
            flash('Филиал успешно добавлен')
            return redirect(url_for('admin_branches'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении филиала: {str(e)}')
    
    return render_template('admin/add_branch.html')

@app.route('/admin/branches/edit/<int:branch_id>', methods=['GET', 'POST'])
@login_required
def edit_branch(branch_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    branch = Филиалы.query.get_or_404(branch_id)
    
    if request.method == 'POST':
        try:
            branch.название = request.form.get('name')
            branch.адрес = request.form.get('address')
            branch.телефон = request.form.get('phone')
            
            db.session.commit()
            flash('Филиал успешно обновлен')
            return redirect(url_for('admin_branches'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении филиала: {str(e)}')
    
    return render_template('admin/edit_branch.html', branch=branch)

@app.route('/admin/branches/delete/<int:branch_id>', methods=['POST'])
@login_required
def delete_branch(branch_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    branch = Филиалы.query.get_or_404(branch_id)
    
    try:
        # Проверить, есть ли связанные записи
        if Сотрудники.query.filter_by(филиал_id=branch_id).first() or Записи.query.filter_by(филиал_id=branch_id).first():
            flash('Невозможно удалить филиал, есть связанные сотрудники или записи')
            return redirect(url_for('admin_branches'))
        
        db.session.delete(branch)
        db.session.commit()
        flash('Филиал успешно удален')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении филиала: {str(e)}')
    
    return redirect(url_for('admin_branches'))

@app.route('/hairdresser/appointments')
@login_required
def hairdresser_appointments():
    if current_user.роль != 'hairdresser':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем все записи, где сотрудник = текущий пользователь, сортируем по дате (сначала ближайшие)
    appointments = Записи.query\
        .filter_by(сотрудник_id=current_user.сотрудник_id)\
        .filter(Записи.дата_визита >= datetime.now())\
        .join(Клиенты, Клиенты.клиент_id == Записи.клиент_id)\
        .join(Услуги, Услуги.услуга_id == Записи.услуга_id)\
        .join(Филиалы, Филиалы.филиал_id == Записи.филиал_id)\
        .add_entity(Клиенты)\
        .add_entity(Услуги)\
        .add_entity(Филиалы)\
        .order_by(Записи.дата_визита.asc())\
        .all()
    
    # Преобразуем результаты в более удобный формат
    formatted_appointments = []
    for appointment, client, service, branch in appointments:
        appointment.client = client
        appointment.service = service
        appointment.branch = branch
        formatted_appointments.append(appointment)
    
    return render_template('hairdresser/appointments.html', appointments=formatted_appointments)

@app.route('/hairdresser/past_appointments')
@login_required
def hairdresser_past_appointments():
    if current_user.роль != 'hairdresser':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем все прошедшие записи, где сотрудник = текущий пользователь
    appointments = Записи.query.filter_by(сотрудник_id=current_user.сотрудник_id)\
        .filter(Записи.дата_визита < datetime.now())\
        .order_by(Записи.дата_визита.desc()).all()
    
    return render_template('hairdresser/past_appointments.html', appointments=appointments)

@app.route('/hairdresser/appointment/<int:appointment_id>')
@login_required
def hairdresser_appointment_details(appointment_id):
    if current_user.роль != 'hairdresser':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем запись и проверяем, что она принадлежит текущему парикмахеру
    appointment = Записи.query.get_or_404(appointment_id)
    if appointment.сотрудник_id != current_user.сотрудник_id:
        flash('У вас нет прав для просмотра этой записи')
        return redirect(url_for('hairdresser_appointments'))
    
    # Получаем данные о клиенте и услуге
    client = Клиенты.query.get(appointment.клиент_id)
    service = Услуги.query.get(appointment.услуга_id)
    branch = Филиалы.query.get(appointment.филиал_id)
    
    return render_template('hairdresser/appointment_details.html', 
                          appointment=appointment,
                          client=client,
                          service=service,
                          branch=branch)

@app.route('/hairdresser/complete_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def complete_appointment(appointment_id):
    if current_user.роль != 'hairdresser':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем запись и проверяем, что она принадлежит текущему парикмахеру
    appointment = Записи.query.get_or_404(appointment_id)
    if appointment.сотрудник_id != current_user.сотрудник_id:
        flash('У вас нет прав для изменения этой записи')
        return redirect(url_for('hairdresser_appointments'))
    
    # Меняем статус записи на "выполнено"
    appointment.статус = 'выполнено'
    db.session.commit()
    
    flash('Запись отмечена как выполненная')
    return redirect(url_for('hairdresser_appointments'))

@app.route('/admin/services')
@login_required
def admin_services():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    services = Услуги.query.all()
    return render_template('admin/services.html', services=services)

@app.route('/admin/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            название = request.form.get('название')
            описание = request.form.get('описание')
            базовая_цена = request.form.get('базовая_цена')
            категория = request.form.get('категория')
            
            if not название or not базовая_цена:
                flash('Название и базовая цена обязательны для заполнения')
                return render_template('admin/add_service.html')
            
            service = Услуги(
                название_услуги=название,
                описание=описание,
                базовая_цена=float(базовая_цена.replace(',', '.')),
                категория_пола=категория
            )
            db.session.add(service)
            db.session.commit()
            flash('Услуга успешно добавлена')
            return redirect(url_for('admin_services'))
        except ValueError as e:
            db.session.rollback()
            flash('Ошибка: Неверный формат цены. Используйте числа, например: 1000 или 1000.50')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении услуги: {str(e)}')
    
    return render_template('admin/add_service.html')

@app.route('/admin/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    service = Услуги.query.get_or_404(service_id)
    
    if request.method == 'POST':
        try:
            название = request.form.get('название')
            описание = request.form.get('описание', '')
            базовая_цена = request.form.get('базовая_цена')
            категория = request.form.get('категория')
            
            if not название or not базовая_цена:
                flash('Название и базовая цена обязательны для заполнения')
                return render_template('admin/edit_service.html', service=service)
            
            service.название_услуги = название
            service.описание = описание
            service.базовая_цена = float(базовая_цена.replace(',', '.'))
            service.категория_пола = категория
            
            db.session.commit()
            flash('Услуга успешно обновлена')
            return redirect(url_for('admin_services'))
        except ValueError as e:
            db.session.rollback()
            flash('Ошибка: Неверный формат цены. Используйте числа, например: 1000 или 1000.50')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении услуги: {str(e)}')
    
    return render_template('admin/edit_service.html', service=service)

@app.route('/admin/services/delete/<int:service_id>', methods=['POST'])
@login_required
def delete_service(service_id):
    if current_user.роль not in ['admin', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    service = Услуги.query.get_or_404(service_id)
    
    try:
        # Проверяем, есть ли связанные записи
        if Записи.query.filter_by(услуга_id=service_id).first():
            flash('Невозможно удалить услугу, есть связанные записи', 'danger')
            return redirect(url_for('admin_services'))
        
        # Удаляем историю цен для этой услуги
        История_цен.query.filter_by(услуга_id=service_id).delete()
        
        # Удаляем саму услугу
        db.session.delete(service)
        db.session.commit()
        
        flash('Услуга успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении услуги: {str(e)}', 'danger')
    
    return redirect(url_for('admin_services'))

# Маршруты для бухгалтера
@app.route('/accountant/dashboard')
@login_required
def accountant_dashboard():
    if current_user.роль != 'accountant':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем текущую дату и начало месяца
    today = datetime.now()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Получаем сумму доходов за текущий месяц
    monthly_income = db.session.query(func.sum(Оплата.сумма)).filter(
        Оплата.дата_оплаты >= start_of_month
    ).scalar() or 0
    
    # Получаем сумму расходов за текущий месяц
    monthly_expenses = db.session.query(func.sum(Расходы.сумма)).filter(
        Расходы.дата >= start_of_month
    ).scalar() or 0
    
    # Вычисляем прибыль
    profit = monthly_income - monthly_expenses
    
    # Получаем статистику по услугам за месяц
    service_stats = db.session.query(
        Услуги.название_услуги,
        func.count(Записи.запись_id).label('count'),
        func.sum(История_цен.новая_цена).label('total')
    ).join(
        Записи, Записи.услуга_id == Услуги.услуга_id
    ).join(
        История_цен, История_цен.услуга_id == Услуги.услуга_id
    ).filter(
        Записи.дата_визита >= start_of_month
    ).group_by(
        Услуги.название_услуги
    ).all()
    
    # Получаем данные для графика (доходы и расходы по дням)
    last_30_days = today - timedelta(days=30)
    
    daily_income = db.session.query(
        func.date(Оплата.дата_оплаты).label('date'),
        func.sum(Оплата.сумма).label('sum')
    ).filter(
        Оплата.дата_оплаты >= last_30_days
    ).group_by(
        func.date(Оплата.дата_оплаты)
    ).all()
    
    daily_expenses = db.session.query(
        func.date(Расходы.дата).label('date'),
        func.sum(Расходы.сумма).label('sum')
    ).filter(
        Расходы.дата >= last_30_days
    ).group_by(
        func.date(Расходы.дата)
    ).all()
    
    # Подготовка данных для графика
    dates = [(today - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30)]
    income_data = {str(date): sum for date, sum in daily_income}
    expense_data = {str(date): sum for date, sum in daily_expenses}
    
    chart_data = {
        'dates': dates,
        'income': [income_data.get(date, 0) for date in dates],
        'expenses': [expense_data.get(date, 0) for date in dates]
    }
    
    return render_template('accountant/dashboard.html',
                         monthly_income=monthly_income,
                         monthly_expenses=monthly_expenses,
                         profit=profit,
                         service_stats=service_stats,
                         chart_data=chart_data)

@app.route('/accountant/reports')
@login_required
def reports():
    if current_user.роль not in ['accountant', 'owner']:  # Добавляем owner
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    return render_template('accountant/reports.html')

@app.route('/accountant/generate_report', methods=['POST'])
@login_required
def generate_report():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    report_type = request.form.get('report_type')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
    end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
    
    try:
        if report_type == 'income':
            # Отчет по доходам
            data = db.session.query(
                func.date(Оплата.дата_оплаты).label('date'),
                func.sum(Оплата.сумма).label('total')
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                func.date(Оплата.дата_оплаты)
            ).order_by(
                func.date(Оплата.дата_оплаты)
            ).all()
            
        elif report_type == 'services':
            # Отчет по услугам
            data = db.session.query(
                Услуги.название_услуги,
                func.count(Записи.запись_id).label('count'),
                func.sum(Оплата.сумма).label('total')
            ).join(
                Записи, Записи.услуга_id == Услуги.услуга_id
            ).join(
                Оплата, Оплата.запись_id == Записи.запись_id
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                Услуги.услуга_id, Услуги.название_услуги
            ).order_by(
                func.sum(Оплата.сумма).desc()
            ).all()
            
        elif report_type == 'employees':
            # Отчет по сотрудникам
            data = db.session.query(
                Сотрудники.имя,
                Сотрудники.фамилия,
                func.count(Записи.запись_id).label('appointments_count'),
                func.sum(Оплата.сумма).label('total_income')
            ).join(
                Записи, Записи.сотрудник_id == Сотрудники.сотрудник_id
            ).join(
                Оплата, Оплата.запись_id == Записи.запись_id
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                Сотрудники.сотрудник_id, Сотрудники.имя, Сотрудники.фамилия
            ).order_by(
                func.sum(Оплата.сумма).desc()
            ).all()
        else:
            flash('Неверный тип отчета')
            return redirect(url_for('reports'))
        
        if not data:
            flash('Нет данных за выбранный период')
            return redirect(url_for('reports'))
        
        return render_template(f'accountant/reports/{report_type}.html',
                             data=data,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        flash(f'Ошибка при формировании отчета: {str(e)}')
        return redirect(url_for('reports'))

@app.route('/accountant/expenses')
@login_required
def expenses():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем параметры фильтрации
    expense_type = request.args.get('type')
    branch_id = request.args.get('branch_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Базовый запрос
    query = Расходы.query
    
    # Применяем фильтры
    if expense_type:
        query = query.filter(Расходы.тип == expense_type)
    if branch_id:
        query = query.filter(Расходы.филиал_id == branch_id)
    if date_from:
        query = query.filter(Расходы.дата >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Расходы.дата <= datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1))
    
    # Получаем отсортированные расходы
    expenses = query.order_by(Расходы.дата.desc()).all()
    
    # Получаем список филиалов для фильтра
    branches = Филиалы.query.all()
    
    return render_template('accountant/expenses.html', 
                         expenses=expenses,
                         branches=branches)

@app.route('/accountant/expenses/add', methods=['POST'])
@login_required
def add_expense():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    try:
        # Создаем новый расход
        expense = Расходы(
            тип=request.form.get('type'),
            сумма=float(request.form.get('amount')),
            дата=datetime.strptime(request.form.get('date'), '%Y-%m-%d'),
            описание=request.form.get('description'),
            филиал_id=request.form.get('branch_id') or None
        )
        
        db.session.add(expense)
        db.session.commit()
        
        flash('Расход успешно добавлен')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении расхода: {str(e)}')
    
    return redirect(url_for('expenses'))

@app.route('/accountant/expenses/edit/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    expense = Расходы.query.get_or_404(expense_id)
    
    try:
        expense.тип = request.form.get('type')
        expense.сумма = float(request.form.get('amount'))
        expense.дата = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        expense.описание = request.form.get('description')
        expense.филиал_id = request.form.get('branch_id') or None
        
        db.session.commit()
        flash('Расход успешно обновлен')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении расхода: {str(e)}')
    
    return redirect(url_for('expenses'))

@app.route('/accountant/expenses/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    expense = Расходы.query.get_or_404(expense_id)
    
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Расход успешно удален')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении расхода: {str(e)}')
    
    return redirect(url_for('expenses'))

@app.route('/accountant/salary')
@login_required
def salary():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    # Получаем всех сотрудников и их статистику за текущий месяц
    today = datetime.now()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    employee_stats = db.session.query(
        Сотрудники.сотрудник_id,
        Сотрудники.имя,
        Сотрудники.фамилия,
        Сотрудники.должность,
        db.func.count(Записи.запись_id).label('appointments_count'),
        db.func.sum(Оплата.сумма).label('total_income')
    ).outerjoin(Записи, Записи.сотрудник_id == Сотрудники.сотрудник_id)\
     .outerjoin(Оплата, Оплата.запись_id == Записи.запись_id)\
     .filter(db.or_(
         Оплата.дата_оплаты >= start_of_month,
         Оплата.дата_оплаты == None
     ))\
     .group_by(Сотрудники.сотрудник_id)\
     .all()
    
    return render_template('accountant/salary.html', 
                         employee_stats=employee_stats,
                         today=today)

@app.route('/accountant/salary/set/<int:employee_id>', methods=['POST'])
@login_required
def set_salary(employee_id):
    if current_user.роль != 'accountant':
        flash('У вас нет прав для выполнения этого действия')
        return redirect(url_for('index'))
    
    try:
        # Получаем данные из формы
        base_salary = float(request.form.get('base_salary', 0))
        commission_percent = int(request.form.get('commission_percent', 0))
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        
        # Закрываем текущую зарплату, если есть
        current_salary = Зарплаты.query.filter_by(
            сотрудник_id=employee_id,
            дата_окончания=None
        ).first()
        
        if current_salary:
            current_salary.дата_окончания = start_date
        
        # Создаем новую запись о зарплате
        new_salary = Зарплаты(
            сотрудник_id=employee_id,
            базовая_ставка=base_salary,
            процент_от_выручки=commission_percent,
            дата_начала=start_date
        )
        
        db.session.add(new_salary)
        db.session.commit()
        
        flash('Зарплата успешно установлена')
    except ValueError:
        flash('Ошибка: проверьте правильность введенных данных')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при установке зарплаты: {str(e)}')
    
    return redirect(url_for('salary'))

@app.route('/accountant/salary/history/<int:employee_id>')
@login_required
def salary_history(employee_id):
    if current_user.роль != 'accountant':
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    employee = Сотрудники.query.get_or_404(employee_id)
    salary_history = Зарплаты.query.filter_by(сотрудник_id=employee_id)\
        .order_by(Зарплаты.дата_начала.desc()).all()
    
    return render_template('accountant/salary_history.html',
                         employee=employee,
                         salary_history=salary_history)

@app.route('/accountant/analytics')
@login_required
def analytics():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    try:
        # Получаем данные за последние 12 месяцев
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Доход по месяцам
        monthly_income = db.session.query(
            func.date_trunc('month', Оплата.дата_оплаты).label('month'),
            func.sum(Оплата.сумма).label('total')
        ).filter(
            Оплата.дата_оплаты.between(start_date, end_date)
        ).group_by(
            'month'
        ).order_by(
            'month'
        ).all()
        
        # Популярные услуги
        popular_services = db.session.query(
            Услуги.название_услуги,
            func.count(Записи.запись_id).label('count'),
            func.sum(Оплата.сумма).label('total')
        ).join(
            Записи, Услуги.услуга_id == Записи.услуга_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).filter(
            Оплата.дата_оплаты.between(start_date, end_date)
        ).group_by(
            Услуги.услуга_id, Услуги.название_услуги
        ).order_by(
            func.count(Записи.запись_id).desc()
        ).limit(5).all()
        
        # Статистика по филиалам
        branch_stats = db.session.query(
            Филиалы.название,
            func.count(Записи.запись_id).label('appointments_count'),
            func.sum(Оплата.сумма).label('total_income')
        ).join(
            Записи, Записи.филиал_id == Филиалы.филиал_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).filter(
            Оплата.дата_оплаты.between(start_date, end_date)
        ).group_by(
            Филиалы.филиал_id, Филиалы.название
        ).all()
        
        return render_template('accountant/analytics.html',
                             monthly_income=monthly_income,
                             popular_services=popular_services,
                             branch_stats=branch_stats)
                             
    except Exception as e:
        flash(f'Ошибка при получении данных: {str(e)}')
        return redirect(url_for('index'))

@app.route('/accountant/analytics/export/excel')
@login_required
def export_analytics_excel():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    try:
        # Получаем те же данные, что и для аналитики
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        monthly_income = db.session.query(
            func.date_trunc('month', Оплата.дата_оплаты).label('month'),
            func.sum(Оплата.сумма).label('total')
        ).filter(
            Оплата.дата_оплаты.between(start_date, end_date)
        ).group_by('month').order_by('month').all()
        
        popular_services = db.session.query(
            Услуги.название_услуги,
            func.count(Записи.запись_id).label('count'),
            func.sum(Оплата.сумма).label('total')
        ).join(
            Записи, Услуги.услуга_id == Записи.услуга_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).group_by(
            Услуги.услуга_id, Услуги.название_услуги
        ).order_by(
            func.count(Записи.запись_id).desc()
        ).limit(5).all()
        
        branch_stats = db.session.query(
            Филиалы.название,
            func.count(Записи.запись_id).label('appointments_count'),
            func.sum(Оплата.сумма).label('total_income')
        ).join(
            Записи, Записи.филиал_id == Филиалы.филиал_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).group_by(
            Филиалы.филиал_id, Филиалы.название
        ).all()

        # Создаем Excel файл
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Форматы для Excel
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4CAF50',
            'color': 'white'
        })
        
        money_format = workbook.add_format({'num_format': '# ##0.00 ₽'})
        
        # Лист с доходами по месяцам
        ws_income = workbook.add_worksheet('Доходы по месяцам')
        ws_income.write(0, 0, 'Месяц', header_format)
        ws_income.write(0, 1, 'Общий доход', header_format)
        
        for idx, (month, total) in enumerate(monthly_income, start=1):
            ws_income.write(idx, 0, month.strftime('%B %Y'))
            ws_income.write(idx, 1, total, money_format)
        
        # Лист с популярными услугами
        ws_services = workbook.add_worksheet('Популярные услуги')
        ws_services.write(0, 0, 'Услуга', header_format)
        ws_services.write(0, 1, 'Количество записей', header_format)
        ws_services.write(0, 2, 'Общий доход', header_format)
        
        for idx, (service, count, total) in enumerate(popular_services, start=1):
            ws_services.write(idx, 0, service)
            ws_services.write(idx, 1, count)
            ws_services.write(idx, 2, total, money_format)
        
        # Лист со статистикой по филиалам
        ws_branches = workbook.add_worksheet('Статистика по филиалам')
        ws_branches.write(0, 0, 'Филиал', header_format)
        ws_branches.write(0, 1, 'Количество записей', header_format)
        ws_branches.write(0, 2, 'Общий доход', header_format)
        
        for idx, (branch, count, total) in enumerate(branch_stats, start=1):
            ws_branches.write(idx, 0, branch)
            ws_branches.write(idx, 1, count)
            ws_branches.write(idx, 2, total, money_format)
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        flash(f'Ошибка при формировании Excel отчета: {str(e)}')
        return redirect(url_for('analytics'))

@app.route('/accountant/analytics/export/pdf')
@login_required
def export_analytics_pdf():
    if current_user.роль not in ['accountant', 'owner']:
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    try:
        # Получаем те же данные, что и для аналитики
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        monthly_income = db.session.query(
            func.date_trunc('month', Оплата.дата_оплаты).label('month'),
            func.sum(Оплата.сумма).label('total')
        ).filter(
            Оплата.дата_оплаты.between(start_date, end_date)
        ).group_by('month').order_by('month').all()
        
        popular_services = db.session.query(
            Услуги.название_услуги,
            func.count(Записи.запись_id).label('count'),
            func.sum(Оплата.сумма).label('total')
        ).join(
            Записи, Услуги.услуга_id == Записи.услуга_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).group_by(
            Услуги.услуга_id, Услуги.название_услуги
        ).order_by(
            func.count(Записи.запись_id).desc()
        ).limit(5).all()
        
        branch_stats = db.session.query(
            Филиалы.название,
            func.count(Записи.запись_id).label('appointments_count'),
            func.sum(Оплата.сумма).label('total_income')
        ).join(
            Записи, Записи.филиал_id == Филиалы.филиал_id
        ).join(
            Оплата, Оплата.запись_id == Записи.запись_id
        ).group_by(
            Филиалы.филиал_id, Филиалы.название
        ).all()

        # Создаем PDF
        output = BytesIO()
        p = canvas.Canvas(output, pagesize=A4)
        width, height = A4
        
        # Заголовок отчета
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Аналитический отчет")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, f"Дата формирования: {datetime.now().strftime('%d.%m.%Y')}")
        
        # Доходы по месяцам
        y = height - 100
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Доходы по месяцам")
        y -= 20
        
        for month, total in monthly_income:
            if y < 50:
                p.showPage()
                y = height - 50
            p.setFont("Helvetica", 12)
            p.drawString(50, y, f"{month.strftime('%B %Y')}: {'{:,.2f}'.format(total)} ₽")
            y -= 20
        
        # Популярные услуги
        y -= 20
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Популярные услуги")
        y -= 20
        
        for service, count, total in popular_services:
            if y < 50:
                p.showPage()
                y = height - 50
            p.setFont("Helvetica", 12)
            p.drawString(50, y, f"{service}: {count} записей, {'{:,.2f}'.format(total)} ₽")
            y -= 20
        
        # Статистика по филиалам
        y -= 20
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Статистика по филиалам")
        y -= 20
        
        for branch, count, total in branch_stats:
            if y < 50:
                p.showPage()
                y = height - 50
            p.setFont("Helvetica", 12)
            p.drawString(50, y, f"{branch}: {count} записей, {'{:,.2f}'.format(total)} ₽")
            y -= 20
        
        p.save()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'analytics_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        )
        
    except Exception as e:
        flash(f'Ошибка при формировании PDF отчета: {str(e)}')
        return redirect(url_for('analytics'))

@app.route('/accountant/reports/quick/<report_type>/<period>')
@login_required
def quick_report(report_type, period):
    if current_user.роль not in ['accountant', 'owner']:  # Добавляем owner
        flash('У вас нет прав для доступа к этой странице')
        return redirect(url_for('index'))
    
    today = datetime.now()
    
    # Определяем даты начала и конца периода
    if period == 'today':
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == 'week':
        start_date = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == 'month':
        start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == 'year':
        start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        flash('Неверный период отчета')
        return redirect(url_for('reports'))

    try:
        if report_type == 'income':
            # Отчет по доходам
            data = db.session.query(
                func.date(Оплата.дата_оплаты).label('date'),
                func.sum(Оплата.сумма).label('total')
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                func.date(Оплата.дата_оплаты)
            ).order_by(
                func.date(Оплата.дата_оплаты)
            ).all()

        elif report_type == 'services':
            # Отчет по услугам
            data = db.session.query(
                Услуги.название_услуги,
                func.count(Записи.запись_id).label('count'),
                func.sum(Оплата.сумма).label('total')
            ).join(
                Записи, Записи.услуга_id == Услуги.услуга_id
            ).join(
                Оплата, Оплата.запись_id == Записи.запись_id
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                Услуги.услуга_id, Услуги.название_услуги
            ).order_by(
                func.sum(Оплата.сумма).desc()
            ).all()

        elif report_type == 'employees':
            # Отчет по сотрудникам
            data = db.session.query(
                Сотрудники.фамилия,
                Сотрудники.имя,
                func.count(Записи.запись_id).label('appointments_count'),
                func.sum(Оплата.сумма).label('total_income')
            ).join(
                Записи, Записи.сотрудник_id == Сотрудники.сотрудник_id
            ).join(
                Оплата, Оплата.запись_id == Записи.запись_id
            ).filter(
                Оплата.дата_оплаты.between(start_date, end_date)
            ).group_by(
                Сотрудники.сотрудник_id, Сотрудники.фамилия, Сотрудники.имя
            ).order_by(
                func.sum(Оплата.сумма).desc()
            ).all()
        else:
            flash('Неверный тип отчета')
            return redirect(url_for('reports'))

        if not data:
            flash('Нет данных за выбранный период')
            return redirect(url_for('reports'))

        return render_template(f'accountant/reports/{report_type}.html',
                             data=data,
                             start_date=start_date,
                             end_date=end_date)
                             
    except Exception as e:
        flash(f'Ошибка при формировании отчета: {str(e)}')
        return redirect(url_for('reports'))

def create_owner_account():
    # Проверяем, существует ли уже аккаунт владельца
    owner = Сотрудники.query.filter_by(логин='owner').first()
    if not owner:
        try:
            # Получаем первый филиал или создаем его
            branch = Филиалы.query.first()
            if not branch:
                branch = Филиалы(
                    название='Главный филиал',
                    адрес='Адрес главного филиала',
                    телефон='+7 (XXX) XXX-XX-XX'
                )
                db.session.add(branch)
                db.session.commit()
            
            # Создаем защищенный аккаунт владельца
            owner = Сотрудники(
                логин='owner',
                имя='Владелец',
                фамилия='Салона',
                должность='Владелец',
                роль='owner',
                дата_приёма=datetime.now(),
                филиал_id=branch.филиал_id
            )
            owner.set_password('owner')  # Установите здесь безопасный пароль
            db.session.add(owner)
            db.session.commit()
            print('Создан защищенный аккаунт владельца')
        except Exception as e:
            db.session.rollback()
            print(f'Ошибка при создании аккаунта владельца: {str(e)}')

@app.before_first_request
def initialize_app():
    create_owner_account()

if __name__ == '__main__':
    with app.app_context():
        # Создаем все таблицы
        db.create_all()
        
        # Создаем филиал, если его нет
        if not Филиалы.query.first():
            main_branch = Филиалы(
                название='Главный филиал',
                адрес='Основной адрес',
                телефон='+7 (999) 123-45-67'
            )
            db.session.add(main_branch)
            db.session.commit()
            main_branch_id = main_branch.филиал_id
        else:
            main_branch_id = Филиалы.query.first().филиал_id

        # Создаем владельца, если его нет
        owner = Сотрудники.query.filter_by(логин='owner').first()
        if not owner:
            owner = Сотрудники(
                филиал_id=main_branch_id,
                логин='owner',
                имя='Owner',
                фамилия='Owner',
                должность='Владелец',
                телефон='+7 (999) 123-45-67',  # Добавляем телефон
                роль='owner',
                дата_приёма=datetime.now().date()
            )
            owner.set_password('owner')
            db.session.add(owner)
            db.session.commit()
            print('Создан аккаунт владельца с логином "owner" и паролем "owner"')

        # Создаем администратора, если его нет
        admin = Сотрудники.query.filter_by(логин='admin').first()
        if not admin:
            admin = Сотрудники(
                филиал_id=main_branch_id,
                логин='admin',
                имя='Admin',
                фамилия='Admin',
                должность='Администратор',
                телефон='+7 (999) 123-45-67',  # Добавляем телефон
                роль='admin',
                дата_приёма=datetime.now().date()
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print('Создан аккаунт администратора с логином "admin" и паролем "admin"')

        # Создаем бухгалтера, если его нет
        accountant = Сотрудники.query.filter_by(логин='accountant').first()
        if not accountant:
            accountant = Сотрудники(
                филиал_id=main_branch_id,
                логин='accountant',
                имя='Accountant',
                фамилия='Accountant',
                должность='Бухгалтер',
                телефон='+7 (999) 123-45-67',  # Добавляем телефон
                роль='accountant',
                дата_приёма=datetime.now().date()
            )
            accountant.set_password('accountant')
            db.session.add(accountant)
            db.session.commit()
            print('Создан аккаунт бухгалтера с логином "accountant" и паролем "accountant"')
        
        # Создаем тестового клиента, если его нет
        test_client = Клиенты.query.filter_by(логин='test').first()
        if not test_client:
            test_client = Клиенты(
                логин='test',
                email='test@example.com',
                телефон='+7 (999) 999-99-99',
                имя='Test',
                фамилия='User',
                отчество='',
                пол='М',
                дата_рождения=datetime.strptime('2000-01-01', '%Y-%m-%d').date(),
                дата_регистрации=datetime.now()
            )
            test_client.set_password('test123')
            db.session.add(test_client)
            print('Создан тестовый клиент с логином "test" и паролем "test123"')
        
        db.session.commit()
    app.run(debug=True)
