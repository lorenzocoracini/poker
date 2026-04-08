from pydantic import BaseModel


class PlayerRegisterSchema(BaseModel):
    name: str
    email: str
    password: str


class PlayerLoginSchema(BaseModel):
    email: str
    password: str

class PlayerResponseSchema(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class PlayerListSchema(BaseModel):
    players: list[PlayerResponseSchema]