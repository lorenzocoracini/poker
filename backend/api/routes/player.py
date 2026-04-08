from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.database import get_db
from api.schemas.player_schema import PlayerRegisterSchema, PlayerResponseSchema, PlayerListSchema
from api.usecases.player_usecase import PlayerRegisterUseCase, PlayerGetAllUseCase

router = APIRouter()

db_dependency = Depends(get_db)


@router.post('/register', response_model=PlayerResponseSchema)
def register(payload: PlayerRegisterSchema, db: Session = db_dependency):
    try:
        player = PlayerRegisterUseCase(db).execute(payload)
        return player
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/', response_model=PlayerListSchema)
def get_all(db: Session = db_dependency):
    players = PlayerGetAllUseCase(db).execute()
    return {'players': players}