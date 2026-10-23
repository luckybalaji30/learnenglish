import importlib
import io
import os

import pytest
from werkzeug.security import check_password_hash


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-only-not-a-production-secret-0123456789")
    monkeypatch.setenv("DEV_INSECURE_COOKIES", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db"))
    monkeypatch.setenv("WORDS_ROOT", str(tmp_path / "words"))
    import quiz
    module = importlib.reload(quiz)
    module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with module.app.app_context():
        module.db.create_all()
    yield module
    with module.app.app_context():
        module.db.session.remove()


def signup(client, username="alice", password="correct-horse-battery-staple"):
    return client.post("/register", data={"username": username, "password": password})


def login(client, username="alice", password="correct-horse-battery-staple"):
    return client.post("/login", data={"username": username, "password": password})


def test_passwords_are_hashed_and_login_works(app_module):
    client = app_module.app.test_client()
    assert signup(client).status_code == 302
    with app_module.app.app_context():
        user = app_module.Users.query.filter_by(username="alice").one()
        assert user.password != "correct-horse-battery-staple"
        assert check_password_hash(user.password, "correct-horse-battery-staple")
    assert login(client, password="wrong").status_code == 200
    assert login(client).status_code == 302
    assert client.get("/mainpage").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/mainpage").status_code == 302


@pytest.mark.parametrize("url", ["/mainpage", "/upload", "/refresh", "/quiz", "/spell", "/misspelled"])
def test_get_routes_require_login(app_module, url):
    response = app_module.app.test_client().get(url)
    assert response.status_code == 302
    assert "/login" in response.location


@pytest.mark.parametrize("url", ["/uploadsubmit", "/quiz_answer", "/spell_answer", "/logout"])
def test_post_routes_require_login(app_module, url):
    response = app_module.app.test_client().post(url)
    assert response.status_code == 302


def test_user_word_banks_are_isolated(app_module):
    alice = app_module.app.test_client()
    bob = app_module.app.test_client()
    signup(alice)
    signup(bob, "bob")
    login(alice)
    login(bob, "bob")
    source = b"Word,Meaning\napple,fruit\nbird,animal\nblue,color\nrun,move\n"
    response = alice.post("/uploadsubmit", data={"file": (io.BytesIO(source), "words.csv")}, content_type="multipart/form-data")
    assert response.status_code == 200
    assert b"4 entries" in alice.get("/mainpage").data
    assert b"Upload a Word/Meaning CSV" in bob.get("/mainpage").data
    assert bob.get("/quiz").status_code == 302
    assert alice.get("/quiz").status_code == 200
    assert bob.post("/quiz_answer").status_code == 400


def test_csrf_required_in_normal_configuration(app_module):
    app_module.app.config["WTF_CSRF_ENABLED"] = True
    client = app_module.app.test_client()
    assert client.post("/register", data={"username": "eve", "password": "very-long-password"}).status_code == 400
