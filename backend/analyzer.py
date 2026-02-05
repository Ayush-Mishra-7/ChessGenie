"""
Chess Game Analyzer using Stockfish.

Analyzes games move-by-move to identify:
- Best moves and alternatives
- Mistakes, blunders, inaccuracies
- Accuracy percentages for each player
- Critical moments where the game could have changed
"""
import os
import chess
import chess.pgn
import chess.engine
from io import StringIO
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
import logging
import asyncio

logger = logging.getLogger(__name__)

# Default paths for Stockfish
ENGINES_DIR = Path(__file__).parent / "engines"

# Analysis configuration
DEFAULT_DEPTH = 15  # Lower depth for faster analysis
DEFAULT_TIMEOUT = 60.0  # Seconds per game


@dataclass
class MoveAnalysis:
    """Analysis result for a single move."""
    move_number: int
    move_san: str
    move_uci: str
    is_white: bool
    eval_before: int  # Centipawns from white's perspective
    eval_after: int
    best_move_uci: str
    best_move_san: str
    centipawn_loss: int
    classification: str  # excellent, good, inaccuracy, mistake, blunder
    position_fen: str


@dataclass
class GameAnalysisResult:
    """Complete analysis result for a game."""
    game_id: str
    white: str
    black: str
    result: str
    opening: Optional[str]
    accuracy_white: float
    accuracy_black: float
    total_moves: int
    mistakes: List[Dict] = field(default_factory=list)
    blunders: List[Dict] = field(default_factory=list)
    best_moves: List[Dict] = field(default_factory=list)
    critical_moments: List[Dict] = field(default_factory=list)
    move_analyses: List[Dict] = field(default_factory=list)
    status: str = "analyzed"
    
    def to_dict(self) -> Dict:
        return asdict(self)


def find_stockfish() -> Optional[Path]:
    """Find Stockfish executable in engines directory."""
    if not ENGINES_DIR.exists():
        return None
    
    # Look for stockfish executable
    patterns = ["stockfish*.exe", "stockfish*"]
    for pattern in patterns:
        matches = list(ENGINES_DIR.glob(pattern))
        for match in matches:
            if match.is_file() and not match.suffix in [".zip", ".tar"]:
                return match
    
    return None


def classify_move(centipawn_loss: int) -> str:
    """Classify a move based on centipawn loss."""
    if centipawn_loss <= 10:
        return "best"
    elif centipawn_loss <= 30:
        return "excellent"
    elif centipawn_loss <= 100:
        return "good"
    elif centipawn_loss <= 200:
        return "inaccuracy"
    elif centipawn_loss <= 500:
        return "mistake"
    else:
        return "blunder"


def calculate_accuracy(centipawn_losses: List[int]) -> float:
    """
    Calculate accuracy percentage from centipawn losses.
    
    Uses the formula: accuracy = 100 * (1 - avg_loss / 200)
    Clamped to [0, 100]
    """
    if not centipawn_losses:
        return 100.0
    
    avg_loss = sum(centipawn_losses) / len(centipawn_losses)
    accuracy = 100 * (1 - avg_loss / 200)
    return max(0.0, min(100.0, round(accuracy, 1)))


def analyze_game_sync(
    pgn_text: str,
    game_id: str = "",
    depth: int = DEFAULT_DEPTH,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[GameAnalysisResult]:
    """
    Analyze a single game synchronously.
    
    Args:
        pgn_text: PGN string of the game
        game_id: Identifier for the game
        depth: Stockfish search depth
        timeout: Maximum time for analysis
    
    Returns:
        GameAnalysisResult or None if analysis fails
    """
    stockfish_path = find_stockfish()
    if not stockfish_path:
        logger.error("Stockfish not found! Run download_stockfish.py first.")
        return None
    
    try:
        # Parse PGN
        game = chess.pgn.read_game(StringIO(pgn_text))
        if not game:
            logger.error(f"Failed to parse PGN for game {game_id}")
            return None
        
        # Extract game metadata
        white = game.headers.get("White", "Unknown")
        black = game.headers.get("Black", "Unknown")
        result = game.headers.get("Result", "*")
        opening = game.headers.get("Opening") or game.headers.get("ECO")
        
        # Initialize engine
        engine = chess.engine.SimpleEngine.popen_uci(str(stockfish_path))
        
        try:
            board = game.board()
            moves = list(game.mainline_moves())
            
            move_analyses = []
            white_losses = []
            black_losses = []
            mistakes = []
            blunders = []
            best_moves = []
            critical_moments = []
            
            # Get initial evaluation
            initial_info = engine.analyse(board, chess.engine.Limit(depth=depth))
            prev_eval = _get_score(initial_info, board.turn)
            
            for move_num, move in enumerate(moves):
                is_white = board.turn == chess.WHITE
                move_san = board.san(move)
                move_uci = move.uci()
                position_fen = board.fen()
                
                # Get best move BEFORE playing the actual move
                best_info = engine.analyse(board, chess.engine.Limit(depth=depth))
                best_move = best_info.get("pv", [None])[0]
                best_move_san = board.san(best_move) if best_move else move_san
                best_move_uci = best_move.uci() if best_move else move_uci
                eval_before = _get_score(best_info, chess.WHITE)
                
                # Play the move
                board.push(move)
                
                # Get evaluation AFTER the move
                after_info = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after = _get_score(after_info, chess.WHITE)
                
                # Calculate centipawn loss (from the perspective of the player who moved)
                if is_white:
                    cp_loss = max(0, eval_before - eval_after)
                    white_losses.append(cp_loss)
                else:
                    cp_loss = max(0, eval_after - eval_before)  # Black wants eval to go down
                    black_losses.append(cp_loss)
                
                classification = classify_move(cp_loss)
                
                move_analysis = MoveAnalysis(
                    move_number=(move_num // 2) + 1,
                    move_san=move_san,
                    move_uci=move_uci,
                    is_white=is_white,
                    eval_before=eval_before,
                    eval_after=eval_after,
                    best_move_uci=best_move_uci,
                    best_move_san=best_move_san,
                    centipawn_loss=cp_loss,
                    classification=classification,
                    position_fen=position_fen
                )
                
                move_analyses.append(asdict(move_analysis))
                
                # Track special moves
                if classification == "mistake":
                    mistakes.append({
                        "move_number": move_analysis.move_number,
                        "player": "white" if is_white else "black",
                        "played": move_san,
                        "best": best_move_san,
                        "loss": cp_loss
                    })
                elif classification == "blunder":
                    blunders.append({
                        "move_number": move_analysis.move_number,
                        "player": "white" if is_white else "black",
                        "played": move_san,
                        "best": best_move_san,
                        "loss": cp_loss
                    })
                elif classification == "best":
                    best_moves.append({
                        "move_number": move_analysis.move_number,
                        "player": "white" if is_white else "black",
                        "move": move_san
                    })
                
                # Track critical moments (large eval swings)
                if abs(eval_after - eval_before) > 150:
                    critical_moments.append({
                        "move_number": move_analysis.move_number,
                        "player": "white" if is_white else "black",
                        "eval_change": eval_after - eval_before,
                        "position_fen": position_fen
                    })
                
                prev_eval = eval_after
            
            # Calculate accuracy
            accuracy_white = calculate_accuracy(white_losses)
            accuracy_black = calculate_accuracy(black_losses)
            
            return GameAnalysisResult(
                game_id=game_id,
                white=white,
                black=black,
                result=result,
                opening=opening,
                accuracy_white=accuracy_white,
                accuracy_black=accuracy_black,
                total_moves=len(moves),
                mistakes=mistakes[:10],  # Top 10
                blunders=blunders[:10],
                best_moves=best_moves[:10],
                critical_moments=critical_moments[:10],
                move_analyses=move_analyses  # Full analysis
            )
            
        finally:
            engine.quit()
            
    except Exception as e:
        logger.error(f"Analysis failed for game {game_id}: {e}")
        return None


def _get_score(info: Dict, perspective: chess.Color) -> int:
    """Extract centipawn score from engine info, from white's perspective."""
    score = info.get("score")
    if score is None:
        return 0
    
    # Get score from white's perspective
    pov_score = score.white()
    
    if pov_score.is_mate():
        mate_in = pov_score.mate()
        # Convert mate to centipawns (mate in 1 = 10000, mate in 2 = 9990, etc.)
        if mate_in > 0:
            return 10000 - (mate_in * 10)
        else:
            return -10000 - (mate_in * 10)
    else:
        return pov_score.score()


async def analyze_game(
    pgn_text: str,
    game_id: str = "",
    depth: int = DEFAULT_DEPTH
) -> Optional[GameAnalysisResult]:
    """Async wrapper for game analysis."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        analyze_game_sync,
        pgn_text,
        game_id,
        depth
    )


async def analyze_games(
    games: List[Tuple[str, str]],  # List of (game_id, pgn) tuples
    depth: int = DEFAULT_DEPTH
) -> List[GameAnalysisResult]:
    """
    Analyze multiple games.
    
    Args:
        games: List of (game_id, pgn_text) tuples
        depth: Analysis depth
    
    Returns:
        List of GameAnalysisResult objects
    """
    results = []
    
    for game_id, pgn in games:
        logger.info(f"Analyzing game {game_id}...")
        result = await analyze_game(pgn, game_id, depth)
        if result:
            results.append(result)
    
    return results
