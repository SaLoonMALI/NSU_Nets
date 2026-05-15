# main.py Python-3.11.14
# Sam Lunev. 2026. All Rights Reserved
import time
import asyncio
import logging
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from worker import parse_and_store, SessionLocal, ScrapedQuestion, get_last_n_questions, export_questions_to_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


class ParseRequest(BaseModel):
    url: str
    start_page: int = 1
    end_page: int = 3
    max_questions: int = 100


class ExportRequest(BaseModel):
    filename: str
    limit: int = 50


@app.post("/parse")
async def parse_url(request: ParseRequest):
    try:
        logger.info(f"Starting parse request for URL: {request.url}")
        logger.info(
            f"Scraping pages {request.start_page} to {request.end_page}")
        await parse_and_store(request.url, request.start_page,
                              request.end_page, request.max_questions)
        logger.info("Parse request completed successfully")
        return {
            "status": "success",
            "message":
            f"Data scraped from pages {request.start_page}-{request.end_page}",
            "questions_count": request.max_questions
        }
    except Exception as e:
        logger.error(f"Parse request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/questions")
async def get_all_questions():
    db = SessionLocal()
    try:
        questions = db.query(ScrapedQuestion).all()
        return {"questions": [q.__dict__ for q in questions]}
    except Exception as e:
        logger.error(f"Failed to fetch questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/questions/last/{limit}")
async def get_last_questions(limit: int):
    questions = get_last_n_questions(limit)
    return {"questions": questions}


@app.post("/export")
async def export_questions(request: ExportRequest):
    try:
        filename = export_questions_to_json(request.limit, request.filename)
        return {
            "message": f"Questions exported to {filename}",
            "count": request.limit
        }
    except Exception as e:
        logger.error(f"Failed to export questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    db = SessionLocal()
    try:
        total_questions = db.query(ScrapedQuestion).count()
        return {"total_questions": total_questions}
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/test-scrape")
async def test_scrape():
    try:
        test_url = "https://stackoverflow.com/questions?tab=newest&page=1"
        await parse_and_store(test_url, 1, 1, 5)
        return {"message": "Test scrape completed successfully"}
    except Exception as e:
        logger.error(f"Test scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
