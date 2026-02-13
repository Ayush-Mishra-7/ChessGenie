"""
Position Generator - Structural Perturbation Algorithm

Given a FEN position where a mistake/blunder was made, generates ~10 similar
practice positions that preserve the same tactical motif.

Algorithm:
1. Extract the "mistake pattern" - identify core vs peripheral pieces
2. Apply controlled perturbations (mirror, shift, swap, noise, remove)
3. Validate legality + Stockfish quick-check to confirm tactic is preserved
4. Return top N diverse, valid positions
"""

import chess
import chess.engine
import copy
import random
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path

logger = logging.getLogger(__name__)

ENGINES_DIR = Path(__file__).parent / "engines"
VERIFY_DEPTH = 8  # Quick Stockfish check depth


@dataclass
class MistakePattern:
    """Extracted pattern from a mistake position."""
    fen: str
    best_move_uci: str
    played_move_uci: str
    moving_piece_square: int        # Square the best-move piece sits on
    moving_piece_type: int          # chess.PAWN, chess.KNIGHT, etc.
    target_square: int              # Where the best move goes
    core_squares: Set[int]          # Squares critical to the tactic
    peripheral_squares: Set[int]    # Squares with non-critical pieces
    side_to_move: bool              # chess.WHITE or chess.BLACK
    

@dataclass 
class GeneratedPosition:
    """A generated practice position."""
    fen: str
    correct_move_uci: str
    correct_move_san: str
    difficulty: str          # "easy", "medium", "hard"
    method: str              # Which perturbation created this
    eval_change: int         # Centipawn change if wrong move played


def find_stockfish() -> Optional[Path]:
    """Find Stockfish executable."""
    if not ENGINES_DIR.exists():
        return None
    patterns = ["stockfish*.exe", "stockfish*"]
    for pattern in patterns:
        for match in ENGINES_DIR.glob(pattern):
            if match.is_file() and match.suffix not in [".zip", ".tar"]:
                return match
    return None


def extract_mistake_pattern(
    fen: str, 
    played_uci: str, 
    best_uci: str
) -> Optional[MistakePattern]:
    """
    Analyze the position to identify which pieces are 'core' to the tactic
    and which are 'peripheral' (can be safely moved/removed).
    
    Core pieces: the moving piece, pieces attacking/defending the target square,
    and pieces that create the tactical motif (pins, forks, etc.)
    
    Peripheral pieces: everything else.
    """
    try:
        board = chess.Board(fen)
        best_move = chess.Move.from_uci(best_uci)
        
        if best_move not in board.legal_moves:
            logger.warning(f"Best move {best_uci} is not legal in position {fen}")
            return None
        
        moving_sq = best_move.from_square
        target_sq = best_move.to_square
        moving_piece = board.piece_at(moving_sq)
        
        if not moving_piece:
            return None
        
        side = board.turn
        
        # Build the set of "core" squares - pieces critical to the tactic
        core_squares = set()
        
        # 1. The moving piece and its target
        core_squares.add(moving_sq)
        core_squares.add(target_sq)
        
        # 2. Both kings (always core - can't remove/move them freely)
        core_squares.add(board.king(chess.WHITE))
        core_squares.add(board.king(chess.BLACK))
        
        # 3. Pieces that attack the target square (defenders and supporters)
        core_squares.update(board.attackers(chess.WHITE, target_sq))
        core_squares.update(board.attackers(chess.BLACK, target_sq))
        
        # 4. Pieces that attack the moving piece's square (they constrain it)
        core_squares.update(board.attackers(chess.WHITE, moving_sq))
        core_squares.update(board.attackers(chess.BLACK, moving_sq))
        
        # 5. If the best move is a discovered attack, find the piece being unblocked
        #    After the best move, check if new attacks appear from the moving piece's file/rank/diagonal
        test_board = board.copy()
        test_board.push(best_move)
        # Squares now attacked by the moving side that weren't before
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == side and sq != moving_sq:
                # Check if this piece gains new attacks after the move
                old_attacks = board.attacks(sq)
                new_attacks = test_board.attacks(sq)
                gained = new_attacks & ~old_attacks
                if gained:
                    # This piece benefits from the discovered attack
                    core_squares.add(sq)
                    core_squares.update(gained & test_board.occupied_co[not side])
        
        # 6. Pieces on the same rank/file/diagonal as a pin/skewer line
        _add_pin_pieces(board, side, core_squares)
        
        # Build peripheral squares - all occupied squares NOT in core
        peripheral_squares = set()
        for sq in chess.SQUARES:
            if board.piece_at(sq) and sq not in core_squares:
                peripheral_squares.add(sq)
        
        return MistakePattern(
            fen=fen,
            best_move_uci=best_uci,
            played_move_uci=played_uci,
            moving_piece_square=moving_sq,
            moving_piece_type=moving_piece.piece_type,
            target_square=target_sq,
            core_squares=core_squares,
            peripheral_squares=peripheral_squares,
            side_to_move=side
        )
        
    except Exception as e:
        logger.error(f"Failed to extract pattern: {e}")
        return None


def _add_pin_pieces(board: chess.Board, side: bool, core_squares: Set[int]):
    """Add pieces involved in pins/skewers to the core set."""
    opponent = not side
    king_sq = board.king(opponent)
    if king_sq is None:
        return
    
    # Check all sliding pieces (bishops, rooks, queens) of the moving side
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != side:
            continue
        if piece.piece_type not in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
            continue
        
        # Check if there's a line between this piece and the opponent's king
        # with exactly one piece in between (a pin)
        between = chess.between(sq, king_sq)
        if not between:
            continue
            
        blockers = between & board.occupied
        if chess.popcount(blockers) == 1:
            # There's exactly one piece between - it's pinned
            pinned_sq = chess.lsb(blockers)
            core_squares.add(sq)       # The pinner
            core_squares.add(pinned_sq) # The pinned piece


# ============================================================
# PERTURBATION FUNCTIONS
# Each takes a board and pattern, returns a new board or None
# ============================================================

def _mirror_horizontal(board: chess.Board) -> Optional[chess.Board]:
    """
    Mirror the position horizontally (a<->h files).
    Preserves tactical geometry but changes coordinates.
    """
    new_board = chess.Board(None)
    new_board.turn = board.turn
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            rank = chess.square_rank(sq)
            file = 7 - chess.square_file(sq)  # Mirror file
            new_sq = chess.square(file, rank)
            new_board.set_piece_at(new_sq, piece)
    
    # Mirror castling rights
    cr = 0
    if board.has_kingside_castling_rights(chess.WHITE):
        cr |= chess.BB_A1  # Kingside becomes queenside after mirror... 
    if board.has_queenside_castling_rights(chess.WHITE):
        cr |= chess.BB_H1
    if board.has_kingside_castling_rights(chess.BLACK):
        cr |= chess.BB_A8
    if board.has_queenside_castling_rights(chess.BLACK):
        cr |= chess.BB_H8
    # Simpler: just clear castling for generated positions
    new_board.set_castling_fen("-")
    
    new_board.ep_square = None
    
    return new_board if _validate_board(new_board) else None


def _mirror_vertical(board: chess.Board) -> Optional[chess.Board]:
    """
    Mirror vertically (ranks 1<->8) and swap colors.
    This is a full color-swap transformation.
    """
    new_board = chess.Board(None)
    new_board.turn = not board.turn
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            rank = 7 - chess.square_rank(sq)  # Mirror rank
            file = chess.square_file(sq)
            new_sq = chess.square(file, rank)
            # Swap piece color
            new_piece = chess.Piece(piece.piece_type, not piece.color)
            new_board.set_piece_at(new_sq, new_piece)
    
    new_board.set_castling_fen("-")
    new_board.ep_square = None
    
    return new_board if _validate_board(new_board) else None


def _shift_position(board: chess.Board, delta_file: int, delta_rank: int) -> Optional[chess.Board]:
    """
    Shift all pieces by (delta_file, delta_rank).
    If any piece goes off-board, return None.
    """
    new_board = chess.Board(None)
    new_board.turn = board.turn
    
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            new_file = chess.square_file(sq) + delta_file
            new_rank = chess.square_rank(sq) + delta_rank
            
            if not (0 <= new_file <= 7 and 0 <= new_rank <= 7):
                return None  # Off-board
            
            new_sq = chess.square(new_file, new_rank)
            
            # Pawns can't be on ranks 0 or 7
            if piece.piece_type == chess.PAWN and new_rank in [0, 7]:
                return None
                
            new_board.set_piece_at(new_sq, piece)
    
    new_board.set_castling_fen("-")
    new_board.ep_square = None
    
    return new_board if _validate_board(new_board) else None


def _remove_peripheral(
    board: chess.Board, 
    pattern: MistakePattern, 
    count: int = 1
) -> Optional[chess.Board]:
    """
    Remove 1-2 peripheral pieces (equal from both sides when possible).
    Creates a cleaner, more puzzle-like position.
    """
    new_board = board.copy()
    peripheral = list(pattern.peripheral_squares)
    
    if len(peripheral) < count:
        return None
    
    random.shuffle(peripheral)
    removed = 0
    
    for sq in peripheral:
        piece = new_board.piece_at(sq)
        if piece and piece.piece_type != chess.KING:
            new_board.remove_piece_at(sq)
            removed += 1
            if removed >= count:
                break
    
    if removed == 0:
        return None
    
    new_board.set_castling_fen("-")
    return new_board if _validate_board(new_board) else None


def _swap_peripheral_piece(
    board: chess.Board, 
    pattern: MistakePattern
) -> Optional[chess.Board]:
    """
    Swap a peripheral piece for a different piece type.
    E.g., change a non-critical bishop to a knight.
    """
    new_board = board.copy()
    peripheral = list(pattern.peripheral_squares)
    
    if not peripheral:
        return None
    
    random.shuffle(peripheral)
    
    for sq in peripheral:
        piece = new_board.piece_at(sq)
        if piece and piece.piece_type not in [chess.KING, chess.PAWN]:
            # Swap to a different minor/major piece
            swappable = [chess.KNIGHT, chess.BISHOP, chess.ROOK]
            options = [p for p in swappable if p != piece.piece_type]
            if options:
                new_piece = chess.Piece(random.choice(options), piece.color)
                new_board.set_piece_at(sq, new_piece)
                if _validate_board(new_board):
                    return new_board
    
    return None


def _add_pawn_noise(
    board: chess.Board, 
    pattern: MistakePattern
) -> Optional[chess.Board]:
    """
    Add or shift 1-2 pawns in non-critical areas.
    Creates visual noise without changing the tactic.
    """
    new_board = board.copy()
    
    # Find empty squares not in core that could hold a pawn
    candidates = []
    for sq in chess.SQUARES:
        if sq in pattern.core_squares:
            continue
        if new_board.piece_at(sq):
            continue
        rank = chess.square_rank(sq)
        if rank in [0, 7]:  # Pawns can't be on first/last rank
            continue
        candidates.append(sq)
    
    if not candidates:
        return None
    
    random.shuffle(candidates)
    
    # Add a pawn for a random side
    color = random.choice([chess.WHITE, chess.BLACK])
    sq = candidates[0]
    
    # Don't put more than one pawn per file for the same side
    file = chess.square_file(sq)
    same_file_pawns = sum(
        1 for r in range(8) 
        if new_board.piece_at(chess.square(file, r)) 
        and new_board.piece_at(chess.square(file, r)).piece_type == chess.PAWN
        and new_board.piece_at(chess.square(file, r)).color == color
    )
    if same_file_pawns >= 1:
        # Try next candidate
        if len(candidates) > 1:
            sq = candidates[1]
        else:
            return None
    
    new_board.set_piece_at(sq, chess.Piece(chess.PAWN, color))
    
    return new_board if _validate_board(new_board) else None


def _move_peripheral_piece(
    board: chess.Board,
    pattern: MistakePattern
) -> Optional[chess.Board]:
    """
    Move a peripheral piece to a different (non-core) square.
    The piece stays on the board but changes location.
    """
    new_board = board.copy()
    peripheral = list(pattern.peripheral_squares)
    
    if not peripheral:
        return None
    
    random.shuffle(peripheral)
    
    for sq in peripheral:
        piece = new_board.piece_at(sq)
        if not piece or piece.piece_type == chess.KING:
            continue
        
        # Find a valid destination
        empty_non_core = [
            s for s in chess.SQUARES
            if not new_board.piece_at(s) 
            and s not in pattern.core_squares
            and s != sq
        ]
        
        if piece.piece_type == chess.PAWN:
            empty_non_core = [
                s for s in empty_non_core
                if chess.square_rank(s) not in [0, 7]
            ]
        
        if empty_non_core:
            dest = random.choice(empty_non_core)
            new_board.remove_piece_at(sq)
            new_board.set_piece_at(dest, piece)
            new_board.set_castling_fen("-")
            if _validate_board(new_board):
                return new_board
            else:
                # Undo
                new_board = board.copy()
    
    return None


# ============================================================
# VALIDATION
# ============================================================

def _validate_board(board: chess.Board) -> bool:
    """
    Check if a board position is legal.
    """
    try:
        # Must have exactly one king per side
        white_kings = len(board.pieces(chess.KING, chess.WHITE))
        black_kings = len(board.pieces(chess.KING, chess.BLACK))
        if white_kings != 1 or black_kings != 1:
            return False
        
        # No pawns on rank 1 or 8
        for sq in list(board.pieces(chess.PAWN, chess.WHITE)) + list(board.pieces(chess.PAWN, chess.BLACK)):
            rank = chess.square_rank(sq)
            if rank in [0, 7]:
                return False
        
        # The side NOT to move must not be in check
        # (i.e., the previous move can't have left the mover in check)
        board_copy = board.copy()
        board_copy.turn = not board.turn
        if board_copy.is_check():
            return False
        
        # Board must be valid enough to have legal moves
        if not any(board.legal_moves):
            return False  # Stalemate/checkmate isn't useful for practice
            
        return True
        
    except Exception:
        return False


def _stockfish_verify(
    board: chess.Board,
    expected_move_type: int,    # Piece type of the expected moving piece
    expected_target: Optional[int],  # Expected target square (can be mirrored)
    original_best_uci: str,
    depth: int = VERIFY_DEPTH
) -> Optional[Tuple[str, str, int]]:
    """
    Quick Stockfish check to see if the position has a clear best move
    that involves a similar tactical idea.
    
    Returns (best_move_uci, best_move_san, eval_advantage) or None.
    """
    stockfish_path = find_stockfish()
    if not stockfish_path:
        return None
    
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(stockfish_path))
        try:
            # Analyze to find the best move
            result = engine.analyse(board, chess.engine.Limit(depth=depth))
            
            pv = result.get("pv", [])
            if not pv:
                return None
            
            best_move = pv[0]
            best_piece = board.piece_at(best_move.from_square)
            
            if not best_piece:
                return None
            
            # Get evaluation
            score = result.get("score")
            if score:
                pov = score.white() if board.turn == chess.WHITE else score.black()
                if pov.is_mate():
                    cp_advantage = 10000
                else:
                    cp_advantage = pov.score() or 0
            else:
                cp_advantage = 0
            
            # The position has a clear best move (significant advantage)
            if cp_advantage < 50:  # Less than 0.5 pawn advantage
                return None
            
            best_san = board.san(best_move)
            return (best_move.uci(), best_san, cp_advantage)
            
        finally:
            engine.quit()
            
    except Exception as e:
        logger.error(f"Stockfish verification failed: {e}")
        return None


def _get_difficulty(eval_advantage: int) -> str:
    """Classify difficulty based on eval advantage."""
    if eval_advantage >= 500:
        return "easy"
    elif eval_advantage >= 200:
        return "medium"
    else:
        return "hard"


def _mirror_uci(uci: str) -> str:
    """Mirror a UCI move horizontally (a<->h)."""
    def mirror_sq(s):
        file = chr(ord('a') + 7 - (ord(s[0]) - ord('a')))
        return file + s[1]
    
    from_sq = mirror_sq(uci[0:2])
    to_sq = mirror_sq(uci[2:4])
    promo = uci[4:] if len(uci) > 4 else ""
    return from_sq + to_sq + promo


def _shift_uci(uci: str, delta_file: int, delta_rank: int) -> Optional[str]:
    """Shift a UCI move by the given delta."""
    def shift_sq(s):
        new_file = ord(s[0]) - ord('a') + delta_file
        new_rank = int(s[1]) - 1 + delta_rank
        if not (0 <= new_file <= 7 and 0 <= new_rank <= 7):
            return None
        return chr(ord('a') + new_file) + str(new_rank + 1)
    
    from_sq = shift_sq(uci[0:2])
    to_sq = shift_sq(uci[2:4])
    if from_sq is None or to_sq is None:
        return None
    promo = uci[4:] if len(uci) > 4 else ""
    return from_sq + to_sq + promo


def _vertical_mirror_uci(uci: str) -> str:
    """Mirror a UCI move vertically (rank 1<->8)."""
    def mirror_sq(s):
        new_rank = 9 - int(s[1])
        return s[0] + str(new_rank)
    
    from_sq = mirror_sq(uci[0:2])
    to_sq = mirror_sq(uci[2:4])
    promo = uci[4:] if len(uci) > 4 else ""
    return from_sq + to_sq + promo


# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_similar_positions(
    fen: str,
    played_uci: str,
    best_uci: str,
    count: int = 10,
    use_stockfish: bool = True
) -> List[GeneratedPosition]:
    """
    Generate similar practice positions from a mistake/blunder FEN.
    
    Args:
        fen: FEN string of the position BEFORE the mistake
        played_uci: The move that was played (the mistake)
        best_uci: The best move that should have been played
        count: Number of positions to generate (default 10)
        use_stockfish: Whether to verify with Stockfish
    
    Returns:
        List of GeneratedPosition objects
    """
    pattern = extract_mistake_pattern(fen, played_uci, best_uci)
    if not pattern:
        logger.error(f"Could not extract pattern from FEN: {fen}")
        return []
    
    board = chess.Board(fen)
    best_move = chess.Move.from_uci(best_uci)
    moving_piece = board.piece_at(best_move.from_square)
    
    candidates = []
    seen_fens = {fen}  # Avoid duplicates
    
    # Define perturbation strategies with their methods
    strategies = [
        ("mirror_h", lambda: _mirror_horizontal(board)),
        ("mirror_v", lambda: _mirror_vertical(board)),
        ("shift_+1f", lambda: _shift_position(board, 1, 0)),
        ("shift_-1f", lambda: _shift_position(board, -1, 0)),
        ("shift_+1r", lambda: _shift_position(board, 0, 1)),
        ("shift_-1r", lambda: _shift_position(board, 0, -1)),
        ("shift_+1+1", lambda: _shift_position(board, 1, 1)),
        ("shift_-1-1", lambda: _shift_position(board, -1, -1)),
        ("shift_+1-1", lambda: _shift_position(board, 1, -1)),
        ("shift_-1+1", lambda: _shift_position(board, -1, 1)),
        ("remove_1", lambda: _remove_peripheral(board, pattern, 1)),
        ("remove_2", lambda: _remove_peripheral(board, pattern, 2)),
        ("remove_3", lambda: _remove_peripheral(board, pattern, 3)),
        ("swap_piece", lambda: _swap_peripheral_piece(board, pattern)),
        ("pawn_noise", lambda: _add_pawn_noise(board, pattern)),
        ("move_piece", lambda: _move_peripheral_piece(board, pattern)),
    ]
    
    # Also combine strategies for more variety
    combined_strategies = [
        ("mirror_h+remove", lambda: _chain(_mirror_horizontal(board), 
                                            lambda b, p: _remove_peripheral(b, p, 1))),
        ("shift+swap", lambda: _chain(_shift_position(board, 1, 0),
                                       lambda b, p: _swap_peripheral_piece(b, p))),
        ("remove+noise", lambda: _chain(_remove_peripheral(board, pattern, 1),
                                         lambda b, p: _add_pawn_noise(b, p))),
        ("remove+move", lambda: _chain(_remove_peripheral(board, pattern, 2),
                                        lambda b, p: _move_peripheral_piece(b, p))),
    ]
    
    all_strategies = strategies + combined_strategies
    
    # Try each strategy multiple times (with randomness)
    max_attempts = count * 5  # Try more than we need
    attempt = 0
    
    for strategy_name, strategy_fn in all_strategies:
        if len(candidates) >= count * 2:  # Collect extra for diversity filtering
            break
            
        # Try each strategy a few times (random perturbations differ each time)
        for _ in range(3):
            if attempt >= max_attempts:
                break
            attempt += 1
            
            try:
                new_board = strategy_fn()
                if new_board is None:
                    continue
                
                new_fen = new_board.fen()
                if new_fen in seen_fens:
                    continue
                seen_fens.add(new_fen)
                
                if use_stockfish:
                    # Determine the expected move coordinates based on transformation
                    result = _stockfish_verify(
                        new_board,
                        moving_piece.piece_type if moving_piece else chess.PAWN,
                        None,
                        best_uci
                    )
                    
                    if result:
                        move_uci, move_san, eval_adv = result
                        candidates.append(GeneratedPosition(
                            fen=new_fen,
                            correct_move_uci=move_uci,
                            correct_move_san=move_san,
                            difficulty=_get_difficulty(eval_adv),
                            method=strategy_name,
                            eval_change=eval_adv
                        ))
                else:
                    # Without Stockfish, just return valid positions
                    # Try to find any strong-looking move
                    candidates.append(GeneratedPosition(
                        fen=new_fen,
                        correct_move_uci="",
                        correct_move_san="",
                        difficulty="unknown",
                        method=strategy_name,
                        eval_change=0
                    ))
                    
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
                continue
    
    # Sort by diversity and quality
    # Prefer positions from different strategies, then by eval advantage
    seen_methods = set()
    diverse_results = []
    other_results = []
    
    for pos in candidates:
        if pos.method not in seen_methods:
            diverse_results.append(pos)
            seen_methods.add(pos.method)
        else:
            other_results.append(pos)
    
    # Combine: diverse first, then fill with others
    final = diverse_results + other_results
    
    # Sort by eval (stronger tactics first)
    final.sort(key=lambda p: -p.eval_change)
    
    return final[:count]


def _chain(board: Optional[chess.Board], fn) -> Optional[chess.Board]:
    """Chain two perturbation functions. fn should accept (board, pattern)."""
    if board is None:
        return None
    try:
        # Create an approximate pattern for the intermediate board
        # All occupied squares become peripheral (no core constraint)
        pattern = MistakePattern(
            fen=board.fen(),
            best_move_uci="",
            played_move_uci="",
            moving_piece_square=0,
            moving_piece_type=chess.PAWN,
            target_square=0,
            core_squares=set(),
            peripheral_squares={sq for sq in chess.SQUARES if board.piece_at(sq)},
            side_to_move=board.turn
        )
        return fn(board, pattern) if callable(fn) else None
    except Exception:
        return None


# For convenience: convert results to dicts
def positions_to_dicts(positions: List[GeneratedPosition]) -> List[Dict]:
    """Convert list of GeneratedPosition to list of dicts."""
    return [asdict(p) for p in positions]
