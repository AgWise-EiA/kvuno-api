from flask_openapi3 import Tag, APIBlueprint

from app.config import API_PREFIX, API_VERSION
from app.dto.auth import RegisterRequest, RegisterResponse, LoginRequest, LoginResponse

__bp__ = "/users"
url_prefix = API_PREFIX + API_VERSION + __bp__

tag = Tag(name='User', description="User management API")

api = APIBlueprint(__bp__, __name__, url_prefix=url_prefix, abp_tags=[tag])


@api.post('/register', responses={201: RegisterResponse})
def register(body: RegisterRequest):
    return {"msg": "registration success"}, 201


@api.post('/login', responses={200: LoginResponse})
def login(body: LoginRequest):
    return {"msg": "login success"}, 200
