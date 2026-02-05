"""
Backfill FEN Positions Script

This script reads existing analyzed games from the database and adds FEN positions
to the mistakes and blunders that don't already have them.

Run from backend directory: python backfill_fen.py
"""

import os
import json
import chess
import chess.pgn
import io
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env")
    exit(1)

engine = create_engine(DATABASE_URL)


def extract_fen_from_pgn(pgn_text: str, move_number: int, is_white: bool) -> str | None:
    """
    Extract the FEN position at a specific move number from a PGN.
    Returns the position BEFORE the move was made.
    """
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if not game:
            return None
        
        board = game.board()
        moves = list(game.mainline_moves())
        
        # Calculate the half-move index
        # move_number=1, white → index 0
        # move_number=1, black → index 1
        # move_number=2, white → index 2
        target_idx = (move_number - 1) * 2 + (0 if is_white else 1)
        
        # Play moves up to (but not including) the target move
        for i, move in enumerate(moves):
            if i == target_idx:
                return board.fen()
            board.push(move)
        
        return None
    except Exception as e:
        print(f"  Error parsing PGN: {e}")
        return None


def backfill_game(game_id: str, pgn: str, result_json: dict) -> dict | None:
    """
    Add FEN positions to mistakes and blunders in the result.
    Returns updated result if changes were made, None otherwise.
    """
    changes_made = False
    
    # Process mistakes
    if 'mistakes' in result_json and result_json['mistakes']:
        for mistake in result_json['mistakes']:
            if 'fen' not in mistake or not mistake['fen']:
                is_white = mistake.get('player', '').lower() == 'white'
                move_num = mistake.get('move_number', 1)
                fen = extract_fen_from_pgn(pgn, move_num, is_white)
                if fen:
                    mistake['fen'] = fen
                    changes_made = True
    
    # Process blunders
    if 'blunders' in result_json and result_json['blunders']:
        for blunder in result_json['blunders']:
            if 'fen' not in blunder or not blunder['fen']:
                is_white = blunder.get('player', '').lower() == 'white'
                move_num = blunder.get('move_number', 1)
                fen = extract_fen_from_pgn(pgn, move_num, is_white)
                if fen:
                    blunder['fen'] = fen
                    changes_made = True
    
    # Process critical moments
    if 'critical_moments' in result_json and result_json['critical_moments']:
        for moment in result_json['critical_moments']:
            if 'position_fen' not in moment or not moment['position_fen']:
                is_white = moment.get('player', '').lower() == 'white'
                move_num = moment.get('move_number', 1)
                fen = extract_fen_from_pgn(pgn, move_num, is_white)
                if fen:
                    moment['position_fen'] = fen
                    changes_made = True
    
    return result_json if changes_made else None


def main():
    print("=== FEN Backfill Script ===\n")
    
    # Fetch all analyzed games with PGN
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT id, pgn, result 
            FROM "GameAnalysis" 
            WHERE pgn IS NOT NULL 
            AND result IS NOT NULL
            AND result::text LIKE '%"status": "analyzed"%'
        '''))
        games = list(result)
    
    print(f"Found {len(games)} analyzed games with PGN\n")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for game_id, pgn, result_json in games:
        try:
            # Parse result JSON if it's a string
            if isinstance(result_json, str):
                result_data = json.loads(result_json)
            else:
                result_data = result_json
            
            # Skip if no mistakes/blunders
            has_content = (
                result_data.get('mistakes') or 
                result_data.get('blunders') or 
                result_data.get('critical_moments')
            )
            if not has_content:
                skipped_count += 1
                continue
            
            # Check if already has FEN data
            already_has_fen = False
            if result_data.get('mistakes'):
                already_has_fen = any(m.get('fen') for m in result_data['mistakes'])
            if not already_has_fen and result_data.get('blunders'):
                already_has_fen = any(b.get('fen') for b in result_data['blunders'])
            
            if already_has_fen:
                skipped_count += 1
                continue
            
            # Backfill FEN positions
            updated_result = backfill_game(game_id, pgn, result_data)
            
            if updated_result:
                # Update database
                with engine.connect() as conn:
                    conn.execute(
                        text('UPDATE "GameAnalysis" SET result = :result WHERE id = :id'),
                        {'result': json.dumps(updated_result), 'id': game_id}
                    )
                    conn.commit()
                
                updated_count += 1
                print(f"✅ Updated game {game_id[:8]}...")
            else:
                skipped_count += 1
                
        except Exception as e:
            error_count += 1
            print(f"❌ Error processing {game_id[:8]}...: {e}")
    
    print(f"\n=== Summary ===")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors:  {error_count}")


if __name__ == "__main__":
    main()
