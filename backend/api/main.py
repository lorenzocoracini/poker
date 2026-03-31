from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import player

app = FastAPI(title='Poker API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],  # Vite default port
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(player.router, prefix='/players', tags=['players'])

@app.get('/')
def root():
    return {'status': 'ok'}