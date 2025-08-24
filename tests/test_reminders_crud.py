import pytest
from app import app, db
from app.models.user import User
from app.models.reminder import Reminder
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()

@pytest.fixture
def user(client):
    with app.app_context():
        u = User(username='creator', email='c@example.com', first_name='C', last_name='User', monthly_income=0)
        u.password_hash = generate_password_hash('secret')
        db.session.add(u)
        db.session.commit()
        return u.id

def login(client, username, password):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=True)

def test_create_reminder(client, user):
    login(client, 'creator', 'secret')
    due_date = (datetime.utcnow() + timedelta(days=5)).strftime('%Y-%m-%d')
    resp = client.post('/reminders/create', data={
        'title': 'Pago Luz',
        'description': 'Factura mensual',
        'due_date': due_date,
        'amount': '120.50',
        'reminder_type': 'custom'
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        r = Reminder.query.filter_by(title='Pago Luz').first()
        assert r is not None
        assert r.user_id == user


def test_delete_reminder(client, user):
    login(client, 'creator', 'secret')
    with app.app_context():
        r = Reminder(user_id=user, title='Eliminar', reminder_type='custom', due_date=datetime.utcnow()+timedelta(days=2))
        db.session.add(r)
        db.session.commit()
        rid = r.id
    resp = client.post(f'/reminders/{rid}/delete', follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Reminder.query.get(rid) is None
