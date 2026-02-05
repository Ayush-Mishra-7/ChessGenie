"""
Test script for the chess analyzer.
Run with: python test_analyzer.py
"""
import asyncio
from analyzer import analyze_game_sync, find_stockfish

# Sample PGN for testing (short game)
SAMPLE_PGN = """[Event "Test Game"]
[Site "ChessGenie"]
[Date "2024.01.01"]
[White "TestPlayer1"]
[Black "TestPlayer2"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O
9. h3 Na5 10. Bc2 c5 11. d4 Qc7 12. Nbd2 cxd4 13. cxd4 Nc6 14. Nb3 a5 15. Be3 a4
16. Nbd2 Bd7 17. Rc1 Qb7 18. Bb1 Rfc8 19. d5 Nb4 20. Rxc8+ Rxc8 21. a3 Na6
22. Bd3 Nc5 23. Bc2 Qb6 24. Qe2 h6 25. Nh2 Nh7 26. f4 exf4 27. Bxf4 Qxb2
28. Bd1 Nb3 29. Bxb3 axb3 30. Nhf3 Be8 31. Qd3 Bf6 32. e5 dxe5 33. Bxe5 Bxe5
34. Nxe5 Qc3 35. Qxc3 Rxc3 36. Nef3 Nf6 37. Kf2 b2 38. Rb1 Rc2 39. Ke3 Nd7
40. Kd3 Rxd2+ 41. Kxd2 b1=Q 42. Rxb1 Nc5 1-0
"""


def main():
    print("=" * 60)
    print("ChessGenie Analyzer Test")
    print("=" * 60)
    print()
    
    # Check if Stockfish is available
    stockfish_path = find_stockfish()
    if not stockfish_path:
        print("❌ Stockfish not found!")
        print("   Run: python download_stockfish.py")
        return
    
    print(f"✅ Stockfish found at: {stockfish_path}")
    print()
    
    # Run analysis
    print("Analyzing sample game...")
    print("(This may take 30-60 seconds depending on depth)")
    print()
    
    result = analyze_game_sync(SAMPLE_PGN, game_id="test_game", depth=12)
    
    if not result:
        print("❌ Analysis failed!")
        return
    
    # Display results
    print("=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print()
    print(f"Game: {result.white} vs {result.black}")
    print(f"Result: {result.result}")
    print(f"Opening: {result.opening or 'Unknown'}")
    print(f"Total moves: {result.total_moves}")
    print()
    
    print("📊 ACCURACY")
    print(f"   White: {result.accuracy_white}%")
    print(f"   Black: {result.accuracy_black}%")
    print()
    
    if result.blunders:
        print(f"💥 BLUNDERS ({len(result.blunders)})")
        for b in result.blunders[:5]:
            print(f"   Move {b['move_number']}: {b['player']} played {b['played']} (best: {b['best']}, -{b['loss']}cp)")
        print()
    
    if result.mistakes:
        print(f"⚠️  MISTAKES ({len(result.mistakes)})")
        for m in result.mistakes[:5]:
            print(f"   Move {m['move_number']}: {m['player']} played {m['played']} (best: {m['best']}, -{m['loss']}cp)")
        print()
    
    if result.best_moves:
        print(f"⭐ BEST MOVES ({len(result.best_moves)})")
        for bm in result.best_moves[:5]:
            print(f"   Move {bm['move_number']}: {bm['player']} - {bm['move']}")
        print()
    
    if result.critical_moments:
        print(f"🔥 CRITICAL MOMENTS ({len(result.critical_moments)})")
        for cm in result.critical_moments[:3]:
            change = cm['eval_change']
            direction = "↑" if change > 0 else "↓"
            print(f"   Move {cm['move_number']}: {cm['player']} - Eval changed {direction}{abs(change)}cp")
        print()
    
    print("=" * 60)
    print("✅ Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
