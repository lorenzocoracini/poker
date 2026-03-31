from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from api.database import get_db
from api import models

router = APIRouter()

class PlayerCreate(BaseModel):
    name: str

@router.post('/')
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(name=player.name)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

@router.get('/')
def list_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()