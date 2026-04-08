from api.repositories.player_repository import PlayerRepository
from api.schemas.player_schema import PlayerRegisterSchema
from sqlalchemy.orm import Session

class PlayerRegisterUseCase:
    def __init__(self, db: Session):
        self.repository = PlayerRepository(db)

    def execute(self, payload: PlayerRegisterSchema):
        existing = self.repository.get_by_email(payload.email)
        if existing:
            raise ValueError('Email já cadastrado.')

        # todo -> encrypt

        player = self.repository.create(
            name=payload.name,
            email=payload.email,
            password=payload.password
        )

        return player

class PlayerGetAllUseCase:
    def __init__(self, db: Session):
        self.repository = PlayerRepository(db)

    def execute(self):
        players = self.repository.get_all()
        return players