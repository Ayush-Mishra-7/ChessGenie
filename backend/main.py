from fastapi import FastAPI

app = FastAPI(title="ChessGenie Analysis Service")


@app.get("/")
async def root():
    return {"status": "ok", "service": "chessgenie-analysis"}


@app.get("/health")
async def health():
    return {"healthy": True}


@app.post("/analyze/games")
async def analyze_games_stub():
    # Placeholder endpoint for the analysis job queue
    return {"status": "queued", "message": "analysis service stub - implement later"}
