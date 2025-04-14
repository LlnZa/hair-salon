from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Regexp

class AddEmployeeForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    last_name = StringField('Фамилия', validators=[DataRequired()])
    position = StringField('Должность', validators=[DataRequired()])
    branch_id = SelectField('Филиал', coerce=int, validators=[DataRequired()])
    hire_date = DateField('Дата приема', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[DataRequired(), Regexp(r'^\+7\d{10}$', message='Телефон должен быть в формате +7XXXXXXXXXX')])
    submit = SubmitField('Добавить сотрудника') 