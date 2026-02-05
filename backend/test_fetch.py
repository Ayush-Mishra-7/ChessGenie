"""
Quick test script to verify game fetching works.
Run with: python test_fetch.py
"""
import asyncio
from game_fetcher import fetch_lichess_games, fetch_chesscom_games

async def main():
    print("=" * 50)
    print("Testing Lichess API (DrNykterstein = Magnus Carlsen)")
    print("=" * 50)
    
    try:
        lichess_games = await fetch_lichess_games("DrNykterstein", limit=3)
        print(f"✅ Fetched {len(lichess_games)} games from Lichess")
        
        if lichess_games:
            game = lichess_games[0]
            print(f"   First game: {game.white} vs {game.black} ({game.result})")
            print(f"   Opening: {game.opening}")
            print(f"   PGN preview: {game.pgn[:100]}...")
    except Exception as e:
        print(f"❌ Lichess fetch failed: {e}")
    
    print()
    print("=" * 50)
    print("Testing Chess.com API (MagnusCarlsen)")
    print("=" * 50)
    
    try:
        chesscom_games = await fetch_chesscom_games("MagnusCarlsen", limit=3)
        print(f"✅ Fetched {len(chesscom_games)} games from Chess.com")
        
        if chesscom_games:
            game = chesscom_games[0]
            print(f"   First game: {game.white} vs {game.black} ({game.result})")
            print(f"   Opening: {game.opening}")
            print(f"   PGN preview: {game.pgn[:100]}...")
    except Exception as e:
        print(f"❌ Chess.com fetch failed: {e}")
    
    print()
    print("=" * 50)
    print("Tests complete!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
