import pytest
import bcrypt

from utils import login_workflow


class FakeDB:
    def __init__(self, username, password):
        # store hashed password
        self._username = username
        self._hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def username_in_use(self, username):
        return username == self._username

    def fetch_password_hash_for_username(self, username):
        if username == self._username:
            return self._hash
        return None

    def fetch_user_by_username(self, username):
        if username == self._username:
            return {"id": 42, "username": username, "email": "test@example.com"}
        return None


@pytest.mark.asyncio
async def test_login_returns_user_id_on_success():
    db = FakeDB("alice", "Secret123!")
    class FakeForm(dict):
        def get(self, k):
            return super().get(k)

    form = FakeForm({"username": "alice", "password": "Secret123!"})
    status, info = await login_workflow(form, db)
    assert status == 0
    assert info == 42
