"""Pytest configuration.

Ensures project root is importable and sets safe defaults for environment
variables so Config doesn't raise during test collection.
"""

import os, sys
import pytest

# Provide deterministic secret for tests (NOT for production)
os.environ.setdefault('ALLOW_DEFAULT_SECRET', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('APP_MASTER_KEY', 'dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLTMyYnl0ZXM=')  # Base64 encoded test key

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope='function')
def app():
    """Create and configure a test Flask application."""
    from app import create_app, db
    
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture(scope='function')
def test_user(app):
    """Create a test user in the database."""
    from app.models.user import User
    from app import db
    
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpassword123')
        db.session.add(user)
        db.session.commit()
        
        # Refresh to get ID
        db.session.refresh(user)
        yield user


@pytest.fixture(scope='function')
def test_user2(app):
    """Create a second test user for permission testing."""
    from app.models.user import User
    from app import db
    
    with app.app_context():
        user = User(
            username='testuser2',
            email='test2@example.com',
            first_name='Test2',
            last_name='User2'
        )
        user.set_password('testpassword456')
        db.session.add(user)
        db.session.commit()
        
        # Refresh to get ID
        db.session.refresh(user)
        yield user


@pytest.fixture(scope='function')
def auth_client(client, test_user):
    """Create an authenticated test client."""
    client.post('/login', data={
        'username': 'testuser',
        'password': 'testpassword123'
    }, follow_redirects=True)
    
    return client
