# StackOverflow Scraper API

An automated web scraping system built with FastAPI and DrissionPage to extract, store, and export StackOverflow-style question data into a PostgreSQL database.

## Setup (Linux)

```bash
# Create virtual environment
python3 -m venv venv

#
# Activate environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## How to Run

```bash
uvicorn main:app --reload
```

## How to Use

### 1. Scrape Questions
Triggers the scraper to crawl specific pages and store results in the database.
```bash
curl -X POST http://localhost:8000/parse \
-H "Content-Type: application/json" \
-d '{
"url": "https://stackoverflow.com/questions?tab=newest",
"start_page": 1,
"end_page": 2,
"max_questions": 30
}'
```

### 2. Check Database Statistics
Returns the total number of questions currently stored in the database.
```bash
curl http://localhost:8000/stats
```

### 3. Retrieve Recent Questions
Fetches the last $N$ questions from the database.
```bash
curl http://localhost:8000/questions/last/10
```

### 4. Export Data to JSON
Exports the most recent questions to a specified JSON file.
```bash
curl -X POST http://localhost:8000/export \
-H "Content-Type: application/json" \
-d '{
"filename": "my_questions.json",
"limit": 15
}'
```

### 5. Test Scrape
Runs a hardcoded scraping task with default parameters to verify system functionality.
```bash
curl http://localhost:8000/test-scrape
```

### 6. Health Check
Checks the operational status of the API.
```bash
curl http://localhost:8000/health
```
