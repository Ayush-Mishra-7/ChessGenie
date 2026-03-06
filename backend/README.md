# ChessGenie - Analysis Service (backend)

This folder contains a minimal FastAPI skeleton for the analysis service. It is a starting point for implementing Stockfish-driven analysis jobs.

Run locally (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

The service exposes a simple health endpoint at `/health` and a placeholder `/analyze/games` POST endpoint.

Similar-position generation benchmark:

```powershell
python -m backend.benchmark_similar_positions --count 8 --timeout 10
python -m backend.benchmark_similar_positions --json
python -m backend.benchmark_similar_positions --verbose
```

The benchmark prints aggregate latency, acceptance, motif-preservation, novelty, accepted methods, and structured rejection reasons from the generator.
