from sqlalchemy.orm import Session
from api.models.player_model import Player


class PlayerRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, email: str, password: str) -> Player:
        player = Player(name=name, email=email, password=password)
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        return player

    def get_by_email(self, email: str) -> Player | None:
        return self.db.query(Player).filter(Player.email == email).first()

    def get_by_id(self, player_id: int) -> Player | None:
        return self.db.query(Player).filter(Player.id == player_id).first()

    def get_all(self) -> list[Player]:
        return self.db.query(Player).all()