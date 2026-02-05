"""
Simple backend worker placeholder.
This script polls the database for queued jobs and would dispatch them to the analysis service.
It is a development helper and should be replaced by a robust worker (Redis queue, Celery/Bull, etc.) in production.
"""
import time
import os
import json
from typing import Any
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load backend/.env if present
base_dir = os.path.dirname(__file__)
env_path = os.path.join(base_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print('DATABASE_URL is not set. Worker cannot run.')
    exit(1)

engine = create_engine(DATABASE_URL, future=True)

def fetch_queued_job():
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, payload FROM \"Job\" WHERE status = 'QUEUED' ORDER BY \"createdAt\" ASC LIMIT 1"))
        row = res.first()
        if not row:
            return None
        return {'id': row[0], 'payload': json.loads(row[1])}

def mark_running(job_id: str):
    with engine.connect() as conn:
        conn.execute(text("UPDATE \"Job\" SET status = 'RUNNING', \"updatedAt\" = now() WHERE id = :id"), {'id': job_id})

def mark_completed(job_id: str, result: Any):
    with engine.connect() as conn:
        conn.execute(text("UPDATE \"Job\" SET status = 'COMPLETED', result = :result, \"updatedAt\" = now() WHERE id = :id"), {'id': job_id, 'result': json.dumps(result)})

def process_job(job):
    print('Processing job', job['id'], 'payload:', job['payload'])
    # Placeholder: call analysis microservice or local analysis logic here.
    time.sleep(2)
    return {'message': 'processed', 'job': job['id']}

def main():
    print('Worker started, polling for jobs...')
    try:
        while True:
            job = fetch_queued_job()
            if job:
                mark_running(job['id'])
                result = process_job(job)
                mark_completed(job['id'], result)
            else:
                time.sleep(3)
    except KeyboardInterrupt:
        print('Worker stopped')

if __name__ == '__main__':
    main()
