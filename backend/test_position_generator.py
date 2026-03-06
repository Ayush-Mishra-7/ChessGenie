"""
Test script for the position generator.
Run with: python test_position_generator.py

Tests the structural perturbation algorithm against known tactical positions.
"""
import time
import chess
from position_generator import (
    generate_similar_positions,
    generate_similar_positions_mvp,
    extract_mistake_pattern,
    positions_to_dicts,
    find_stockfish
)


# Known tactical positions for testing
# Format: (description, fen, played_uci (mistake), best_uci)
TEST_POSITIONS = [
    (
        "Knight fork on f7 (fork king and rook)",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "d2d3",       # A passive developing move (mistake)
        "h5f7",       # Qxf7# (Scholar's mate - actually checkmate!)
    ),
    (
        "Back rank weakness",
        "6k1/5ppp/8/8/8/8/5PPP/1r2R1K1 w - - 0 1",
        "e1e2",       # Moving the rook away (mistake)
        "e1b1",       # Rxb1 - capturing the rook
    ),
    (
        "Undefended piece - knight hanging",
        "r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 2",
        "d7d6",       # A normal move (not the worst)
        "d7d5",       # d5 - challenging the center
    ),
    (
        "Discovered attack - bishop uncovers rook",
        "r2qk2r/ppp2ppp/2n1bn2/3pp3/2B1P1b1/2NP1N2/PPP2PPP/R1BQ1RK1 w kq - 0 7",
        "h2h3",       # h3 kicking the bishop (decent but not best)
        "c4d5",       # Bxd5 winning a pawn
    ),
]


def print_board(fen: str, label: str = ""):
    """Print a chess board from FEN in ASCII."""
    board = chess.Board(fen)
    if label:
        print(f"  {label}")
    print(f"  FEN: {fen}")
    # Print board with coordinates
    board_str = str(board)
    lines = board_str.split('\n')
    for i, line in enumerate(lines):
        print(f"  {8-i} {line}")
    print("    a b c d e f g h")
    print()


def main():
    print("=" * 70)
    print("ChessGenie Position Generator Test")
    print("=" * 70)
    print()

    # Check Stockfish
    stockfish = find_stockfish()
    use_sf = stockfish is not None
    if use_sf:
        print(f"✅ Stockfish found at: {stockfish}")
    else:
        print("⚠️  Stockfish not found - positions won't be verified")
        print("   Generated positions may not preserve the tactic")
    print()

    total_generated = 0
    total_time = 0

    for desc, fen, played_uci, best_uci in TEST_POSITIONS:
        print("=" * 70)
        print(f"📋 {desc}")
        print("=" * 70)
        print()
        
        # Show original position
        print_board(fen, "ORIGINAL POSITION (before mistake)")
        print(f"  ❌ Played: {played_uci}")
        print(f"  ✅ Best:   {best_uci}")
        print()
        
        # Extract pattern
        pattern = extract_mistake_pattern(fen, played_uci, best_uci)
        if pattern:
            print(f"  📊 Pattern Analysis:")
            print(f"     Core squares:       {len(pattern.core_squares)}")
            print(f"     Peripheral squares: {len(pattern.peripheral_squares)}")
            print(f"     Moving piece type:  {chess.piece_name(pattern.moving_piece_type)}")
            print(f"     Side to move:       {'White' if pattern.side_to_move else 'Black'}")
            print()
        
        # Generate positions
        print(f"  🔄 Generating similar positions...")
        start = time.time()
        positions = generate_similar_positions(
            fen, played_uci, best_uci, 
            count=10, 
            use_stockfish=use_sf
        )
        elapsed = time.time() - start
        total_time += elapsed
        
        print(f"  ⏱️  Generated {len(positions)} positions in {elapsed:.1f}s")
        print()
        
        if not positions:
            print("  ⚠️  No positions generated!")
            print()
            continue
        
        total_generated += len(positions)
        
        for i, pos in enumerate(positions):
            print(f"  --- Position {i+1}/{len(positions)} [{pos.method}] ---")
            print_board(pos.fen, f"Difficulty: {pos.difficulty} | Eval: +{pos.eval_change}cp")
            if pos.correct_move_san:
                print(f"  ✅ Correct move: {pos.correct_move_san} ({pos.correct_move_uci})")
            print()

        print("  🧪 MVP response preview...")
        mvp = generate_similar_positions_mvp(
            fen,
            played_uci,
            best_uci,
            count=3,
            difficulty=None,
            use_stockfish=use_sf,
            timeout_seconds=6.0,
            seed=7
        )
        for item in mvp.get("generated", []):
            print(
                f"     -> {item['generation_method']} | score={item.get('quality_score')} | "
                f"gap={item.get('eval_gap_cp')} | wrong={item.get('wrong_move_san')}"
            )
        print()
        
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Test positions:     {len(TEST_POSITIONS)}")
    print(f"  Total generated:    {total_generated}")
    print(f"  Total time:         {total_time:.1f}s")
    print(f"  Avg per position:   {total_time/len(TEST_POSITIONS):.1f}s")
    if use_sf:
        print(f"  Stockfish verified: ✅")
    else:
        print(f"  Stockfish verified: ❌ (not available)")
    print()


if __name__ == "__main__":
    main()
