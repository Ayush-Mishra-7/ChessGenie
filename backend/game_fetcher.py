"""
Game fetching service for Lichess and Chess.com APIs.
"""
import httpx
import chess.pgn
from io import StringIO
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class FetchedGame:
    """Represents a fetched chess game."""
    game_id: str
    pgn: str
    white: str
    black: str
    result: str
    opening: Optional[str] = None
    date: Optional[str] = None
    time_control: Optional[str] = None
    platform: str = "unknown"


async def fetch_lichess_games(username: str, limit: int = 10) -> List[FetchedGame]:
    """
    Fetch games from Lichess API.
    
    Uses the streaming NDJSON endpoint:
    GET https://lichess.org/api/games/user/{username}
    
    Args:
        username: Lichess username
        limit: Maximum number of games to fetch (default 10 for testing)
    
    Returns:
        List of FetchedGame objects
    """
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        "max": limit,
        "pgnInJson": "true",
        "opening": "true",
        "clocks": "false",
        "evals": "false"
    }
    headers = {
        "Accept": "application/x-ndjson"
    }
    
    games = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream("GET", url, params=params, headers=headers) as response:
                if response.status_code == 404:
                    logger.warning(f"Lichess user not found: {username}")
                    return []
                
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    import json
                    game_data = json.loads(line)
                    
                    game = FetchedGame(
                        game_id=game_data.get("id", ""),
                        pgn=game_data.get("pgn", ""),
                        white=game_data.get("players", {}).get("white", {}).get("user", {}).get("name", "Unknown"),
                        black=game_data.get("players", {}).get("black", {}).get("user", {}).get("name", "Unknown"),
                        result=_parse_result(game_data.get("winner")),
                        opening=game_data.get("opening", {}).get("name"),
                        date=game_data.get("createdAt"),
                        time_control=game_data.get("speed"),
                        platform="LICHESS"
                    )
                    games.append(game)
                    
                    if len(games) >= limit:
                        break
                        
        except httpx.HTTPStatusError as e:
            logger.error(f"Lichess API error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Lichess request error: {e}")
            raise
    
    logger.info(f"Fetched {len(games)} games from Lichess for {username}")
    return games


async def fetch_chesscom_games(username: str, limit: int = 10) -> List[FetchedGame]:
    """
    Fetch games from Chess.com API.
    
    Uses the archives endpoint:
    GET https://api.chess.com/pub/player/{username}/games/archives
    Then fetches games from each monthly archive.
    
    Args:
        username: Chess.com username (case-insensitive)
        limit: Maximum number of games to fetch (default 10 for testing)
    
    Returns:
        List of FetchedGame objects
    """
    username_lower = username.lower()
    archives_url = f"https://api.chess.com/pub/player/{username_lower}/games/archives"
    
    headers = {
        "User-Agent": "ChessGenie/1.0 (contact: support@chessgenie.app)"
    }
    
    games = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # First, get list of monthly archives
            archives_response = await client.get(archives_url, headers=headers)
            
            if archives_response.status_code == 404:
                logger.warning(f"Chess.com user not found: {username}")
                return []
            
            archives_response.raise_for_status()
            archives_data = archives_response.json()
            archive_urls = archives_data.get("archives", [])
            
            if not archive_urls:
                logger.info(f"No games found for Chess.com user: {username}")
                return []
            
            # Fetch from most recent archives first
            for archive_url in reversed(archive_urls):
                if len(games) >= limit:
                    break
                
                archive_response = await client.get(archive_url, headers=headers)
                archive_response.raise_for_status()
                archive_data = archive_response.json()
                
                archive_games = archive_data.get("games", [])
                
                # Process games in reverse order (most recent first)
                for game_data in reversed(archive_games):
                    if len(games) >= limit:
                        break
                    
                    pgn = game_data.get("pgn", "")
                    
                    game = FetchedGame(
                        game_id=game_data.get("uuid", game_data.get("url", "").split("/")[-1]),
                        pgn=pgn,
                        white=game_data.get("white", {}).get("username", "Unknown"),
                        black=game_data.get("black", {}).get("username", "Unknown"),
                        result=_parse_chesscom_result(game_data),
                        opening=_extract_opening_from_pgn(pgn),
                        date=game_data.get("end_time"),
                        time_control=game_data.get("time_class"),
                        platform="CHESS_COM"
                    )
                    games.append(game)
                    
        except httpx.HTTPStatusError as e:
            logger.error(f"Chess.com API error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Chess.com request error: {e}")
            raise
    
    logger.info(f"Fetched {len(games)} games from Chess.com for {username}")
    return games


def _parse_result(winner: Optional[str]) -> str:
    """Parse Lichess winner field to standard result format."""
    if winner == "white":
        return "1-0"
    elif winner == "black":
        return "0-1"
    else:
        return "1/2-1/2"


def _parse_chesscom_result(game_data: Dict) -> str:
    """Parse Chess.com game result."""
    white = game_data.get("white", {})
    black = game_data.get("black", {})
    
    white_result = white.get("result", "")
    
    if white_result == "win":
        return "1-0"
    elif white_result in ("checkmated", "timeout", "resigned", "abandoned"):
        return "0-1"
    elif white_result in ("stalemate", "agreed", "repetition", "insufficient", "50move", "timevsinsufficient"):
        return "1/2-1/2"
    else:
        return "*"


def _extract_opening_from_pgn(pgn: str) -> Optional[str]:
    """Extract opening name from PGN headers if available."""
    try:
        game = chess.pgn.read_game(StringIO(pgn))
        if game and "Opening" in game.headers:
            return game.headers["Opening"]
        if game and "ECO" in game.headers:
            return game.headers["ECO"]
    except Exception:
        pass
    return None


async def fetch_games(platform: str, username: str, limit: int = 10) -> List[FetchedGame]:
    """
    Unified game fetching function.
    
    Args:
        platform: "LICHESS" or "CHESS_COM"
        username: Username on the platform
        limit: Maximum games to fetch
    
    Returns:
        List of FetchedGame objects
    """
    if platform.upper() == "LICHESS":
        return await fetch_lichess_games(username, limit)
    elif platform.upper() in ("CHESS_COM", "CHESSCOM"):
        return await fetch_chesscom_games(username, limit)
    else:
        raise ValueError(f"Unsupported platform: {platform}")
