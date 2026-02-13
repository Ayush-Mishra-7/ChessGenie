"""
Debug script: Analyze a single game and print detailed accuracy info.
Run with: python test_accuracy_debug.py

This helps diagnose WHY accuracy might show 0% by printing
every move's centipawn loss and the final accuracy calculation.
"""
import chess
import chess.pgn
from io import StringIO
from analyzer import analyze_game_sync, find_stockfish, calculate_accuracy


# ── Sample PGN ──────────────────────────────────────────────────
# Replace this with ANY game you want to debug
SAMPLE_PGN = """[Event "Live Chess"]
[Site "Chess.com"]
[Date "2024.01.15"]
[White "PlayerA"]
[Black "PlayerB"]
[Result "0-1"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O
9. h3 Na5 10. Bc2 c5 11. d4 Qc7 12. Nbd2 cxd4 13. cxd4 Nc6 14. Nb3 a5 15. Be3 a4
16. Nbd2 Bd7 17. Rc1 Qb7 18. Bb1 Rfc8 19. d5 Nb4 20. Rxc8+ Rxc8 21. a3 Na6
22. Bd3 Nc5 23. Bc2 Qb6 24. Qe2 h6 25. Nh2 Nh7 26. f4 exf4 27. Bxf4 Qxb2
28. Bd1 Nb3 29. Bxb3 axb3 30. Nhf3 Be8 31. Qd3 Bf6 32. e5 dxe5 33. Bxe5 Bxe5
34. Nxe5 Qc3 35. Qxc3 Rxc3 36. Nef3 Nf6 37. Kf2 b2 38. Rb1 Rc2 39. Ke3 Nd7
40. Kd3 Rxd2+ 41. Kxd2 b1=Q 42. Rxb1 Nc5 0-1
"""


def main():
    print("=" * 70)
    print("ACCURACY DEBUGGING SCRIPT")
    print("=" * 70)
    print()
    
    # Check Stockfish
    sf = find_stockfish()
    if not sf:
        print("❌ Stockfish not found! Run download_stockfish.py first.")
        return
    print(f"✅ Stockfish: {sf}")
    print()
    
    # Analyze
    print("Analyzing game (depth=12, this may take ~60s)...")
    result = analyze_game_sync(SAMPLE_PGN, game_id="debug", depth=12)
    
    if not result:
        print("❌ Analysis returned None - check analyzer.py logs")
        return
    
    # ── Header ──
    print()
    print(f"  White: {result.white}")
    print(f"  Black: {result.black}")
    print(f"  Result: {result.result}")
    print(f"  Total moves: {result.total_moves}")
    print()
    
    # ── Per-move centipawn losses ──
    white_losses = []
    black_losses = []
    
    print("-" * 70)
    print(f"{'Move':<6} {'Player':<8} {'Played':<10} {'Best':<10} {'CP Loss':<10} {'Class':<12} {'Eval Before':<12} {'Eval After':<12}")
    print("-" * 70)
    
    for ma in result.move_analyses:
        player = "White" if ma['is_white'] else "Black"
        cp = ma['centipawn_loss']
        
        if ma['is_white']:
            white_losses.append(cp)
        else:
            black_losses.append(cp)
        
        # Highlight mistakes/blunders
        marker = ""
        if ma['classification'] == 'blunder':
            marker = " 💥"
        elif ma['classification'] == 'mistake':
            marker = " ⚠️"
        elif ma['classification'] == 'best':
            marker = " ⭐"
        
        print(f"{ma['move_number']:<6} {player:<8} {ma['move_san']:<10} {ma['best_move_san']:<10} {cp:<10} {ma['classification']:<12} {ma['eval_before']:<12} {ma['eval_after']:<12}{marker}")
    
    print("-" * 70)
    print()
    
    # ── Accuracy calculation breakdown ──
    print("=" * 70)
    print("ACCURACY CALCULATION BREAKDOWN")
    print("=" * 70)
    print()
    
    print(f"  White centipawn losses ({len(white_losses)} moves):")
    if white_losses:
        print(f"    Values: {white_losses}")
        avg_w = sum(white_losses) / len(white_losses)
        print(f"    Sum: {sum(white_losses)}")
        print(f"    Avg loss: {avg_w:.1f}cp")
        print(f"    Formula: 100 * (1 - {avg_w:.1f}/200) = {100 * (1 - avg_w/200):.1f}%")
        print(f"    Clamped: {max(0.0, min(100.0, 100 * (1 - avg_w/200))):.1f}%")
        print(f"    calculate_accuracy() returns: {calculate_accuracy(white_losses)}%")
    else:
        print(f"    ⚠️ NO WHITE LOSSES - this means no white moves were analyzed!")
        print(f"    calculate_accuracy([]) returns: {calculate_accuracy([])}%")
    
    print()
    
    print(f"  Black centipawn losses ({len(black_losses)} moves):")
    if black_losses:
        print(f"    Values: {black_losses}")
        avg_b = sum(black_losses) / len(black_losses)
        print(f"    Sum: {sum(black_losses)}")
        print(f"    Avg loss: {avg_b:.1f}cp")
        print(f"    Formula: 100 * (1 - {avg_b:.1f}/200) = {100 * (1 - avg_b/200):.1f}%")
        print(f"    Clamped: {max(0.0, min(100.0, 100 * (1 - avg_b/200))):.1f}%")
        print(f"    calculate_accuracy() returns: {calculate_accuracy(black_losses)}%")
    else:
        print(f"    ⚠️ NO BLACK LOSSES - this means no black moves were analyzed!")
        print(f"    calculate_accuracy([]) returns: {calculate_accuracy([])}%")
    
    print()
    print("=" * 70)
    print(f"  FINAL: White accuracy = {result.accuracy_white}%")
    print(f"  FINAL: Black accuracy = {result.accuracy_black}%")
    print("=" * 70)
    
    # ── Check for 0% issues ──
    if result.accuracy_white == 0.0 or result.accuracy_black == 0.0:
        print()
        print("⚠️  0% ACCURACY DETECTED!")
        print("  Possible causes:")
        if white_losses and sum(white_losses) / len(white_losses) >= 200:
            print("  → White's avg loss >= 200cp (very poor play, formula yields 0%)")
        if black_losses and sum(black_losses) / len(black_losses) >= 200:
            print("  → Black's avg loss >= 200cp (very poor play, formula yields 0%)")
        if not white_losses:
            print("  → No white losses collected (PGN parsing issue?)")
        if not black_losses:
            print("  → No black losses collected (PGN parsing issue?)")
        
        # Check for mate-score outliers
        for losses, name in [(white_losses, "White"), (black_losses, "Black")]:
            outliers = [l for l in losses if l > 1000]
            if outliers:
                print(f"  → {name} has {len(outliers)} extreme losses (>1000cp): {outliers}")
                print(f"    These are likely mate score conversions inflating the average.")
                print(f"    Without outliers: avg = {sum(l for l in losses if l <= 1000) / max(1, len([l for l in losses if l <= 1000])):.1f}cp")
    
    print()
    print("✅ Debug complete.")


if __name__ == "__main__":
    main()
