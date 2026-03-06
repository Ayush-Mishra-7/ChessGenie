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
import time
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Set, Any
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
    motifs: List[str]               # Detected tactical motifs (fork, pin, etc.)
    

@dataclass 
class GeneratedPosition:
    """A generated practice position."""
    fen: str
    correct_move_uci: str
    correct_move_san: str
    difficulty: str          # "easy", "medium", "hard"
    method: str              # Which perturbation created this
    eval_change: int         # Centipawn change if wrong move played
    motifs: List[str]        # Tactical motifs present in this position


@dataclass
class TacticalRole:
    """Represents a tactical role in a source position."""
    name: str
    square: int
    piece_type: int
    color: bool


@dataclass
class RoleRelation:
    """Directed relation between tactical roles."""
    source: str
    relation: str
    target: str


@dataclass
class RoleGraph:
    """Compact graph-like tactical representation."""
    roles: List[TacticalRole]
    relations: List[RoleRelation]


@dataclass
class SourceTacticalProfile:
    """Serialized source profile for the API response."""
    fen: str
    motifs: List[str]
    core_squares: List[str]
    peripheral_squares: List[str]
    role_graph: Dict[str, Any]


@dataclass
class CandidateScore:
    """Detailed tactical quality evaluation for a generated candidate."""
    best_move_uci: str
    best_move_san: str
    wrong_move_uci: str
    wrong_move_san: str
    best_eval_cp: int
    wrong_eval_cp: int
    eval_gap_cp: int
    motifs: List[str]
    motif_match: float
    line_stability: float
    human_plausibility: float
    composite_score: float
    line_stable: bool
    explanation_short: str
    explanation_best: str
    explanation_wrong: str


def _log_generation_event(level: int, event: str, **fields: Any):
    """Emit structured generation logs as a single JSON payload."""
    payload = {"event": event, **fields}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))


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


def detect_motifs(board: chess.Board, best_move: chess.Move, pv: List[chess.Move] = None) -> List[str]:
    """Detect tactical motifs in a position."""
    motifs = []
    
    # If we have PV, use it to check future boards
    full_sequence = [best_move]
    if pv and len(pv) > 1:
        full_sequence = pv
    
    # 1. Check for Sacrifice (best move captures a piece, but then we lose material for a mate/win)
    # Or simply: we play a move that seems to lose material but leads to a forced win.
    moving_piece = board.piece_at(best_move.from_square)
    if moving_piece:
        test_board = board.copy()
        test_board.push(best_move)
        
        # Simple sacrifice check: move a piece to a square where it can be captured by a lower-value piece
        # and it's actually captured in the PV.
        if len(full_sequence) > 1:
            next_move = full_sequence[1]
            if board.piece_at(next_move.to_square) == moving_piece:
                # Our piece was captured!
                captured_by = board.piece_at(next_move.from_square)
                if captured_by:
                    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
                    if values.get(moving_piece.piece_type, 0) > values.get(captured_by.piece_type, 0):
                        motifs.append("sacrifice")

    # 2. Check for Mate in the sequence
    final_board = board.copy()
    for move in full_sequence:
        final_board.push(move)
    
    if final_board.is_checkmate():
        motifs.append("mate-threat")
        # Check if it's a smothered mate
        enemy_king = final_board.king(not board.turn)
        is_smothered = True
        for sq in final_board.attacks(enemy_king):
            p = final_board.piece_at(sq)
            if not p or p.color == board.turn:
                is_smothered = False
                break
        if is_smothered:
            motifs.append("smothered-mate")
            
        # Check if it's a back-rank mate
        rank = chess.square_rank(enemy_king)
        if rank in [0, 7]:
            # King on back rank
            # Check if blocked by own pawns in the final position
            file = chess.square_file(enemy_king)
            blocked_count = 0
            for f in range(max(0, file-1), min(8, file+2)):
                r = 1 if rank == 0 else 6
                blocking_pawn = final_board.piece_at(chess.square(f, r))
                if blocking_pawn and blocking_pawn.piece_type == chess.PAWN and blocking_pawn.color == (not board.turn):
                    blocked_count += 1
            if blocked_count >= 2:
                motifs.append("back-rank")

    # 3. Check for Fork
    # A fork is when a piece attacks two or more pieces of greater value, or the king.
    test_board = board.copy()
    test_board.push(best_move)
    attacks = test_board.attacks(best_move.to_square)
    attacked_pieces = []
    for sq in attacks:
        p = test_board.piece_at(sq)
        if p and p.color != board.turn:
            attacked_pieces.append(p)
    
    has_king = any(p.piece_type == chess.KING for p in attacked_pieces)
    valuable = [p for p in attacked_pieces if p.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]]
    
    if (has_king and len(valuable) >= 1) or len(valuable) >= 2:
        motifs.append("fork")

    # 4. Pin/Skewer
    core_temp = set()
    _add_pin_pieces(board, board.turn, core_temp)
    if core_temp:
        motifs.append("pin/skewer")

    return list(set(motifs))


def extract_mistake_pattern(
    fen: str, 
    played_uci: str, 
    best_uci: str,
    depth: int = VERIFY_DEPTH
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
        
        # 0. Get PV for motif detection and importance tracing
        pv = []
        stockfish_path = find_stockfish()
        if stockfish_path:
            try:
                with chess.engine.SimpleEngine.popen_uci(str(stockfish_path)) as engine:
                    res = engine.analyse(board, chess.engine.Limit(depth=depth))
                    pv = res.get("pv", [])
            except:
                pass
        
        # 1. The moving piece and its target
        core_squares.add(moving_sq)
        core_squares.add(target_sq)
        
        # 2. Both kings (always core)
        core_squares.add(board.king(chess.WHITE))
        core_squares.add(board.king(chess.BLACK))
        
        # 3. PV pieces - any piece that moves or is captured in the PV is core
        temp_board = board.copy()
        for move in pv[:4]: # Trace first 4 moves
            core_squares.add(move.from_square)
            core_squares.add(move.to_square)
            # Defenders of squares in PV
            core_squares.update(board.attackers(chess.WHITE, move.to_square))
            core_squares.update(board.attackers(chess.BLACK, move.to_square))
            temp_board.push(move)
        
        # 4. Pieces that attack the target square
        core_squares.update(board.attackers(chess.WHITE, target_sq))
        core_squares.update(board.attackers(chess.BLACK, target_sq))
        
        # 5. Pieces that attack the moving piece's square
        core_squares.update(board.attackers(chess.WHITE, moving_sq))
        core_squares.update(board.attackers(chess.BLACK, moving_sq))
        
        # 6. Discovered attacks
        test_board = board.copy()
        test_board.push(best_move)
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == side and sq != moving_sq:
                old_attacks = board.attacks(sq)
                new_attacks = test_board.attacks(sq)
                gained = new_attacks & ~old_attacks
                if gained:
                    core_squares.add(sq)
                    core_squares.update(gained & test_board.occupied_co[not side])
        
        # 7. Pins/Skewers
        _add_pin_pieces(board, side, core_squares)

        # 8. Motif detection
        motifs = detect_motifs(board, best_move, pv)
        
        # 9. Special handling for certain motifs
        if "smothered-mate" in motifs:
            enemy_king = board.king(not side)
            for sq in board.attacks(enemy_king):
                p = board.piece_at(sq)
                if p and p.color != side:
                    core_squares.add(sq)
        
        if "back-rank" in motifs:
            enemy_king = board.king(not side)
            rank = chess.square_rank(enemy_king)
            file = chess.square_file(enemy_king)
            for f in range(max(0, file-1), min(8, file+2)):
                r = 1 if rank == 0 else 6
                sq = chess.square(f, r)
                if board.piece_at(sq):
                    core_squares.add(sq)

        # Build peripheral squares
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
            side_to_move=side,
            motifs=motifs
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
) -> Optional[Tuple[str, str, int, List[str]]]:
    """
    Quick Stockfish check to see if the position has a clear best move
    that involves a similar tactical idea.
    
    Returns (best_move_uci, best_move_san, eval_advantage, motifs) or None.
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
            
            # Detect motifs in the new position
            motifs = detect_motifs(board, best_move)
            
            best_san = board.san(best_move)
            return (best_move.uci(), best_san, cp_advantage, motifs)
            
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
    role_graph = _build_role_graph(board, pattern)
    
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
                        move_uci, move_san, eval_adv, motifs = result
                        candidates.append(GeneratedPosition(
                            fen=new_fen,
                            correct_move_uci=move_uci,
                            correct_move_san=move_san,
                            difficulty=_get_difficulty(eval_adv),
                            method=strategy_name,
                            eval_change=eval_adv,
                            motifs=motifs
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
                        eval_change=0,
                        motifs=pattern.motifs
                    ))
                    
            except Exception as e:
                logger.debug(f"Strategy {strategy_name} failed: {e}")
                continue

    for strategy_name, reembedded_board in _generate_reembedded_boards(board, pattern, role_graph):
        if len(candidates) >= count * 2:
            break

        new_fen = reembedded_board.fen()
        if new_fen in seen_fens:
            continue
        seen_fens.add(new_fen)

        if use_stockfish:
            result = _stockfish_verify(
                reembedded_board,
                moving_piece.piece_type if moving_piece else chess.PAWN,
                None,
                best_uci
            )
            if not result:
                continue

            move_uci, move_san, eval_adv, motifs = result
            candidates.append(GeneratedPosition(
                fen=new_fen,
                correct_move_uci=move_uci,
                correct_move_san=move_san,
                difficulty=_get_difficulty(eval_adv),
                method=strategy_name,
                eval_change=eval_adv,
                motifs=motifs
            ))
        else:
            candidates.append(GeneratedPosition(
                fen=new_fen,
                correct_move_uci="",
                correct_move_san="",
                difficulty="unknown",
                method=strategy_name,
                eval_change=0,
                motifs=pattern.motifs
            ))
    
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
            side_to_move=board.turn,
            motifs=[]
        )
        return fn(board, pattern) if callable(fn) else None
    except Exception:
        return None


def _square_name_list(squares: Set[int]) -> List[str]:
    """Convert a square set into sorted SAN-like coordinate names."""
    return sorted(chess.square_name(sq) for sq in squares)


def _build_role_graph(board: chess.Board, pattern: MistakePattern) -> RoleGraph:
    """Build a lightweight tactical role graph from extracted pattern data."""
    roles: List[TacticalRole] = []
    relations: List[RoleRelation] = []
    added_roles: Set[str] = set()

    def add_role(name: str, square: int, piece_type: int, color: bool):
        if square is None or name in added_roles:
            return
        if any(existing.square == square for existing in roles):
            return
        roles.append(TacticalRole(
            name=name,
            square=square,
            piece_type=piece_type,
            color=color
        ))
        added_roles.add(name)

    moving_sq = pattern.moving_piece_square
    target_sq = pattern.target_square
    moving_piece = board.piece_at(moving_sq)

    if moving_piece:
        add_role("attacker", moving_sq, moving_piece.piece_type, moving_piece.color)

    target_piece = board.piece_at(target_sq)
    if target_piece:
        add_role("target", target_sq, target_piece.piece_type, target_piece.color)
    else:
        add_role("target_square", target_sq, 0, board.turn)

    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is not None:
        add_role("white_king", white_king, chess.KING, chess.WHITE)
    if black_king is not None:
        add_role("black_king", black_king, chess.KING, chess.BLACK)

    if moving_piece:
        opponent_king_sq = board.king(not moving_piece.color)
        opponent_king_name = "black_king" if moving_piece.color == chess.WHITE else "white_king"
        if opponent_king_sq is not None:
            add_role("king_safety_context", opponent_king_sq, chess.KING, not moving_piece.color)

        relations.append(RoleRelation("attacker", "moves_to", "target" if target_piece else "target_square"))
        relations.append(RoleRelation("attacker", "attacks", "target" if target_piece else "target_square"))

        if opponent_king_sq is not None:
            relations.append(RoleRelation("attacker", "pressures", "king_safety_context" if "king_safety_context" in added_roles else opponent_king_name))

        enemy_attackers = sorted(board.attackers(not moving_piece.color, target_sq))
        for idx, defender_sq in enumerate(enemy_attackers[:2]):
            defender_piece = board.piece_at(defender_sq)
            if not defender_piece:
                continue

            defender_name = "defender_primary" if idx == 0 else "defender_secondary"
            add_role(defender_name, defender_sq, defender_piece.piece_type, defender_piece.color)
            relations.append(RoleRelation(defender_name, "defends", "target" if target_piece else "target_square"))

        if opponent_king_sq is not None:
            between = chess.between(moving_sq, opponent_king_sq)
            blockers = sorted(chess.SquareSet(between & board.occupied))
            if blockers:
                blocker_sq = blockers[0]
                blocker_piece = board.piece_at(blocker_sq)
                if blocker_piece:
                    add_role("critical_blocker", blocker_sq, blocker_piece.piece_type, blocker_piece.color)
                    relations.append(RoleRelation("critical_blocker", "blocks", "king_safety_context" if "king_safety_context" in added_roles else opponent_king_name))

            for pinned_sq in sorted(pattern.core_squares):
                if pinned_sq in {moving_sq, target_sq}:
                    continue
                pinned_piece = board.piece_at(pinned_sq)
                if not pinned_piece or pinned_piece.color == moving_piece.color:
                    continue
                if board.is_pinned(pinned_piece.color, pinned_sq):
                    add_role("pinned_piece", pinned_sq, pinned_piece.piece_type, pinned_piece.color)
                    relations.append(RoleRelation("attacker", "pins", "pinned_piece"))
                    break

    return RoleGraph(roles=roles, relations=relations)


def _serialize_role_graph(role_graph: RoleGraph) -> Dict[str, Any]:
    """Serialize role graph with human-readable square names."""
    serialized_roles = []
    for role in role_graph.roles:
        serialized_roles.append({
            "name": role.name,
            "square": chess.square_name(role.square),
            "piece_type": role.piece_type,
            "color": "white" if role.color == chess.WHITE else "black"
        })

    serialized_relations = [asdict(rel) for rel in role_graph.relations]
    return {
        "roles": serialized_roles,
        "relations": serialized_relations
    }


def _board_signature(board: chess.Board) -> str:
    """Get a compact board signature for novelty comparisons."""
    chars = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        chars.append(piece.symbol() if piece else ".")
    chars.append("w" if board.turn == chess.WHITE else "b")
    return "".join(chars)


def _novelty_score(source_board: chess.Board, candidate_board: chess.Board) -> float:
    """Compute a normalized novelty score against source board in [0, 1]."""
    src = _board_signature(source_board)
    cand = _board_signature(candidate_board)
    if len(src) != len(cand):
        return 1.0
    diff = sum(1 for a, b in zip(src, cand) if a != b)
    return round(diff / len(src), 3)


def _square_delta(from_sq: int, to_sq: int) -> Tuple[int, int]:
    """Return file/rank delta from one square to another."""
    return (
        chess.square_file(to_sq) - chess.square_file(from_sq),
        chess.square_rank(to_sq) - chess.square_rank(from_sq),
    )


def _apply_delta(square: int, delta_file: int, delta_rank: int) -> Optional[int]:
    """Apply a file/rank delta to a square and return the new square if on board."""
    new_file = chess.square_file(square) + delta_file
    new_rank = chess.square_rank(square) + delta_rank
    if not (0 <= new_file <= 7 and 0 <= new_rank <= 7):
        return None
    return chess.square(new_file, new_rank)


def _transform_vector(delta: Tuple[int, int], variant: str) -> Tuple[int, int]:
    """Transform a relative vector for role-graph re-embedding."""
    df, dr = delta
    if variant == "mirror_h":
        return (-df, dr)
    if variant == "mirror_v":
        return (df, -dr)
    if variant == "rotate_180":
        return (-df, -dr)
    return (df, dr)


def _is_valid_piece_square(piece_type: int, square: int) -> bool:
    """Check basic square validity for a piece type."""
    if square is None:
        return False
    if piece_type == 0:
        return True
    if piece_type == chess.PAWN and chess.square_rank(square) in {0, 7}:
        return False
    return True


def _vector_geometry(delta: Tuple[int, int]) -> str:
    """Classify the geometry of a relative vector."""
    df, dr = delta
    adf, adr = abs(df), abs(dr)
    if df == 0 or dr == 0:
        return "orthogonal"
    if adf == adr:
        return "diagonal"
    if sorted((adf, adr)) == [1, 2]:
        return "knight"
    return "other"


def _compatible_role_piece_types(role: TacticalRole, delta: Tuple[int, int]) -> List[int]:
    """Return geometry-compatible piece substitutions for a tactical role."""
    if role.name in {"attacker", "target", "white_king", "black_king", "king_safety_context", "pinned_piece"}:
        return [role.piece_type]

    geometry = _vector_geometry(delta)
    if role.piece_type in {chess.BISHOP, chess.ROOK, chess.QUEEN}:
        if geometry == "diagonal":
            return [chess.BISHOP, chess.QUEEN]
        if geometry == "orthogonal":
            return [chess.ROOK, chess.QUEEN]
    return [role.piece_type]


def _nearby_squares(square: int, radius: int = 2) -> List[int]:
    """Enumerate nearby squares ordered from closest to furthest."""
    candidates: List[Tuple[int, int]] = []
    base_file = chess.square_file(square)
    base_rank = chess.square_rank(square)

    for file_delta in range(-radius, radius + 1):
        for rank_delta in range(-radius, radius + 1):
            if file_delta == 0 and rank_delta == 0:
                continue
            new_file = base_file + file_delta
            new_rank = base_rank + rank_delta
            if not (0 <= new_file <= 7 and 0 <= new_rank <= 7):
                continue
            dist = abs(file_delta) + abs(rank_delta)
            candidates.append((dist, chess.square(new_file, new_rank)))

    candidates.sort(key=lambda item: item[0])
    return [sq for _, sq in candidates]


def _place_piece_with_fallback(
    new_board: chess.Board,
    piece: chess.Piece,
    preferred_squares: List[Optional[int]],
    reserved_squares: Set[int],
    required: bool
) -> bool:
    """Place a piece on the first available valid square from the preference list."""
    seen: Set[int] = set()

    for square in preferred_squares:
        if square is None or square in seen:
            continue
        seen.add(square)
        if square in reserved_squares or new_board.piece_at(square):
            continue
        if not _is_valid_piece_square(piece.piece_type, square):
            continue
        new_board.set_piece_at(square, piece)
        return True

    return not required


def _generate_reembedded_boards(
    board: chess.Board,
    pattern: MistakePattern,
    role_graph: RoleGraph,
    attempts: int = 24
) -> List[Tuple[str, chess.Board]]:
    """Lightweight constraint solver that re-embeds role pieces while refilling support material."""
    role_lookup = {role.name: role for role in role_graph.roles}
    attacker = role_lookup.get("attacker")
    if attacker is None:
        return []

    role_squares = {role.square for role in role_graph.roles if role.piece_type != 0}
    target_square_role = role_lookup.get("target_square")

    non_role_entries: List[Tuple[int, chess.Piece, bool]] = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or square in role_squares:
            continue
        non_role_entries.append((square, piece, square in pattern.core_squares))

    raw_vectors = {
        role.name: _square_delta(attacker.square, role.square)
        for role in role_graph.roles
    }

    variants = ["identity", "mirror_h", "mirror_v", "rotate_180"]
    generated: List[Tuple[str, chess.Board]] = []
    seen_fens: Set[str] = set()

    for variant in variants:
        transformed_vectors = {
            name: _transform_vector(delta, variant)
            for name, delta in raw_vectors.items()
        }
        candidate_anchors = list(chess.SQUARES)
        random.shuffle(candidate_anchors)

        produced_for_variant = 0
        for anchor_square in candidate_anchors:
            if produced_for_variant >= max(2, attempts // len(variants)):
                break

            if not _is_valid_piece_square(attacker.piece_type, anchor_square):
                continue

            placement_map: Dict[str, int] = {}
            collision = False
            for role in role_graph.roles:
                if role.name == "attacker":
                    square = anchor_square
                else:
                    delta_file, delta_rank = transformed_vectors[role.name]
                    square = _apply_delta(anchor_square, delta_file, delta_rank)
                if square is None or not _is_valid_piece_square(role.piece_type, square):
                    collision = True
                    break
                if square in placement_map.values():
                    collision = True
                    break
                placement_map[role.name] = square

            if collision:
                continue

            new_board = chess.Board(None)
            new_board.turn = board.turn
            reserved_empty: Set[int] = set()

            if target_square_role is not None:
                reserved_empty.add(placement_map[target_square_role.name])

            role_failed = False
            for role in role_graph.roles:
                square = placement_map[role.name]
                if role.piece_type == 0:
                    reserved_empty.add(square)
                    continue

                piece_types = _compatible_role_piece_types(role, transformed_vectors[role.name])
                piece_type = random.choice(piece_types) if len(piece_types) > 1 else piece_types[0]
                piece = chess.Piece(piece_type, role.color)

                if square in reserved_empty and role.name != "target":
                    role_failed = True
                    break

                if new_board.piece_at(square):
                    role_failed = True
                    break

                new_board.set_piece_at(square, piece)

            if role_failed:
                continue

            for original_square, piece, is_core_piece in sorted(non_role_entries, key=lambda item: not item[2]):
                delta_file, delta_rank = _square_delta(attacker.square, original_square)
                preferred_primary = _apply_delta(anchor_square, *_transform_vector((delta_file, delta_rank), variant))

                preferred_squares: List[Optional[int]] = [preferred_primary]
                if preferred_primary is not None:
                    preferred_squares.extend(_nearby_squares(preferred_primary, radius=1 if is_core_piece else 2))
                preferred_squares.extend(_nearby_squares(original_square, radius=1 if is_core_piece else 2))

                placed = _place_piece_with_fallback(
                    new_board,
                    piece,
                    preferred_squares,
                    reserved_empty,
                    required=is_core_piece
                )
                if not placed:
                    role_failed = True
                    break

            if role_failed:
                continue

            new_board.set_castling_fen("-")
            new_board.ep_square = None
            if not _validate_board(new_board):
                continue

            fen = new_board.fen()
            if fen in seen_fens or fen == board.fen():
                continue

            method_name = f"role_reembed_{variant}"
            seen_fens.add(fen)
            generated.append((method_name, new_board))
            produced_for_variant += 1

    return generated


def _rotate_180(board: chess.Board) -> Optional[chess.Board]:
    """Rotate the board 180 degrees while preserving piece colors and side to move."""
    new_board = chess.Board(None)
    new_board.turn = board.turn

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            file = 7 - chess.square_file(sq)
            rank = 7 - chess.square_rank(sq)
            new_sq = chess.square(file, rank)
            new_board.set_piece_at(new_sq, piece)

    new_board.set_castling_fen("-")
    new_board.ep_square = None

    return new_board if _validate_board(new_board) else None


def _analyze_with_cache(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    depth: int,
    multipv: int = 1,
    cache: Optional[Dict[Tuple[str, int, int], List[Dict[str, Any]]]] = None
) -> List[Dict[str, Any]]:
    """Analyze a board position and normalize the response to a list of PV entries."""
    key = (board.fen(), depth, multipv)
    if cache is not None and key in cache:
        return cache[key]

    try:
        if multipv > 1:
            result = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
            normalized = result if isinstance(result, list) else [result]
        else:
            result = engine.analyse(board, chess.engine.Limit(depth=depth))
            normalized = [result]
    except chess.engine.EngineError as exc:
        _log_generation_event(
            logging.WARNING,
            "engine_analysis_failed",
            fen=board.fen(),
            depth=depth,
            multipv=multipv,
            error=str(exc),
        )
        return []

    if cache is not None:
        cache[key] = normalized

    return normalized


def _score_to_cp(info: Dict[str, Any], turn: bool) -> int:
    """Convert a python-chess engine score into centipawns for the side to move."""
    score = info.get("score")
    if score is None:
        return 0

    pov = score.pov(turn)
    if pov.is_mate():
        mate_in = pov.mate()
        if mate_in is None:
            return 0
        sign = 1 if mate_in > 0 else -1
        return sign * (10000 - (abs(mate_in) * 10))

    return pov.score() or 0


def _motif_match_score(source_motifs: List[str], candidate_motifs: List[str]) -> float:
    """Measure motif overlap between source and candidate."""
    if not source_motifs:
        return 1.0 if candidate_motifs else 0.5

    overlap = set(source_motifs) & set(candidate_motifs)
    return round(len(overlap) / len(set(source_motifs)), 3)


def _target_eval_band(difficulty: Optional[str]) -> Tuple[int, int]:
    """Return the target eval-gap band for the requested difficulty."""
    bands = {
        "easy": (300, 10000),
        "medium": (150, 700),
        "hard": (80, 250),
    }
    return bands.get((difficulty or "").lower(), (150, 700))


def _eval_gap_match_score(eval_gap_cp: int, difficulty: Optional[str]) -> float:
    """Score how well a candidate's eval gap fits the requested band."""
    lower, upper = _target_eval_band(difficulty)
    if lower <= eval_gap_cp <= upper:
        return 1.0
    if eval_gap_cp < lower:
        return round(max(0.0, eval_gap_cp / lower), 3) if lower else 0.0
    excess = eval_gap_cp - upper
    decay_base = max(upper, 1)
    return round(max(0.0, 1 - (excess / decay_base)), 3)


def _difficulty_depths(difficulty: Optional[str]) -> Tuple[int, int]:
    """Tune fast and quality depths by requested difficulty."""
    level = (difficulty or "").lower()
    if level == "easy":
        return 6, 9
    if level == "hard":
        return 8, 12
    return 7, 10


def _line_stability_score(fast_best: Optional[chess.Move], quality_best: Optional[chess.Move], board: chess.Board) -> float:
    """Compare fast-depth and quality-depth best moves."""
    if not fast_best or not quality_best:
        return 0.0
    if fast_best == quality_best:
        return 1.0

    fast_piece = board.piece_at(fast_best.from_square)
    quality_piece = board.piece_at(quality_best.from_square)
    if fast_piece and quality_piece and fast_piece.piece_type == quality_piece.piece_type:
        return 0.5

    return 0.0


def _find_plausible_wrong_move(
    board: chess.Board,
    analysis_rows: List[Dict[str, Any]],
    best_move: chess.Move,
    best_eval_cp: int
) -> Tuple[Optional[chess.Move], int, float]:
    """Pick a plausible non-best move from the top engine alternatives."""
    chosen_move: Optional[chess.Move] = None
    chosen_eval: Optional[int] = None
    best_human_score = -1.0

    for row in analysis_rows:
        pv = row.get("pv", [])
        if not pv:
            continue

        move = pv[0]
        if move == best_move:
            continue

        alt_eval = _score_to_cp(row, board.turn)
        gap = max(0, best_eval_cp - alt_eval)
        if gap <= 0:
            continue

        human_score = 0.0
        if 120 <= gap <= 450:
            human_score = 1.0
        elif 80 <= gap <= 700:
            human_score = 0.7
        elif gap <= 1000:
            human_score = 0.4

        if human_score > best_human_score:
            best_human_score = human_score
            chosen_move = move
            chosen_eval = alt_eval

    if chosen_move is None or chosen_eval is None:
        return None, 0, 0.0

    return chosen_move, chosen_eval, round(best_human_score, 3)


def _piece_label(board: chess.Board, move: chess.Move) -> str:
    """Human-readable piece label for explanation text."""
    piece = board.piece_at(move.from_square)
    if not piece:
        return "piece"
    return chess.piece_name(piece.piece_type)


def _motif_summary(motifs: List[str]) -> str:
    """Format motifs for explanation text."""
    if not motifs:
        return "tactical pressure"
    if len(motifs) == 1:
        return motifs[0]
    return ", ".join(motifs[:-1]) + f" and {motifs[-1]}"


def _build_explanations(
    board: chess.Board,
    best_move: chess.Move,
    wrong_move: Optional[chess.Move],
    motifs: List[str],
    eval_gap_cp: int
) -> Tuple[str, str, str]:
    """Create short explainability strings for UI use."""
    summary = f"The position keeps the {_motif_summary(motifs)} theme with a roughly {eval_gap_cp}cp punishment gap."
    best_text = f"Best move {board.san(best_move)} activates the {_piece_label(board, best_move)} and preserves the tactical idea."

    if wrong_move is None:
        wrong_text = "Alternative moves do not keep the same tactical payoff."
    else:
        wrong_text = f"The tempting alternative {board.san(wrong_move)} drops the advantage and misses the main tactic."

    return summary, best_text, wrong_text


def _candidate_rejection(reason: str) -> Tuple[None, None, str]:
    """Return a normalized rejected-candidate result."""
    return None, None, reason


def _evaluate_candidate(
    source_board: chess.Board,
    candidate_board: chess.Board,
    method: str,
    source_motifs: List[str],
    difficulty: Optional[str],
    engine: Optional[chess.engine.SimpleEngine],
    analysis_cache: Optional[Dict[Tuple[str, int, int], List[Dict[str, Any]]]] = None,
    fast_depth: int = 7,
    quality_depth: int = 10
) -> Tuple[Optional[GeneratedPosition], Optional[CandidateScore], Optional[str]]:
    """Run the fast and quality validation passes for a single generated board."""
    if not _validate_board(candidate_board):
        return _candidate_rejection("illegal_board")

    if engine is None:
        legal_move = next(iter(candidate_board.legal_moves), None)
        if legal_move is None:
            return _candidate_rejection("no_legal_moves")

        motifs = source_motifs[:]
        summary, best_text, wrong_text = _build_explanations(
            candidate_board,
            legal_move,
            None,
            motifs,
            0
        )
        generated = GeneratedPosition(
            fen=candidate_board.fen(),
            correct_move_uci="",
            correct_move_san="",
            difficulty="unknown",
            method=method,
            eval_change=0,
            motifs=motifs
        )
        score = CandidateScore(
            best_move_uci="",
            best_move_san="",
            wrong_move_uci="",
            wrong_move_san="",
            best_eval_cp=0,
            wrong_eval_cp=0,
            eval_gap_cp=0,
            motifs=motifs,
            motif_match=1.0 if motifs else 0.5,
            line_stability=0.0,
            human_plausibility=0.0,
            composite_score=_novelty_score(source_board, candidate_board),
            line_stable=False,
            explanation_short=summary,
            explanation_best=best_text,
            explanation_wrong=wrong_text
        )
        return generated, score, None

    try:
        fast_rows = _analyze_with_cache(engine, candidate_board, fast_depth, multipv=3, cache=analysis_cache)
        quality_rows = _analyze_with_cache(engine, candidate_board, quality_depth, multipv=4, cache=analysis_cache)
    except chess.engine.EngineError:
        return _candidate_rejection("engine_failure")
    if not fast_rows or not quality_rows:
        return _candidate_rejection("engine_analysis_missing")

    fast_pv = fast_rows[0].get("pv", [])
    quality_pv = quality_rows[0].get("pv", [])
    if not fast_pv or not quality_pv:
        return _candidate_rejection("empty_principal_variation")

    fast_best = fast_pv[0]
    best_move = quality_pv[0]
    if best_move not in candidate_board.legal_moves:
        return _candidate_rejection("best_move_not_legal")

    best_eval_cp = _score_to_cp(quality_rows[0], candidate_board.turn)
    if best_eval_cp < 80:
        return _candidate_rejection("best_eval_too_small")

    candidate_motifs = detect_motifs(candidate_board, best_move, quality_pv)
    motif_match = _motif_match_score(source_motifs, candidate_motifs)
    if source_motifs and motif_match <= 0:
        return _candidate_rejection("motif_drift")

    wrong_move, wrong_eval_cp, human_plausibility = _find_plausible_wrong_move(
        candidate_board,
        quality_rows,
        best_move,
        best_eval_cp
    )
    eval_gap_cp = max(0, best_eval_cp - wrong_eval_cp)
    if wrong_move is None or eval_gap_cp < 80:
        return _candidate_rejection("no_plausible_wrong_move")

    line_stability = _line_stability_score(fast_best, best_move, candidate_board)
    novelty = _novelty_score(source_board, candidate_board)
    eval_gap_match = _eval_gap_match_score(eval_gap_cp, difficulty)
    composite_score = round(
        0.35 * motif_match
        + 0.25 * eval_gap_match
        + 0.20 * line_stability
        + 0.15 * novelty
        + 0.05 * human_plausibility,
        3
    )

    summary, best_text, wrong_text = _build_explanations(
        candidate_board,
        best_move,
        wrong_move,
        candidate_motifs,
        eval_gap_cp
    )

    generated = GeneratedPosition(
        fen=candidate_board.fen(),
        correct_move_uci=best_move.uci(),
        correct_move_san=candidate_board.san(best_move),
        difficulty=_get_difficulty(eval_gap_cp),
        method=method,
        eval_change=eval_gap_cp,
        motifs=candidate_motifs
    )
    score = CandidateScore(
        best_move_uci=best_move.uci(),
        best_move_san=candidate_board.san(best_move),
        wrong_move_uci=wrong_move.uci(),
        wrong_move_san=candidate_board.san(wrong_move),
        best_eval_cp=best_eval_cp,
        wrong_eval_cp=wrong_eval_cp,
        eval_gap_cp=eval_gap_cp,
        motifs=candidate_motifs,
        motif_match=motif_match,
        line_stability=line_stability,
        human_plausibility=human_plausibility,
        composite_score=composite_score,
        line_stable=(line_stability >= 1.0),
        explanation_short=summary,
        explanation_best=best_text,
        explanation_wrong=wrong_text
    )
    return generated, score, None


def _board_similarity(board_a: chess.Board, board_b: chess.Board) -> float:
    """Return a simple board similarity score in [0, 1]."""
    sig_a = _board_signature(board_a)
    sig_b = _board_signature(board_b)
    if len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return round(matches / len(sig_a), 3)


def _select_diverse_candidates(
    source_board: chess.Board,
    evaluated: List[Tuple[GeneratedPosition, CandidateScore]],
    count: int,
    similarity_threshold: float = 0.92
) -> List[Tuple[GeneratedPosition, CandidateScore]]:
    """Greedy diversity selection using the composite score and board similarity."""
    accepted: List[Tuple[GeneratedPosition, CandidateScore]] = []

    for candidate in sorted(evaluated, key=lambda item: item[1].composite_score, reverse=True):
        candidate_board = chess.Board(candidate[0].fen)
        if _board_similarity(source_board, candidate_board) >= 0.985:
            continue

        too_similar = False
        for accepted_pos, _ in accepted:
            accepted_board = chess.Board(accepted_pos.fen)
            if _board_similarity(candidate_board, accepted_board) >= similarity_threshold:
                too_similar = True
                break

        if too_similar:
            continue

        accepted.append(candidate)
        if len(accepted) >= count:
            break

    return accepted


def _candidate_stats_template() -> Dict[str, Any]:
    """Initialize generation statistics for observability and benchmarking."""
    return {
        "raw_candidates": 0,
        "evaluated": 0,
        "accepted": 0,
        "timed_out": False,
        "accepted_methods": {},
        "rejection_reasons": {},
    }


def _increment_counter(bucket: Dict[str, int], key: str):
    """Increment a string-keyed counter map."""
    bucket[key] = bucket.get(key, 0) + 1


def _analyze_source_position(
    board: chess.Board,
    played_uci: str,
    best_uci: str,
    engine: Optional[chess.engine.SimpleEngine],
    analysis_cache: Optional[Dict[Tuple[str, int, int], List[Dict[str, Any]]]] = None,
    depth: int = VERIFY_DEPTH
) -> Optional[Dict[str, Any]]:
    """Return a compact source analysis summary for the API response."""
    if engine is None:
        return None

    rows = _analyze_with_cache(engine, board, depth, multipv=1, cache=analysis_cache)
    if not rows:
        return None

    pv = rows[0].get("pv", [])
    eval_before_cp = _score_to_cp(rows[0], board.turn)

    played_board = board.copy()
    best_board = board.copy()
    played_move = chess.Move.from_uci(played_uci)
    best_move = chess.Move.from_uci(best_uci)

    played_after = None
    best_after = None
    if played_move in played_board.legal_moves:
        played_board.push(played_move)
        played_after_rows = _analyze_with_cache(engine, played_board, depth, multipv=1, cache=analysis_cache)
        if played_after_rows:
            played_after = _score_to_cp(played_after_rows[0], board.turn)

    if best_move in best_board.legal_moves:
        best_board.push(best_move)
        best_after_rows = _analyze_with_cache(engine, best_board, depth, multipv=1, cache=analysis_cache)
        if best_after_rows:
            best_after = _score_to_cp(best_after_rows[0], board.turn)

    return {
        "depth": depth,
        "pv": [move.uci() for move in pv[:5]],
        "eval_before_cp": eval_before_cp,
        "eval_after_best_cp": best_after,
        "eval_after_played_cp": played_after
    }


def generate_similar_positions_mvp(
    fen: str,
    played_uci: str,
    best_uci: str,
    count: int = 20,
    difficulty: Optional[str] = None,
    use_stockfish: bool = True,
    side_to_move: Optional[str] = None,
    seed: Optional[int] = None,
    timeout_seconds: float = 12.0
) -> Dict[str, Any]:
    """
    Iteration-1 MVP wrapper for generating similar positions with source metadata.

    Returns:
        {
            "source": {...},
            "generated": [...]
        }
    """
    board = chess.Board(fen)
    pattern = extract_mistake_pattern(fen, played_uci, best_uci)
    if not pattern:
        return {
            "source": {"fen": fen, "motifs": []},
            "generated": [],
            "partial": False
        }

    role_graph = _build_role_graph(board, pattern)
    source_profile = SourceTacticalProfile(
        fen=fen,
        motifs=pattern.motifs,
        core_squares=_square_name_list(pattern.core_squares),
        peripheral_squares=_square_name_list(pattern.peripheral_squares),
        role_graph=_serialize_role_graph(role_graph)
    )

    requested_turn = (side_to_move or "same_as_source").strip().lower()
    if requested_turn not in {"same_as_source", "white", "black"}:
        requested_turn = "same_as_source"

    source_turn = board.turn
    analysis_cache: Dict[Tuple[str, int, int], List[Dict[str, Any]]] = {}
    partial = False
    started_at = time.perf_counter()
    fast_depth, quality_depth = _difficulty_depths(difficulty)
    stats = _candidate_stats_template()

    random_state = random.getstate()
    if seed is not None:
        random.seed(seed)

    stockfish_path = find_stockfish() if use_stockfish else None
    engine: Optional[chess.engine.SimpleEngine] = None
    source_payload = asdict(source_profile)
    normalized: List[Dict[str, Any]] = []

    try:
        _log_generation_event(
            logging.INFO,
            "generation_start",
            fen=fen,
            count=count,
            difficulty=difficulty,
            requested_turn=requested_turn,
            timeout_seconds=timeout_seconds,
            seed=seed,
            use_stockfish=use_stockfish,
        )

        if stockfish_path:
            engine = chess.engine.SimpleEngine.popen_uci(str(stockfish_path))

        pool_size = max(count * 10, 40)
        generated = generate_similar_positions(
            fen=fen,
            played_uci=played_uci,
            best_uci=best_uci,
            count=pool_size,
            use_stockfish=False
        )

        raw_candidates: List[Tuple[str, str]] = []
        seen_fens = {fen}

        for strategy_name, strategy_fn in [
            ("mirror_h", lambda: _mirror_horizontal(board)),
            ("mirror_v", lambda: _mirror_vertical(board)),
            ("rotate_180", lambda: _rotate_180(board)),
        ]:
            try:
                transformed = strategy_fn()
            except Exception:
                transformed = None

            if transformed is None:
                continue

            transformed_fen = transformed.fen()
            if transformed_fen not in seen_fens:
                raw_candidates.append((transformed_fen, strategy_name))
                seen_fens.add(transformed_fen)

        for pos in generated:
            if pos.fen not in seen_fens:
                raw_candidates.append((pos.fen, pos.method))
                seen_fens.add(pos.fen)

        stats["raw_candidates"] = len(raw_candidates)

        evaluated: List[Tuple[GeneratedPosition, CandidateScore]] = []
        for candidate_fen, method in raw_candidates:
            if time.perf_counter() - started_at > timeout_seconds:
                partial = True
                stats["timed_out"] = True
                _log_generation_event(logging.WARNING, "generation_timeout", method=method, elapsed_seconds=round(time.perf_counter() - started_at, 3))
                break

            try:
                candidate_board = chess.Board(candidate_fen)
            except Exception:
                continue

            if requested_turn == "same_as_source" and candidate_board.turn != source_turn:
                _increment_counter(stats["rejection_reasons"], "side_to_move_mismatch")
                continue
            if requested_turn == "white" and candidate_board.turn != chess.WHITE:
                _increment_counter(stats["rejection_reasons"], "side_to_move_mismatch")
                continue
            if requested_turn == "black" and candidate_board.turn != chess.BLACK:
                _increment_counter(stats["rejection_reasons"], "side_to_move_mismatch")
                continue

            generated_pos, candidate_score, rejection_reason = _evaluate_candidate(
                source_board=board,
                candidate_board=candidate_board,
                method=method,
                source_motifs=pattern.motifs,
                difficulty=difficulty,
                engine=engine,
                analysis_cache=analysis_cache,
                fast_depth=fast_depth,
                quality_depth=quality_depth
            )
            stats["evaluated"] += 1
            if rejection_reason is not None:
                _increment_counter(stats["rejection_reasons"], rejection_reason)
                _log_generation_event(logging.DEBUG, "candidate_rejected", method=method, reason=rejection_reason, fen=candidate_fen)
                continue

            if difficulty and generated_pos.difficulty != difficulty.lower().strip():
                _increment_counter(stats["rejection_reasons"], "difficulty_mismatch")
                continue

            evaluated.append((generated_pos, candidate_score))
            _log_generation_event(
                logging.DEBUG,
                "candidate_scored",
                method=method,
                quality_score=candidate_score.composite_score,
                eval_gap_cp=candidate_score.eval_gap_cp,
                motifs=candidate_score.motifs,
            )

        selected = _select_diverse_candidates(board, evaluated, count=count)
        for pos, candidate_score in selected:
            candidate_board = chess.Board(pos.fen)
            novelty = _novelty_score(board, candidate_board)
            stats["accepted"] += 1
            _increment_counter(stats["accepted_methods"], pos.method)
            normalized.append({
                "fen": pos.fen,
                "solution_move_uci": pos.correct_move_uci,
                "solution_move_san": pos.correct_move_san,
                "motifs": pos.motifs,
                "eval_gap_cp": pos.eval_change,
                "difficulty": pos.difficulty,
                "generation_method": pos.method,
                "novelty_score": novelty,
                "quality_score": candidate_score.composite_score,
                "line_stable": candidate_score.line_stable,
                "wrong_move_uci": candidate_score.wrong_move_uci,
                "wrong_move_san": candidate_score.wrong_move_san,
                "explanations": {
                    "summary": candidate_score.explanation_short,
                    "best_move": candidate_score.explanation_best,
                    "wrong_move": candidate_score.explanation_wrong
                }
            })

        source_analysis = _analyze_source_position(
            board,
            played_uci,
            best_uci,
            engine,
            analysis_cache=analysis_cache,
            depth=VERIFY_DEPTH
        )
        if source_analysis is not None:
            source_payload["analysis"] = source_analysis

        _log_generation_event(
            logging.INFO,
            "generation_complete",
            accepted=stats["accepted"],
            evaluated=stats["evaluated"],
            raw_candidates=stats["raw_candidates"],
            partial=partial,
            rejection_reasons=stats["rejection_reasons"],
            accepted_methods=stats["accepted_methods"],
            elapsed_seconds=round(time.perf_counter() - started_at, 3),
        )

    finally:
        if engine is not None:
            try:
                engine.quit()
            except chess.engine.EngineError as exc:
                _log_generation_event(logging.WARNING, "engine_shutdown_failed", error=str(exc))
        if seed is not None:
            random.setstate(random_state)

    return {
        "source": source_payload,
        "generated": normalized[:count],
        "partial": partial,
        "stats": stats
    }


# For convenience: convert results to dicts
def positions_to_dicts(positions: List[GeneratedPosition]) -> List[Dict]:
    """Convert list of GeneratedPosition to list of dicts."""
    return [asdict(p) for p in positions]
