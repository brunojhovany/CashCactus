import pytest
from app import app, db
from app.models.user import User
from app.models.reminder import Reminder
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()

@pytest.fixture
def user1(client):
    with app.app_context():
        u = User(username='user1', email='u1@example.com', first_name='U1', last_name='Test', monthly_income=0)
        u.password_hash = generate_password_hash('pass1')
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def user2(client):
    with app.app_context():
        u = User(username='user2', email='u2@example.com', first_name='U2', last_name='Test', monthly_income=0)
        u.password_hash = generate_password_hash('pass2')
        db.session.add(u)
        db.session.commit()
        return u.id

@pytest.fixture
def reminder_user1(client, user1):
    from datetime import datetime
    with app.app_context():
        r = Reminder(user_id=user1, title='Privado', reminder_type='custom', due_date=datetime(2030, 1, 1))
        db.session.add(r)
        db.session.commit()
        return r.id

def login(client, username, password):
    return client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=True)

def test_cannot_access_other_user_reminder_edit(client, user1, user2, reminder_user1):
    login(client, 'user2', 'pass2')
    resp = client.get(f'/reminders/{reminder_user1}/edit')
    assert resp.status_code == 404

def test_cannot_complete_other_user_reminder(client, user1, user2, reminder_user1):
    login(client, 'user2', 'pass2')
    resp = client.post(f'/reminders/{reminder_user1}/complete')
    # Should 404 due to ownership enforcement
    assert resp.status_code == 404

def test_owner_can_edit_and_complete(client, user1, reminder_user1):
    login(client, 'user1', 'pass1')
    resp = client.get(f'/reminders/{reminder_user1}/edit')
    assert resp.status_code == 200
    resp2 = client.post(f'/reminders/{reminder_user1}/complete')
    assert resp2.status_code in (302, 200)
