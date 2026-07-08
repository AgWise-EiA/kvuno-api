
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., description="Desired username", examples=["johndoe"])
    email: str = Field(..., description="Email address", examples=["john@example.com"])
    password: str = Field(..., description="Password", examples=["securePass123"])


class RegisterResponse(BaseModel):
    msg: str = Field(..., description="Registration result message", examples=["registration success"])


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username", examples=["johndoe"])
    password: str = Field(..., description="Password", examples=["securePass123"])


class LoginResponse(BaseModel):
    msg: str = Field(..., description="Login result message", examples=["login success"])
