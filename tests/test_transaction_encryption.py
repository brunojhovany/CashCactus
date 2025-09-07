import base64
from app import app, db
from app.models.user import User
from app.models.transaction import Transaction
from werkzeug.security import generate_password_hash
from app.services.transaction_search import find_by_description, find_by_notes


def _ensure_master_key():
    import os
    if 'APP_MASTER_KEY' not in os.environ:
        os.environ['APP_MASTER_KEY'] = base64.b64encode(b'A' * 32).decode()


def test_transaction_encrypted_fields(tmp_path):
    _ensure_master_key()
    app.config['TESTING'] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
        u = User(
            username='encuser',
            email='e@example.com',
            first_name='E',
            last_name='User',
            monthly_income=0
        )
        u.password_hash = generate_password_hash('pass')
        db.session.add(u)
        db.session.commit()

        t = Transaction(user_id=u.id, amount=10.5, category='other', transaction_type='expense')
        t.description = 'Compra Mercado'
        t.notes = 'Lista básica'
        db.session.add(t)
        db.session.commit()

        stored = Transaction.query.get(t.id)
        assert stored.description == 'Compra Mercado'
        assert stored.notes == 'Lista básica'
        assert stored.description_enc is not None and b'Compra Mercado' not in stored.description_enc
        assert stored.notes_enc is not None and 'Lista básica'.encode('utf-8') not in stored.notes_enc
        assert len(stored.description_bidx) == 64
        assert len(stored.notes_bidx) == 64

    # Búsquedas por blind index (requiere contexto app)
    with app.app_context():
        by_desc = find_by_description(u.id, 'Compra Mercado')
        assert len(by_desc) == 1 and by_desc[0].id == stored.id
        by_notes = find_by_notes(u.id, 'Lista básica')
        assert len(by_notes) == 1
