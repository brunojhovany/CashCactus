"""Pytest configuration.

Ensures project root is importable and sets safe defaults for environment
variables so Config doesn't raise during test collection.
"""

import os, sys

# Provide deterministic secret for tests (NOT for production)
os.environ.setdefault('ALLOW_DEFAULT_SECRET', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
