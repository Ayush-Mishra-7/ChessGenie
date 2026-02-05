"""
ChessGenie Analysis Service - FastAPI Backend

This service handles:
- Game fetching from Lichess and Chess.com
- Job processing for analysis tasks
- Health checks and status endpoints
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from contextlib import asynccontextmanager

from game_fetcher import fetch_games, FetchedGame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
base_dir = os.path.dirname(__file__)
env_path = os.path.join(base_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL not set in backend/.env')

engine = create_engine(DATABASE_URL, future=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("ChessGenie Analysis Service starting up...")
    yield
    logger.info("ChessGenie Analysis Service shutting down...")


app = FastAPI(
    title='ChessGenie Analysis Service',
    version='0.1.0',
    lifespan=lifespan
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async def root():
    """Root endpoint - service info."""
    return {'status': 'ok', 'service': 'chessgenie-analysis', 'version': '0.1.0'}


@app.get('/health')
async def health():
    """Health check endpoint."""
    return {'healthy': True, 'timestamp': datetime.utcnow().isoformat()}


@app.post('/jobs/{job_id}/process')
async def process_job(job_id: str, background_tasks: BackgroundTasks):
    """
    Process a queued analysis job.
    
    This endpoint:
    1. Fetches the job from database
    2. Retrieves games from the specified platform
    3. Stores the games in GameAnalysis table  
    4. Updates job status to COMPLETED
    """
    with engine.connect() as conn:
        # Fetch job details
        job_row = conn.execute(
            text('SELECT id, "userId", type, status, payload FROM "Job" WHERE id = :id'),
            {'id': job_id}
        ).first()
        
        if not job_row:
            raise HTTPException(status_code=404, detail='Job not found')

        job_status = job_row[3]
        if job_status != 'QUEUED':
            raise HTTPException(
                status_code=400, 
                detail=f'Job is not queued (current status: {job_status})'
            )

        # Mark job as running
        conn.execute(
            text('UPDATE "Job" SET status = :s, "updatedAt" = now() WHERE id = :id'),
            {'s': 'RUNNING', 'id': job_id}
        )
        conn.commit()

    # Process job in background
    background_tasks.add_task(
        _process_job_task,
        job_id,
        job_row[1],  # userId
        job_row[4]   # payload
    )

    return {'ok': True, 'jobId': job_id, 'status': 'RUNNING'}


async def _process_job_task(job_id: str, user_id: str, payload):
    """Background task to process a job."""
    try:
        # Parse payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        platform = payload.get('platform', 'LICHESS')
        username = payload.get('username', '')
        game_limit = int(payload.get('game_limit', 10))  # Default to 10 for testing
        analysis_depth = int(payload.get('analysis_depth', 15))  # Stockfish depth
        
        logger.info(f"Processing job {job_id}: fetching {game_limit} games from {platform} for {username}")
        
        # Fetch games from platform
        games = await fetch_games(platform, username, game_limit)
        
        if not games:
            logger.warning(f"No games found for {username} on {platform}")
            _update_job_failed(job_id, "No games found for this user")
            return
        
        logger.info(f"Fetched {len(games)} games. Starting Stockfish analysis...")
        
        # Import analyzer (do it here to avoid import issues if Stockfish not installed)
        from analyzer import analyze_games_parallel, find_stockfish
        
        stockfish_available = find_stockfish() is not None
        if not stockfish_available:
            logger.warning("Stockfish not found - skipping deep analysis")
        
        # Check for previously analyzed games (caching)
        game_ids = [game.game_id for game in games]
        cached_analyses = {}
        with engine.connect() as conn:
            result = conn.execute(
                text('''
                    SELECT "gameId", result FROM "GameAnalysis" 
                    WHERE "userId" = :userId AND "gameId" = ANY(:gameIds)
                    AND result::text LIKE '%"status": "analyzed"%'
                '''),
                {'userId': user_id, 'gameIds': game_ids}
            )
            for row in result:
                cached_analyses[row[0]] = row[1]
        
        # Separate games into cached and need-analysis
        games_to_analyze = []
        game_lookup = {}
        for game in games:
            game_lookup[game.game_id] = game
            if game.game_id not in cached_analyses and game.pgn:
                games_to_analyze.append((game.game_id, game.pgn))
        
        logger.info(f"Found {len(cached_analyses)} cached analyses, {len(games_to_analyze)} need analysis")
        
        analyses = []
        game_counter = [0]  # Use list to allow mutation in closure
        
        def store_game_result(game, analysis_result, ga_id):
            """Store a single game result to database immediately."""
            if analysis_result:
                result_data = {
                    "game_id": game.game_id,
                    "white": game.white,
                    "black": game.black,
                    "result": game.result,
                    "opening": game.opening or analysis_result.opening,
                    "date": str(game.date) if game.date else None,
                    "time_control": game.time_control,
                    "platform": game.platform,
                    "status": "analyzed",
                    # Analysis metrics
                    "accuracy_white": analysis_result.accuracy_white,
                    "accuracy_black": analysis_result.accuracy_black,
                    "total_moves": analysis_result.total_moves,
                    "mistakes": analysis_result.mistakes,
                    "blunders": analysis_result.blunders,
                    "best_moves": analysis_result.best_moves,
                    "critical_moments": analysis_result.critical_moments
                }
            else:
                result_data = {
                    "game_id": game.game_id,
                    "white": game.white,
                    "black": game.black,
                    "result": game.result,
                    "opening": game.opening,
                    "date": str(game.date) if game.date else None,
                    "time_control": game.time_control,
                    "platform": game.platform,
                    "status": "fetched"  # Not analyzed
                }
            
            result_json = json.dumps(result_data)
            
            with engine.connect() as conn:
                conn.execute(
                    text('''
                        INSERT INTO "GameAnalysis" 
                        (id, "userId", "jobId", "gameId", pgn, result, "createdAt", "updatedAt") 
                        VALUES (:id, :userId, :jobId, :gameId, :pgn, :result, now(), now())
                    '''),
                    {
                        'id': ga_id,
                        'userId': user_id,
                        'jobId': job_id,
                        'gameId': game.game_id,
                        'pgn': game.pgn,
                        'result': result_json
                    }
                )
                conn.commit()
            
            return {
                'id': ga_id, 
                'gameId': game.game_id,
                'status': result_data.get('status'),
                'accuracy_white': result_data.get('accuracy_white'),
                'accuracy_black': result_data.get('accuracy_black')
            }
        
        if stockfish_available and games_to_analyze:
            # Use parallel analysis - stream results as each game completes
            async for analysis_result in analyze_games_parallel(
                games_to_analyze, 
                depth=analysis_depth,
                max_workers=2  # Limit concurrent Stockfish instances
            ):
                game_counter[0] += 1
                ga_id = f"{job_id}_g{game_counter[0]}"
                game = game_lookup.get(analysis_result.game_id)
                
                if game:
                    analysis_info = store_game_result(game, analysis_result, ga_id)
                    analyses.append(analysis_info)
                    logger.info(f"Stored game {game_counter[0]}/{len(games)}: {game.white} vs {game.black}")
        else:
            # No Stockfish - just store games without analysis
            for i, game in enumerate(games):
                ga_id = f"{job_id}_g{i}"
                analysis_info = store_game_result(game, None, ga_id)
                analyses.append(analysis_info)
        
        # Mark job as completed
        with engine.connect() as conn:
            conn.execute(
                text('UPDATE "Job" SET status = :s, result = :res, "updatedAt" = now() WHERE id = :id'),
                {
                    's': 'COMPLETED',
                    'res': json.dumps({
                        'total_games': len(games),
                        'analyses': analyses,
                        'platform': platform,
                        'username': username
                    }),
                    'id': job_id
                }
            )
            conn.commit()
        
        logger.info(f"Job {job_id} completed: analyzed {len(analyses)} games")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _update_job_failed(job_id, str(e))


def _update_job_failed(job_id: str, error_message: str):
    """Mark a job as failed."""
    with engine.connect() as conn:
        conn.execute(
            text('UPDATE "Job" SET status = :s, result = :res, "updatedAt" = now() WHERE id = :id'),
            {
                's': 'FAILED',
                'res': json.dumps({'error': error_message}),
                'id': job_id
            }
        )
        conn.commit()


@app.get('/jobs/{job_id}/status')
async def get_job_status(job_id: str):
    """Get the status of a job."""
    with engine.connect() as conn:
        job_row = conn.execute(
            text('SELECT id, status, result, "createdAt", "updatedAt" FROM "Job" WHERE id = :id'),
            {'id': job_id}
        ).first()
        
        if not job_row:
            raise HTTPException(status_code=404, detail='Job not found')
        
        result = None
        if job_row[2]:
            try:
                result = json.loads(job_row[2]) if isinstance(job_row[2], str) else job_row[2]
            except:
                result = job_row[2]
        
        return {
            'jobId': job_row[0],
            'status': job_row[1],
            'result': result,
            'createdAt': str(job_row[3]),
            'updatedAt': str(job_row[4])
        }


@app.get('/games/{user_id}')
async def get_user_games(user_id: str, limit: int = 50):
    """Get all fetched games for a user."""
    with engine.connect() as conn:
        rows = conn.execute(
            text('''
                SELECT id, "gameId", pgn, result, "createdAt" 
                FROM "GameAnalysis" 
                WHERE "userId" = :userId 
                ORDER BY "createdAt" DESC 
                LIMIT :limit
            '''),
            {'userId': user_id, 'limit': limit}
        ).fetchall()
        
        games = []
        for row in rows:
            result = None
            if row[3]:
                try:
                    result = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                except:
                    result = row[3]
            
            games.append({
                'id': row[0],
                'gameId': row[1],
                'pgn': row[2][:200] + '...' if row[2] and len(row[2]) > 200 else row[2],
                'result': result,
                'createdAt': str(row[4])
            })
        
        return {'games': games, 'total': len(games)}
