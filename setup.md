# ChessGenie Setup Guide

Follow these steps to set up and run the ChessGenie application (Frontend + Backend).

## Prerequisites

- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)
- **PostgreSQL** (Running locally or hosted)

## 1. Environment Configuration

### Frontend (.env)
The frontend (Next.js) and database migration tool (Prisma) read from the root `.env` file.

1. Copy the example file in the root directory:
   ```bash
   cp .env.example .env
   ```
   *(On Windows Command Prompt: `copy .env.example .env`)*

2. Open `.env` and configure your variables, especially:
   - `DATABASE_URL`: Connection string for your PostgreSQL database.
   - `NEXTAUTH_SECRET`: Generate a random string (e.g., `openssl rand -base64 32`).
   - `ENCRYPTION_KEY`: A 32-byte hex string for API key encryption.

### Backend (.env)
The Python backend needs its own environment variables, specifically to connect to the database.

1. Create a `.env` file in the `backend/` directory.
2. Add the `DATABASE_URL` to it (same as in the root `.env`):
   ```properties
   DATABASE_URL="postgresql://user:password@localhost:5432/chessgenie"
   # Add other backend-specific variables if needed
   ```

## 2. Install Dependencies

### Frontend
Install Node.js dependencies:
```bash
npm install
```

### Backend
It is recommended to use a Python virtual environment.

1. **Create and activate venv**:
   
   *Windows (PowerShell):*
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate
   ```

   *macOS/Linux:*
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Python packages**:
   ```bash
   pip install -r backend/requirements.txt
   ```

## 3. Database Setup

Initialize the database schema using Prisma. This will create the tables in your PostgreSQL database.

```bash
npm run prisma:migrate
```

## 4. Running the Application

### Start Frontend (Next.js)
Runs on `http://localhost:3000`.

```bash
npm run dev
```

### Start Backend (FastAPI)
Runs on `http://localhost:8000`.

You can run the backend using the provided npm script (from the root directory):
```bash
npm run backend
```

*Note: Ensure your Python virtual environment is active if you installed dependencies there, or that the `python` in your path has the requirements installed.*

Alternatively, run directly with Python:
```bash
uvicorn backend.main:app --reload --port 8000
```
