from flask import current_app
from flask_mail import Message, Mail
from threading import Thread

mail = Mail()

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body=None):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    if html_body:
        msg.html = html_body
    
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), msg)).start()

def send_email_confirmation(user):
    subject = "Подтверждение регистрации"
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    recipients = [user.email]
    
    text_body = f'''
Здравствуйте, {user.name}!

Спасибо за регистрацию в нашем салоне красоты.
Ваш аккаунт успешно создан.

С уважением,
Команда салона красоты
'''
    
    html_body = f'''
    <h3>Здравствуйте, {user.name}!</h3>
    <p>Спасибо за регистрацию в нашем салоне красоты.</p>
    <p>Ваш аккаунт успешно создан.</p>
    <br>
    <p>С уважением,<br>
    Команда салона красоты</p>
'''
    
    send_email(subject, sender, recipients, text_body, html_body) 