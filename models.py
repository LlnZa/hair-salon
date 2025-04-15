from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from time import time
from flask import current_app as app

db = SQLAlchemy()

class Клиенты(db.Model, UserMixin):
    __tablename__ = 'клиенты'
    
    клиент_id = db.Column(db.Integer, primary_key=True)
    логин = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    телефон = db.Column(db.String(20), nullable=False)
    имя = db.Column(db.String(50), nullable=False)
    фамилия = db.Column(db.String(50), nullable=False)
    отчество = db.Column(db.String(50))
    пол = db.Column(db.String(1), nullable=False)
    дата_рождения = db.Column(db.Date, nullable=False)
    дата_регистрации = db.Column(db.DateTime, default=datetime.now)
    пароль_хеш = db.Column(db.String(128))
    записи = db.relationship('Записи', back_populates='клиент', lazy=True)

    # Виртуальное свойство для роли
    @property
    def роль(self):
        return 'client'

    def set_password(self, password):
        self.пароль_хеш = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.пароль_хеш, password)

    # Изменённый метод get_id – теперь с префиксом "client-"
    def get_id(self):
        return f"client-{self.клиент_id}"
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False

    def get_reset_password_token(self, expires_in=3600):
        return jwt.encode(
            {'reset_password': self.клиент_id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                          algorithms=['HS256'])['reset_password']
        except:
            return None
        return Клиенты.query.get(id)

class Филиалы(db.Model):
    __tablename__ = 'филиалы'
    филиал_id = db.Column(db.Integer, primary_key=True)
    название = db.Column(db.String(100), nullable=False)
    адрес = db.Column(db.String(200))
    телефон = db.Column(db.String(20))
    расходы = db.relationship('Расходы', backref='филиал', lazy=True)
    сотрудники = db.relationship('Сотрудники', back_populates='филиал', lazy=True)
    записи = db.relationship('Записи', back_populates='филиал', lazy=True)

class Сотрудники(db.Model, UserMixin):
    __tablename__ = 'сотрудники'
    
    сотрудник_id = db.Column(db.Integer, primary_key=True)
    филиал_id = db.Column(db.Integer, db.ForeignKey('филиалы.филиал_id'), nullable=False)
    фамилия = db.Column(db.String(50), nullable=False)
    имя = db.Column(db.String(50), nullable=False)
    должность = db.Column(db.String(50), nullable=False)
    телефон = db.Column(db.String(20), nullable=False)
    дата_приёма = db.Column(db.Date, nullable=False)
    логин = db.Column(db.String(50), unique=True, nullable=False)
    пароль_хеш = db.Column(db.String(128))
    роль = db.Column(db.String(20), nullable=False, default='employee')
    рейтинг = db.Column(db.Float, default=0.0)
    записи = db.relationship('Записи', back_populates='сотрудник', lazy=True)
    филиал = db.relationship('Филиалы', back_populates='сотрудники')

    def set_password(self, password):
        self.пароль_хеш = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.пароль_хеш, password)

    # Изменённый метод get_id – теперь с префиксом "employee-"
    def get_id(self):
        return f"employee-{self.сотрудник_id}"
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False

class Услуги(db.Model):
    __tablename__ = 'услуги'
    
    услуга_id = db.Column(db.Integer, primary_key=True)
    название_услуги = db.Column(db.String(50), nullable=False)
    описание = db.Column(db.Text)
    базовая_цена = db.Column(db.Numeric(10,2), nullable=False)
    категория_пола = db.Column(db.String(20))
    записи = db.relationship('Записи', back_populates='услуга', lazy=True)
    история_цен = db.relationship('История_цен', back_populates='услуга', lazy=True)

class История_цен(db.Model):
    __tablename__ = 'история_цен'
    
    история_цен_id = db.Column(db.Integer, primary_key=True)
    услуга_id = db.Column(db.Integer, db.ForeignKey('услуги.услуга_id'), nullable=False)
    новая_цена = db.Column(db.Numeric(10,2), nullable=False)
    дата_изменения = db.Column(db.Date, nullable=False)

    услуга = db.relationship('Услуги', back_populates='история_цен')

class Записи(db.Model):
    __tablename__ = 'записи'
    
    запись_id = db.Column(db.Integer, primary_key=True)
    клиент_id = db.Column(db.Integer, db.ForeignKey('клиенты.клиент_id'), nullable=False)
    сотрудник_id = db.Column(db.Integer, db.ForeignKey('сотрудники.сотрудник_id'), nullable=False)
    филиал_id = db.Column(db.Integer, db.ForeignKey('филиалы.филиал_id'), nullable=False)
    услуга_id = db.Column(db.Integer, db.ForeignKey('услуги.услуга_id'), nullable=False)
    дата_визита = db.Column(db.DateTime, nullable=False)
    статус = db.Column(db.String(50))
    примечание = db.Column(db.Text)
    оценка = db.Column(db.Integer)
    отзыв = db.Column(db.Text)

    клиент = db.relationship('Клиенты', back_populates='записи')
    сотрудник = db.relationship('Сотрудники', back_populates='записи')
    филиал = db.relationship('Филиалы', back_populates='записи')
    услуга = db.relationship('Услуги', back_populates='записи')
    оплата_set = db.relationship('Оплата', back_populates='запись')

class Оплата(db.Model):
    __tablename__ = 'оплата'
    
    оплата_id = db.Column(db.Integer, primary_key=True)
    запись_id = db.Column(db.Integer, db.ForeignKey('записи.запись_id'), nullable=False)
    сумма = db.Column(db.Numeric(10,2), nullable=False)
    дата_оплаты = db.Column(db.DateTime)
    способ_оплаты = db.Column(db.String(50))
    статус_оплаты = db.Column(db.String(50))

    запись = db.relationship('Записи', back_populates='оплата_set')

class Расходы(db.Model):
    __tablename__ = 'расходы'
    id = db.Column(db.Integer, primary_key=True)
    тип = db.Column(db.String(50), nullable=False)
    сумма = db.Column(db.Float, nullable=False)
    дата = db.Column(db.Date, nullable=False)
    описание = db.Column(db.Text)
    филиал_id = db.Column(db.Integer, db.ForeignKey('филиалы.филиал_id'), nullable=True)

    def __repr__(self):
        return f'<Расход {self.тип} - {self.сумма}>'

class Зарплаты(db.Model):
    __tablename__ = 'зарплаты'
    
    id = db.Column(db.Integer, primary_key=True)
    сотрудник_id = db.Column(db.Integer, db.ForeignKey('сотрудники.сотрудник_id'), nullable=False)
    базовая_ставка = db.Column(db.Numeric(10,2), nullable=False)
    процент_от_выручки = db.Column(db.Integer, default=0)
    дата_начала = db.Column(db.Date, nullable=False)
    дата_окончания = db.Column(db.Date)
    
    сотрудник = db.relationship('Сотрудники', backref=db.backref('зарплаты_сотрудника', lazy=True))

    def __repr__(self):
        return f'<Зарплата {self.сотрудник.имя}: {self.базовая_ставка}₽ + {self.процент_от_выручки}%>'

