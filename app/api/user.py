import secrets

import bcrypt
from flask import request
from flask_openapi3 import Tag, APIBlueprint

from app.config import API_PREFIX, API_VERSION
from app.dto.auth import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse
from app.models.database_conn import MyDb
from app.models.kvuno import User, UserToken

__bp__ = "/users"
url_prefix = API_PREFIX + API_VERSION + __bp__

tag = Tag(name='User', description="User management API")

api = APIBlueprint(__bp__, __name__, url_prefix=url_prefix, abp_tags=[tag])


@api.post('/register', responses={201: RegisterResponse, 409: {"description": "Username or email already exists"}})
def register(body: RegisterRequest):
    db = MyDb.get_db()
    existing = db.session.query(User).filter(
        (User.username == body.username) | (User.email == body.email)
    ).first()
    if existing:
        return {"msg": "username or email already exists"}, 409

    password_hash = bcrypt.hashpw(body.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(username=body.username, email=body.email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()
    return {"msg": "registration success"}, 201


@api.post('/login', responses={200: LoginResponse, 401: {"description": "Invalid credentials"}})
def login(body: LoginRequest):
    db = MyDb.get_db()
    user = db.session.query(User).filter(User.username == body.username).first()
    if not user or not bcrypt.checkpw(body.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return {"msg": "invalid credentials"}, 401

    token = secrets.token_hex(32)
    user_token = UserToken(user_id=user.id, token=token)
    db.session.add(user_token)
    db.session.commit()
    return {"msg": "login success", "access_token": token}, 200


def get_current_user():
    """Extract the authenticated user from the request's Authorization header.

    Returns:
        User or None if not authenticated.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.replace('Bearer ', '', 1)
    db = MyDb.get_db()
    token_record = db.session.query(UserToken).filter(UserToken.token == token).first()
    if not token_record:
        return None
    return db.session.query(User).filter(User.id == token_record.user_id).first()
