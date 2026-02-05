"""Debug script to check if FEN is stored correctly."""
import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    result = conn.execute(text('SELECT id, result FROM "GameAnalysis" WHERE result IS NOT NULL LIMIT 3'))
    for row in result:
        game_id = row[0][:12]
        data = row[1]
        
        print(f"\n=== Game {game_id} ===")
        
        if isinstance(data, str):
            data = json.loads(data)
        
        blunders = data.get('blunders', [])
        mistakes = data.get('mistakes', [])
        
        print(f"Blunders: {len(blunders)}")
        for b in blunders[:2]:
            fen = b.get('fen', 'NO FEN')
            print(f"  Move {b.get('move_number')}: fen={fen[:30] if fen != 'NO FEN' else 'NO FEN'}...")
        
        print(f"Mistakes: {len(mistakes)}")
        for m in mistakes[:2]:
            fen = m.get('fen', 'NO FEN')
            print(f"  Move {m.get('move_number')}: fen={fen[:30] if fen != 'NO FEN' else 'NO FEN'}...")
