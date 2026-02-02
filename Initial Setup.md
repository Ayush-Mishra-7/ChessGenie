Based on my research, I'll create a comprehensive roadmap for your chess analysis platform. This is a complex, full-stack project that requires careful planning across frontend, backend, and infrastructure.

# Chess Analysis Platform - Complete Development Roadmap

## Executive Summary

Your platform is a **SaaS chess analysis tool** that integrates with Lichess and Chess.com, providing AI-powered game analysis, puzzle generation, and subscription-based features. This roadmap covers architecture, tech stack, implementation phases, and detailed specifications.

***

## Recommended Tech Stack

### Frontend
- **Framework**: **Next.js 14+ (React)** with App Router
  - **Why**: Best for modern web apps, excellent SEO, hybrid rendering (SSR/SSG), built-in API routes, TypeScript support
  - Server Components reduce client-side JavaScript
  - Edge-ready for global deployment
  
### Backend
- **API Layer**: Next.js API Routes (serverless functions)
- **Chess Engine**: **Stockfish 17.1** (latest version)
  - Integration via Python wrapper or Node.js chess libraries
- **Secondary Backend** (for heavy processing): **Python FastAPI**
  - **Why**: Best for chess engine integration, async processing, ML-ready
  - Handles Stockfish analysis, puzzle generation algorithms

### Database
- **Primary Database**: **PostgreSQL** (managed via Supabase or AWS RDS)
  - **Why**: ACID compliance for transactions, complex queries, subscription management
  - Store: user accounts, API keys (encrypted), game history, analysis results, subscriptions
- **Cache Layer**: **Redis** (for session management, rate limiting)

### Authentication & Security
- **Auth**: **NextAuth.js v5** (Auth.js) or **Clerk**
  - OAuth 2.0 + JWT tokens
  - Secure session management
  - Email/password + social login options

### Payment Processing
- **Stripe** for subscriptions
  - Webhook integration for payment events
  - Support for tiered pricing (4 subscription levels)

### Chess Libraries
- **Frontend**: `chess.js` (move validation), `react-chessboard` (UI)
- **Backend**: `python-chess` (Stockfish integration, PGN parsing)

### Infrastructure
- **Hosting**: Vercel (Next.js) + AWS EC2/Lambda (Python FastAPI)
- **Storage**: AWS S3 (for game archives, analysis cache)
- **Queue System**: AWS SQS or BullMQ (for async game analysis)

***

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Login/Signup │  │  Dashboard   │  │ Analysis View│      │
│  │   (Auth)     │  │ (API Setup)  │  │  (Results)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                          │                                    │
└──────────────────────────┼────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Next.js API Routes (Orchestration)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  User Auth   │  │ Stripe API   │  │ Job Queue    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────┬─────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│   PostgreSQL     │ │    Redis     │ │ Python FastAPI       │
│                  │ │  (Cache)     │ │                      │
│ - Users          │ │              │ │ - Stockfish Engine   │
│ - API Keys       │ └──────────────┘ │ - Game Fetcher       │
│ - Game History   │                  │ - Analysis Algorithm │
│ - Subscriptions  │                  │ - Puzzle Generator   │
└──────────────────┘                  └──────────┬───────────┘
                                                  │
                           ┌──────────────────────┼──────────────────────┐
                           │                      │                      │
                           ▼                      ▼                      ▼
                   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
                   │ Lichess API  │      │Chess.com API │      │  Stockfish   │
                   │              │      │              │      │   Binary     │
                   └──────────────┘      └──────────────┘      └──────────────┘
```

***

## Detailed Feature Specifications

### 1. Secure User Login & Authentication

**Requirements:**
- Email/password authentication with password hashing (bcrypt)
- JWT-based session management
- OAuth support (optional: Google, GitHub)
- Email verification
- Password reset flow
- Rate limiting on login attempts

**Implementation:**
```typescript
// lib/auth.ts (NextAuth.js config)
import NextAuth from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { PrismaAdapter } from "@auth/prisma-adapter"
import { compare } from "bcrypt"
import prisma from "@/lib/prisma"

export const authOptions = {
  adapter: PrismaAdapter(prisma),
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Invalid credentials")
        }
        
        const user = await prisma.user.findUnique({
          where: { email: credentials.email }
        })
        
        if (!user || !user.hashedPassword) {
          throw new Error("Invalid credentials")
        }
        
        const isValid = await compare(credentials.password, user.hashedPassword)
        
        if (!isValid) {
          throw new Error("Invalid credentials")
        }
        
        return {
          id: user.id,
          email: user.email,
          name: user.name,
        }
      }
    })
  ],
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  pages: {
    signIn: '/login',
    error: '/login',
  }
}
```

**Database Schema (Prisma):**
```prisma
model User {
  id              String   @id @default(cuid())
  email           String   @unique
  hashedPassword  String?
  name            String?
  emailVerified   DateTime?
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt
  
  apiKeys         ApiKey[]
  analyses        GameAnalysis[]
  subscription    Subscription?
}
```

***

### 2. API Key Management (Lichess & Chess.com)

**Requirements:**
- Securely store API keys (encrypted at rest)
- Validate API keys against platform APIs
- UI for adding/removing API keys
- Support for multiple chess platforms per user
- Test connection feature

**Database Schema:**
```prisma
model ApiKey {
  id          String   @id @default(cuid())
  userId      String
  platform    Platform @default(LICHESS)
  username    String
  apiKey      String   // Encrypted
  isValid     Boolean  @default(true)
  lastChecked DateTime @default(now())
  createdAt   DateTime @default(now())
  
  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  
  @@unique([userId, platform])
}

enum Platform {
  LICHESS
  CHESS_COM
}
```

**Encryption Implementation:**
```typescript
// lib/encryption.ts
import crypto from 'crypto'

const algorithm = 'aes-256-gcm'
const secretKey = Buffer.from(process.env.ENCRYPTION_KEY!, 'hex') // 32-byte key

export function encrypt(text: string): string {
  const iv = crypto.randomBytes(16)
  const cipher = crypto.createCipheriv(algorithm, secretKey, iv)
  
  let encrypted = cipher.update(text, 'utf8', 'hex')
  encrypted += cipher.final('hex')
  
  const authTag = cipher.getAuthTag()
  
  return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`
}

export function decrypt(encryptedData: string): string {
  const [ivHex, authTagHex, encrypted] = encryptedData.split(':')
  
  const iv = Buffer.from(ivHex, 'hex')
  const authTag = Buffer.from(authTagHex, 'hex')
  
  const decipher = crypto.createDecipheriv(algorithm, secretKey, iv)
  decipher.setAuthTag(authTag)
  
  let decrypted = decipher.update(encrypted, 'hex', 'utf8')
  decrypted += decipher.final('utf8')
  
  return decrypted
}
```

**API Endpoints:**
```typescript
// app/api/apikeys/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { encrypt } from '@/lib/encryption'
import prisma from '@/lib/prisma'

// POST: Add new API key
export async function POST(req: NextRequest) {
  const session = await getServerSession()
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  
  const { platform, username, apiKey } = await req.json()
  
  // Validate API key against platform
  const isValid = await validateApiKey(platform, username, apiKey)
  if (!isValid) {
    return NextResponse.json({ error: 'Invalid API key' }, { status: 400 })
  }
  
  // Encrypt and store
  const encryptedKey = encrypt(apiKey)
  
  const user = await prisma.user.findUnique({
    where: { email: session.user.email }
  })
  
  const savedKey = await prisma.apiKey.create({
    data: {
      userId: user!.id,
      platform,
      username,
      apiKey: encryptedKey,
      isValid: true
    }
  })
  
  return NextResponse.json({ success: true, id: savedKey.id })
}
```

***

### 3. Game Fetching & Analysis Engine

**Requirements:**
- Fetch last N games from Lichess/Chess.com APIs
- Parse PGN format games
- Queue games for Stockfish analysis
- Store analysis results
- Progress tracking for long-running analysis

**Python FastAPI Backend (analysis-service):**

```python
# main.py (FastAPI)
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import chess
import chess.pgn
import chess.engine
from io import StringIO
import requests

app = FastAPI()

# Stockfish engine path
ENGINE_PATH = "/usr/local/bin/stockfish"

class AnalysisRequest(BaseModel):
    user_id: str
    platform: str
    username: str
    game_limit: int
    analysis_depth: int = 20

class GameAnalysis(BaseModel):
    game_id: str
    white: str
    black: str
    result: str
    opening: str
    best_move: Optional[dict]
    critical_moments: List[dict]
    mistakes: List[dict]
    accuracy_white: float
    accuracy_black: float

@app.post("/analyze/games")
async def analyze_games(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    # Fetch games from platform API
    games = await fetch_games(request.platform, request.username, request.game_limit)
    
    # Queue analysis job
    job_id = f"{request.user_id}_{request.platform}_{int(time.time())}"
    background_tasks.add_task(
        analyze_games_task,
        job_id,
        games,
        request.analysis_depth
    )
    
    return {"job_id": job_id, "status": "queued", "total_games": len(games)}

async def fetch_games(platform: str, username: str, limit: int) -> List[str]:
    """Fetch games from Lichess or Chess.com API"""
    if platform == "LICHESS":
        # Lichess API: https://lichess.org/api/games/user/{username}
        url = f"https://lichess.org/api/games/user/{username}"
        params = {
            "max": limit,
            "pgnInJson": "true",
            "clocks": "false",
            "evals": "false",
            "opening": "true"
        }
        response = requests.get(url, params=params, stream=True)
        games = []
        for line in response.iter_lines():
            if line:
                game_data = json.loads(line)
                games.append(game_data['pgn'])
        return games
    
    elif platform == "CHESS_COM":
        # Chess.com API: Get archives first
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        archives_response = requests.get(archives_url)
        archives = archives_response.json()['archives']
        
        games = []
        # Get most recent archives until we have enough games
        for archive_url in reversed(archives):
            if len(games) >= limit:
                break
            
            archive_response = requests.get(archive_url)
            archive_games = archive_response.json()['games']
            
            for game in archive_games:
                if len(games) >= limit:
                    break
                games.append(game['pgn'])
        
        return games[:limit]

async def analyze_games_task(job_id: str, pgn_games: List[str], depth: int):
    """Background task to analyze all games"""
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
    
    analyses = []
    
    for i, pgn_text in enumerate(pgn_games):
        pgn = chess.pgn.read_game(StringIO(pgn_text))
        if not pgn:
            continue
        
        # Analyze game
        analysis = await analyze_single_game(engine, pgn, depth)
        analyses.append(analysis)
        
        # Update progress in database
        await update_job_progress(job_id, i + 1, len(pgn_games))
    
    engine.quit()
    
    # Store results in PostgreSQL via API
    await store_analysis_results(job_id, analyses)

async def analyze_single_game(
    engine: chess.engine.SimpleEngine,
    pgn: chess.pgn.Game,
    depth: int
) -> GameAnalysis:
    """Analyze a single chess game with Stockfish"""
    board = pgn.board()
    moves = list(pgn.mainline_moves())
    
    best_move_analysis = None
    critical_moments = []
    mistakes = []
    
    position_scores = []
    previous_score = 0
    
    for move_number, move in enumerate(moves):
        # Get engine evaluation BEFORE the move
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        current_score = info["score"].relative.score(mate_score=10000)
        
        # Get best move suggestion
        best_move = info.get("pv")[0] if "pv" in info else None
        
        # Check if this is a mistake (eval drops significantly)
        if move_number > 0:
            score_drop = previous_score - current_score
            
            if score_drop > 100:  # Mistake threshold (1 pawn)
                mistakes.append({
                    "move_number": move_number,
                    "move_played": move.uci(),
                    "best_move": best_move.uci() if best_move else None,
                    "score_drop": score_drop,
                    "position_fen": board.fen()
                })
            
            # Critical moment: eval swing > 200 centipawns
            if abs(score_drop) > 200:
                critical_moments.append({
                    "move_number": move_number,
                    "eval_before": previous_score,
                    "eval_after": current_score,
                    "position_fen": board.fen()
                })
        
        # Track best move (highest eval advantage)
        if best_move_analysis is None or abs(current_score) > abs(best_move_analysis["eval"]):
            best_move_analysis = {
                "move_number": move_number,
                "move": move.uci(),
                "eval": current_score,
                "position_fen": board.fen()
            }
        
        position_scores.append(current_score)
        previous_score = current_score
        
        # Play the move
        board.push(move)
    
    # Calculate accuracy (percentage of moves within 50cp of best)
    accuracy_threshold = 50
    white_accurate = sum(1 for i, score in enumerate(position_scores) 
                        if i % 2 == 0 and abs(score - position_scores[i-1]) < accuracy_threshold 
                        if i > 0)
    black_accurate = sum(1 for i, score in enumerate(position_scores) 
                        if i % 2 == 1 and abs(score - position_scores[i-1]) < accuracy_threshold)
    
    white_moves = (len(moves) + 1) // 2
    black_moves = len(moves) // 2
    
    accuracy_white = (white_accurate / white_moves * 100) if white_moves > 0 else 0
    accuracy_black = (black_accurate / black_moves * 100) if black_moves > 0 else 0
    
    return GameAnalysis(
        game_id=pgn.headers.get("Site", "").split("/")[-1],
        white=pgn.headers.get("White", "Unknown"),
        black=pgn.headers.get("Black", "Unknown"),
        result=pgn.headers.get("Result", "*"),
        opening=pgn.headers.get("Opening", "Unknown"),
        best_move=best_move_analysis,
        critical_moments=critical_moments[:10],  # Top 10
        mistakes=mistakes,
        accuracy_white=round(accuracy_white, 1),
        accuracy_black=round(accuracy_black, 1)
    )

@app.get("/analyze/status/{job_id}")
async def get_analysis_status(job_id: str):
    """Check analysis job status"""
    # Query job status from database
    status = await get_job_status_from_db(job_id)
    return status
```

***

### 4. Puzzle Generation from Mistakes

**Requirements:**
- Identify critical positions from mistakes
- Generate tactical puzzles with solution paths
- Ensure puzzle quality (has clear best move)
- Generate 25 puzzles per analysis
- Store puzzles with explanations

**Puzzle Generation Algorithm:**

```python
# puzzle_generator.py
from typing import List, Dict
import chess
import chess.engine

class PuzzleGenerator:
    def __init__(self, engine_path: str):
        self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    
    async def generate_puzzles_from_mistakes(
        self,
        mistakes: List[Dict],
        target_count: int = 25
    ) -> List[Dict]:
        """Generate training puzzles from player mistakes"""
        puzzles = []
        
        for mistake in mistakes:
            # Load position one move BEFORE the mistake
            board = chess.Board(mistake["position_fen"])
            
            # Verify there's a clear tactical solution
            puzzle = await self._create_puzzle(board, mistake)
            
            if puzzle and puzzle["is_valid"]:
                puzzles.append(puzzle)
            
            if len(puzzles) >= target_count:
                break
        
        # If not enough puzzles, generate similar positions
        if len(puzzles) < target_count:
            additional = await self._generate_similar_puzzles(
                mistakes,
                target_count - len(puzzles)
            )
            puzzles.extend(additional)
        
        return puzzles[:target_count]
    
    async def _create_puzzle(self, board: chess.Board, mistake_context: Dict) -> Dict:
        """Create a puzzle from a position"""
        # Analyze position deeply
        info = self.engine.analyse(board, chess.engine.Limit(depth=25))
        
        best_move = info["pv"][0] if "pv" in info else None
        if not best_move:
            return None
        
        # Check if puzzle is tactical (has a forcing sequence)
        board_copy = board.copy()
        board_copy.push(best_move)
        
        # Verify the best move is significantly better than alternatives
        best_score = info["score"].relative.score(mate_score=10000)
        
        # Get second best move
        legal_moves = list(board.legal_moves)
        legal_moves.remove(best_move)
        
        if not legal_moves:
            return None
        
        second_best_score = -999999
        for move in legal_moves[:5]:  # Check top 5 alternatives
            test_board = board.copy()
            test_board.push(move)
            test_info = self.engine.analyse(test_board, chess.engine.Limit(depth=15))
            score = test_info["score"].relative.score(mate_score=10000)
            second_best_score = max(second_best_score, score)
        
        # Puzzle is valid if best move is significantly better (2+ pawns)
        is_valid = (best_score - second_best_score) > 200
        
        # Generate explanation
        explanation = self._generate_explanation(board, best_move, info)
        
        # Get solution line (3-5 moves)
        solution_line = info["pv"][:5] if "pv" in info else [best_move]
        
        return {
            "fen": board.fen(),
            "best_move": best_move.uci(),
            "solution_line": [move.uci() for move in solution_line],
            "theme": self._identify_theme(board, best_move),
            "difficulty": self._calculate_difficulty(best_score, second_best_score),
            "explanation": explanation,
            "is_valid": is_valid,
            "original_mistake": mistake_context["move_played"]
        }
    
    def _identify_theme(self, board: chess.Board, move: chess.Move) -> str:
        """Identify tactical theme of the puzzle"""
        piece = board.piece_at(move.from_square)
        target = board.piece_at(move.to_square)
        
        # Check for common themes
        if board.is_check():
            return "checkmate" if board.is_checkmate() else "check"
        
        if target:  # Capture
            if piece and piece.piece_type == chess.QUEEN:
                return "queen_sacrifice"
            return "capturing"
        
        # Check for fork patterns
        if self._is_fork(board, move):
            return "fork"
        
        # Check for pin
        if self._creates_pin(board, move):
            return "pin"
        
        # Check for discovered attack
        if self._is_discovered_attack(board, move):
            return "discovered_attack"
        
        return "tactic"
    
    def _is_fork(self, board: chess.Board, move: chess.Move) -> bool:
        """Check if move creates a fork"""
        test_board = board.copy()
        test_board.push(move)
        
        piece = test_board.piece_at(move.to_square)
        if not piece:
            return False
        
        attacks = test_board.attacks(move.to_square)
        valuable_pieces = 0
        
        for square in attacks:
            target_piece = test_board.piece_at(square)
            if target_piece and target_piece.color != piece.color:
                if target_piece.piece_type in [chess.ROOK, chess.QUEEN, chess.KING]:
                    valuable_pieces += 1
        
        return valuable_pieces >= 2
    
    def _calculate_difficulty(self, best_score: int, second_best: int) -> str:
        """Calculate puzzle difficulty based on eval difference"""
        diff = best_score - second_best
        
        if diff > 500:
            return "easy"
        elif diff > 300:
            return "medium"
        else:
            return "hard"
    
    def _generate_explanation(
        self,
        board: chess.Board,
        move: chess.Move,
        engine_info: Dict
    ) -> str:
        """Generate human-readable explanation"""
        piece = board.piece_at(move.from_square)
        piece_name = chess.piece_name(piece.piece_type).capitalize()
        
        target = board.piece_at(move.to_square)
        
        # Basic move description
        move_san = board.san(move)
        explanation = f"The best move is {move_san}. "
        
        # Add tactical explanation
        if target:
            target_name = chess.piece_name(target.piece_type)
            explanation += f"This captures the opponent's {target_name}. "
        
        if board.gives_check(move):
            explanation += "This puts the opponent in check. "
        
        # Add follow-up
        if "pv" in engine_info and len(engine_info["pv"]) > 1:
            test_board = board.copy()
            test_board.push(move)
            next_move_san = test_board.san(engine_info["pv"] [reddit](https://www.reddit.com/r/chessbeginners/comments/152087c/use_lichess_for_analysis_and_chesscom_to_play_the/))
            explanation += f"After the opponent's likely response {next_move_san}, you maintain a strong advantage."
        
        return explanation
    
    def __del__(self):
        if hasattr(self, 'engine'):
            self.engine.quit()
```

***

### 5. Frontend Dashboard & UI Components

**Key Pages:**

1. **Login/Signup** (`/login`, `/signup`)
2. **Dashboard** (`/dashboard`) - Overview, API setup, subscription status
3. **Analysis View** (`/analysis`) - View analysis results, top games, mistakes
4. **Puzzle Trainer** (`/puzzles`) - Interactive puzzle solving
5. **Subscription** (`/subscription`) - Manage payment and plan

**Dashboard Component:**

```typescript
// app/dashboard/page.tsx
import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import ApiKeyManager from '@/components/ApiKeyManager'
import AnalysisHistory from '@/components/AnalysisHistory'
import SubscriptionBanner from '@/components/SubscriptionBanner'

export default async function DashboardPage() {
  const session = await getServerSession()
  
  if (!session) {
    redirect('/login')
  }
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-4xl font-bold mb-8">Chess Analysis Dashboard</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* API Key Management */}
        <div className="lg:col-span-2">
          <ApiKeyManager />
        </div>
        
        {/* Subscription Status */}
        <div>
          <SubscriptionBanner />
        </div>
      </div>
      
      {/* Recent Analysis */}
      <div className="mt-8">
        <AnalysisHistory />
      </div>
      
      {/* Start New Analysis Button */}
      <div className="mt-8 text-center">
        <button className="btn btn-primary btn-lg">
          Analyze My Games
        </button>
      </div>
    </div>
  )
}
```

**Interactive Chessboard Component:**

```typescript
// components/InteractiveBoard.tsx
'use client'

import { useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { Chess } from 'chess.js'

interface InteractiveBoardProps {
  initialFen: string
  solutionMoves: string[]
  onSolved: () => void
  showExplanation: boolean
}

export default function InteractiveBoard({
  initialFen,
  solutionMoves,
  onSolved,
  showExplanation
}: InteractiveBoardProps) {
  const [game, setGame] = useState(new Chess(initialFen))
  const [moveIndex, setMoveIndex] = useState(0)
  const [feedback, setFeedback] = useState<string | null>(null)
  
  function onDrop(sourceSquare: string, targetSquare: string) {
    const move = game.move({
      from: sourceSquare,
      to: targetSquare,
      promotion: 'q' // Always promote to queen for simplicity
    })
    
    // Illegal move
    if (move === null) {
      setFeedback('Illegal move!')
      return false
    }
    
    // Check if move matches solution
    const expectedMove = solutionMoves[moveIndex]
    if (move.from + move.to !== expectedMove) {
      setFeedback('Not the best move. Try again!')
      game.undo()
      setGame(new Chess(game.fen()))
      return false
    }
    
    // Correct move!
    setFeedback('Correct! ')
    setMoveIndex(moveIndex + 1)
    setGame(new Chess(game.fen()))
    
    // Check if puzzle is solved
    if (moveIndex + 1 >= solutionMoves.length) {
      setFeedback('Puzzle solved! Great job! ')
      onSolved()
    } else {
      // Make opponent's response
      setTimeout(() => {
        if (solutionMoves[moveIndex + 1]) {
          const responseMove = solutionMoves[moveIndex + 1]
          game.move({
            from: responseMove.substring(0, 2),
            to: responseMove.substring(2, 4)
          })
          setMoveIndex(moveIndex + 2)
          setGame(new Chess(game.fen()))
        }
      }, 500)
    }
    
    return true
  }
  
  return (
    <div className="flex flex-col items-center">
      <div className="w-full max-w-xl">
        <Chessboard
          position={game.fen()}
          onPieceDrop={onDrop}
          boardWidth={560}
        />
      </div>
      
      {feedback && (
        <div className={`mt-4 p-4 rounded-lg ${
          feedback.includes('Correct') || feedback.includes('solved')
            ? 'bg-green-100 text-green-800'
            : 'bg-red-100 text-red-800'
        }`}>
          {feedback}
        </div>
      )}
    </div>
  )
}
```

***

### 6. Subscription & Payment Integration

**Subscription Tiers:**

| Tier | Games Analyzed | Price | Type |
|------|---------------|-------|------|
| **Free** | Last 50 games | $0 | One-time |
| **Basic** | Last 100 games | $20 | One-time |
| **Pro** | Last 200 games | $30 | One-time |
| **Ultimate** | Last 500 games | $50 | One-time |
| **Premium Monthly** | Last 100 games daily | $10/month | Recurring |

**Database Schema:**

```prisma
model Subscription {
  id            String   @id @default(cuid())
  userId        String   @unique
  tier          SubscriptionTier
  status        SubscriptionStatus
  stripeCustomerId     String?
  stripeSubscriptionId String?
  currentPeriodStart   DateTime?
  currentPeriodEnd     DateTime?
  cancelAtPeriodEnd    Boolean  @default(false)
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  
  user          User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}

enum SubscriptionTier {
  FREE
  BASIC
  PRO
  ULTIMATE
  PREMIUM_MONTHLY
}

enum SubscriptionStatus {
  ACTIVE
  CANCELED
  EXPIRED
  PAST_DUE
}
```

**Stripe Integration:**

```typescript
// app/api/stripe/checkout/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import Stripe from 'stripe'
import prisma from '@/lib/prisma'

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2024-12-18.acacia'
})

export async function POST(req: NextRequest) {
  const session = await getServerSession()
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  
  const { tier } = await req.json()
  
  const user = await prisma.user.findUnique({
    where: { email: session.user.email }
  })
  
  // Price mapping
  const prices = {
    BASIC: { amount: 2000, type: 'payment' },
    PRO: { amount: 3000, type: 'payment' },
    ULTIMATE: { amount: 5000, type: 'payment' },
    PREMIUM_MONTHLY: { priceId: process.env.STRIPE_PREMIUM_PRICE_ID, type: 'subscription' }
  }
  
  const priceInfo = prices[tier as keyof typeof prices]
  
  if (priceInfo.type === 'payment') {
    // One-time payment
    const checkoutSession = await stripe.checkout.sessions.create({
      mode: 'payment',
      payment_method_types: ['card'],
      line_items: [
        {
          price_data: {
            currency: 'usd',
            product_data: {
              name: `Chess Analysis - ${tier}`,
              description: `Analyze your chess games`
            },
            unit_amount: priceInfo.amount
          },
          quantity: 1
        }
      ],
      success_url: `${process.env.NEXT_PUBLIC_BASE_URL}/dashboard?success=true`,
      cancel_url: `${process.env.NEXT_PUBLIC_BASE_URL}/subscription?canceled=true`,
      metadata: {
        userId: user!.id,
        tier
      }
    })
    
    return NextResponse.json({ url: checkoutSession.url })
  } else {
    // Recurring subscription
    const checkoutSession = await stripe.checkout.sessions.create({
      mode: 'subscription',
      payment_method_types: ['card'],
      line_items: [
        {
          price: priceInfo.priceId,
          quantity: 1
        }
      ],
      success_url: `${process.env.NEXT_PUBLIC_BASE_URL}/dashboard?success=true`,
      cancel_url: `${process.env.NEXT_PUBLIC_BASE_URL}/subscription?canceled=true`,
      metadata: {
        userId: user!.id,
        tier
      }
    })
    
    return NextResponse.json({ url: checkoutSession.url })
  }
}
```

**Stripe Webhook Handler:**

```typescript
// app/api/stripe/webhook/route.ts
import { NextRequest, NextResponse } from 'next/server'
import Stripe from 'stripe'
import { headers } from 'next/headers'
import prisma from '@/lib/prisma'

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)

export async function POST(req: NextRequest) {
  const body = await req.text()
  const signature = headers().get('stripe-signature')!
  
  let event: Stripe.Event
  
  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    )
  } catch (err) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 })
  }
  
  // Handle events
  switch (event.type) {
    case 'checkout.session.completed':
      const session = event.data.object as Stripe.Checkout.Session
      await handleCheckoutComplete(session)
      break
      
    case 'customer.subscription.updated':
      const subscription = event.data.object as Stripe.Subscription
      await handleSubscriptionUpdate(subscription)
      break
      
    case 'customer.subscription.deleted':
      const deletedSub = event.data.object as Stripe.Subscription
      await handleSubscriptionCanceled(deletedSub)
      break
  }
  
  return NextResponse.json({ received: true })
}

async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const userId = session.metadata?.userId
  const tier = session.metadata?.tier
  
  if (!userId || !tier) return
  
  // Update subscription in database
  await prisma.subscription.upsert({
    where: { userId },
    create: {
      userId,
      tier: tier as any,
      status: 'ACTIVE',
      stripeCustomerId: session.customer as string,
      stripeSubscriptionId: session.subscription as string
    },
    update: {
      tier: tier as any,
      status: 'ACTIVE',
      stripeCustomerId: session.customer as string,
      stripeSubscriptionId: session.subscription as string
    }
  })
}
```

***

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
1. Set up Next.js project with TypeScript
2. Configure PostgreSQL database (Supabase/AWS RDS)
3. Implement authentication (NextAuth.js)
4. Create basic UI shell (dashboard, layout)
5. Set up Prisma ORM and migrations

**Deliverables:**
- Working login/signup flow
- Database schema deployed
- Basic dashboard skeleton

***

### Phase 2: API Integration (Weeks 3-4)
1. Build API key management system
2. Implement encryption for API keys
3. Integrate Lichess API for game fetching
4. Integrate Chess.com API for game fetching
5. Create API key validation endpoints

**Deliverables:**
- Users can add/remove Lichess and Chess.com API keys
- Test connection feature working
- Games can be fetched from both platforms

***

### Phase 3: Analysis Engine (Weeks 5-7)
1. Set up Python FastAPI backend service
2. Integrate Stockfish chess engine
3. Implement game analysis algorithm
4. Create job queue system for long-running analysis
5. Calculate metrics (best moves, accuracy, critical moments)
6. Store analysis results in PostgreSQL

**Deliverables:**
- Working analysis service
- Can analyze 50 games with Stockfish
- Results stored and retrievable
- Progress tracking for analysis jobs

***

### Phase 4: Puzzle Generation (Weeks 8-9)
1. Implement puzzle generation algorithm
2. Identify tactical themes
3. Validate puzzle quality
4. Generate 25 puzzles from mistakes
5. Create explanations for moves

**Deliverables:**
- 25 puzzles generated per analysis
- Puzzles have clear solutions
- Explanations are accurate and helpful

***

### Phase 5: Frontend Polish & Interactivity (Weeks 10-11)
1. Build analysis results display
2. Create top 5 games showcase
3. Implement interactive puzzle trainer
4. Add chessboard visualization
5. Show mistake analysis and critical moments

**Deliverables:**
- Beautiful UI for analysis results
- Interactive puzzle solving
- Top games display with annotations

***

### Phase 6: Payment & Subscriptions (Weeks 12-13)
1. Integrate Stripe payment gateway
2. Create subscription tiers
3. Implement webhook handlers
4. Build subscription management UI
5. Add usage limits based on tier

**Deliverables:**
- Working payment flow
- 4 one-time tiers + 1 monthly subscription
- Subscription status visible in dashboard
- Usage enforcement

***

### Phase 7: Testing & Deployment (Weeks 14-15)
1. Write unit tests (Jest, Pytest)
2. Integration testing
3. Load testing for analysis service
4. Security audit
5. Deploy to production (Vercel + AWS)
6. Set up monitoring (Sentry, LogRocket)

**Deliverables:**
- Production-ready application
- CI/CD pipeline configured
- Monitoring and error tracking active

***

## Security Considerations

1. **API Key Protection:**
   - Encrypt all API keys with AES-256-GCM
   - Store encryption key in environment variable (AWS Secrets Manager)
   - Never log decrypted keys

2. **Authentication:**
   - Use bcrypt for password hashing (cost factor: 12)
   - Implement rate limiting on login (5 attempts per 15 minutes)
   - JWT tokens with 30-day expiration
   - HttpOnly cookies for session management

3. **Authorization:**
   - Row-level security in PostgreSQL
   - Verify user owns resources before access
   - Subscription tier checks on analysis requests

4. **Payment Security:**
   - PCI compliance through Stripe
   - Webhook signature verification
   - Never store credit card data

5. **Rate Limiting:**
   - API endpoints: 100 requests/minute per user
   - Analysis requests: Based on subscription tier
   - Use Redis for distributed rate limiting

***

## Scalability Plan

### Immediate Scale (0-1000 users)
- Vercel hosting (Next.js)
- AWS EC2 t3.medium for Python FastAPI
- PostgreSQL on Supabase (or AWS RDS)
- Single Stockfish instance

### Medium Scale (1000-10,000 users)
- Auto-scaling EC2 instances
- AWS SQS for job queue
- Multiple Stockfish workers
- Redis for caching and rate limiting
- CDN for static assets

### Large Scale (10,000+ users)
- Kubernetes for microservices
- Separate analysis worker pool
- Read replicas for PostgreSQL
- ElastiCache Redis cluster
- CloudFront CDN

***

## Cost Estimation (Monthly)

**For 1,000 users:**
- Vercel Pro: $20
- AWS EC2 (t3.medium): $30
- Supabase Pro: $25
- Redis (AWS ElastiCache): $15
- Stripe fees: ~2.9% + $0.30 per transaction
- **Total: ~$90/month + transaction fees**

**For 10,000 users:**
- Vercel Enterprise: $150
- AWS infrastructure: $300-500
- Database: $150
- Redis: $50
- **Total: ~$650-850/month + transaction fees**

***

## Environment Variables Checklist

```bash
# .env.local

# Database
DATABASE_URL="postgresql://..."

# Authentication
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="generate-with-openssl-rand-base64-32"

# Encryption
ENCRYPTION_KEY="generate-with-openssl-rand-hex-32"

# Stripe
STRIPE_SECRET_KEY="sk_test_..."
STRIPE_PUBLISHABLE_KEY="pk_test_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
STRIPE_PREMIUM_PRICE_ID="price_..."

# External APIs
LICHESS_API_URL="https://lichess.org/api"
CHESS_COM_API_URL="https://api.chess.com/pub"

# Python Backend
ANALYSIS_SERVICE_URL="http://localhost:8000"

# Stockfish
STOCKFISH_PATH="/usr/local/bin/stockfish"
```

***

## Quick Start Commands

```bash
# Clone and setup Next.js frontend
npx create-next-app@latest chess-analysis --typescript --tailwind --app
cd chess-analysis
npm install next-auth @prisma/client bcrypt stripe chess.js react-chessboard

# Setup Prisma
npx prisma init
npx prisma generate
npx prisma migrate dev --name init

# Run development server
npm run dev

# Setup Python backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-chess requests pydantic sqlalchemy

# Run Python service
uvicorn main:app --reload --port 8000
```

***

## Summary

This roadmap provides a **production-ready** chess analysis platform with:

✅ Secure authentication & API key management  
✅ Integration with Lichess and Chess.com APIs  
✅ Stockfish-powered game analysis  
✅ AI-generated tactical puzzles from mistakes  
✅ Interactive puzzle trainer  
✅ 4-tier subscription system with Stripe  
✅ Scalable architecture  
✅ Security best practices  

**Recommended Timeline:** 15 weeks for MVP  
**Tech Stack:** Next.js + PostgreSQL + Python FastAPI + Stockfish  
**Estimated Cost:** $90-850/month depending on scale

This architecture separates concerns cleanly: Next.js handles UI and API orchestration, PostgreSQL manages data persistence, Python FastAPI handles compute-intensive chess analysis, and Stripe manages payments. The system is designed to scale horizontally as user demand grows.
