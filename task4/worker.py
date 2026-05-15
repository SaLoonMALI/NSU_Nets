# worker.py Python-3.11.14
# Sam Lunev. 2026. All Rights Reserved.
import asyncio
import logging
import time
import sys
import json
from urllib.parse import urlparse
from contextlib import contextmanager
from DrissionPage import ChromiumPage, ChromiumOptions
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

DATABASE_URL = "postgresql://stackoverflow_user:your_secure_password@localhost:5432/stackoverflow_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ScrapedQuestion(Base):
    __tablename__ = "scraped_questions"
    __table_args__ = {"schema": "stackoverflow_schema"}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    url = Column(String)
    raw_stats = Column(Text)
    text = Column(Text)


Base.metadata.create_all(bind=engine)


@contextmanager
def browser_session():
    options = ChromiumOptions()
    options.set_pref('profile.managed_default_content_settings.images', 2)
    options.set_pref('profile.managed_default_content_settings.popups', 2)
    options.set_pref('profile.managed_default_content_settings.javascript', 1)
    page = None
    try:
        print("[INFO] Initializing browser...")
        page = ChromiumPage(addr_or_opts=options)
        yield page
    except Exception as e:
        print(f"[FAIL] Critical Error in browser session: {e}",
              file=sys.stderr)
        raise
    finally:
        if page:
            print("\n[INFO] Closing browser session...")
            page.quit()


def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Invalid protocol. Only HTTP/HTTPS allowed.")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL format.")
    return True


async def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2**attempt)
            logging.warning(
                f"Attempt {attempt + 1} failed. Retrying in {delay}s...")
            await asyncio.sleep(delay)


def extract_stackoverflow_data(
        page,
        max_pages=8,
        target_limit=100,
        url="https://stackoverflow.com/questions?tab=newest&page="):
    all_scraped_data = []
    total_count = 0
    for page_number in range(1, max_pages + 1):
        if total_count >= target_limit:
            break
        current_url = url + f"{page_number}"
        print(f"[INFO] Navigating to {current_url}")
        page.get(current_url, timeout=25, retry=2, interval=4)
        if not wait_for_cookie(page, 'cf_clearance', timeout=15):
            print(f"[WARN] cf_clearance isn't loaded. Check JS/Cookies")
        print("[INFO] Wait for target element")
        sample_element = page.ele('.s-post-summary--content-excerpt',
                                  timeout=100)
        if not sample_element:
            print(
                "\n[FAIL] Could not find elements. Check if site structure changed or CF 'box' check\n"
            )
            return []
        print("\n[SUCCESS] Pattern Identified\n")
        questions = page.eles('.s-post-summary--content')
        print(f"[INFO] Found {len(questions)} questions")
        for q in questions:
            try:
                link_elem = q.ele('tag:a')
                link = link_elem.attr('href') if link_elem else "N/A"
                title = link_elem.text if link_elem else "No Title"
                stats = q.eles('tag:span')
                text = q.ele('.s-post-summary--content-excerpt').text if q.ele(
                    '.s-post-summary--content-excerpt') else ""
                item_data = {
                    "title":
                    title,
                    "url":
                    f"https://stackoverflow.com{link}"
                    if link.startswith('/') else link,
                    "raw_stats": [s.text for s in stats if s.text],
                    "text":
                    text
                }
                all_scraped_data.append(item_data)
                print(f"[INFO] -> Extracted: {title[:50]}.")
                total_count += 1
                if total_count >= target_limit:
                    break
            except Exception as e:
                print(f"[FAIL] Error while parsing an item: {e}")
                continue
    return all_scraped_data


def wait_for_cookie(page, cookie_name, timeout=10):
    start_time = time.time()
    print(f"[INFO] Waiting for cookie: '{cookie_name}'.")
    while time.time() - start_time < timeout:
        cookies = page.cookies()
        if any(cookie['name'] == cookie_name for cookie in cookies):
            print(f"[SUCCESS] Cookie '{cookie_name}' is present")
            return True
        time.sleep(0.5)
    print("[FAIL] Cookie waiting timeout reached")
    return False


async def parse_and_store(url: str,
                          start_page: int = 1,
                          end_page: int = 3,
                          max_questions: int = 100):
    validate_url(url)
    with browser_session() as page:
        base_url = url.split('?')[0] if '?' in url else url
        if 'page=' in url:
            page_number = int(
                url.split('page=')[1].split('&')[0]) if 'page=' in url else 1
            base_url = url.split('page=')[0] + 'page='
        else:
            base_url = base_url + '?page='

        data = extract_stackoverflow_data(page, end_page, max_questions,
                                          base_url)
        db = SessionLocal()
        try:
            for item in data:
                db_item = ScrapedQuestion(title=item["title"],
                                          url=item["url"],
                                          raw_stats="; ".join(
                                              item["raw_stats"]),
                                          text=item["text"])
                db.add(db_item)
            db.commit()
            logging.info(f"[SUCCESS] Stored {len(data)} items to DB.")
        except Exception as e:
            db.rollback()
            logging.error(f"[FAIL] Failed to store data: {e}")
            raise
        finally:
            db.close()


def get_last_n_questions(limit: int):
    """Get last N questions from database"""
    db = SessionLocal()
    try:
        questions = db.query(ScrapedQuestion).order_by(
            ScrapedQuestion.id.desc()).limit(limit).all()
        return [q.__dict__ for q in questions]
    except Exception as e:
        logging.error(f"Failed to fetch last {limit} questions: {e}")
        return []
    finally:
        db.close()


def export_questions_to_json(limit: int, filename: str):
    """Export last N questions to JSON file"""
    questions = get_last_n_questions(limit)

    serializable_questions = []
    for q in questions:
        q_dict = {k: v for k, v in q.items() if not k.startswith('_')}
        serializable_questions.append(q_dict)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(serializable_questions, f, ensure_ascii=False, indent=2)

    return filename


def get_question_count():
    """Get total count of questions in database"""
    db = SessionLocal()
    try:
        return db.query(ScrapedQuestion).count()
    except Exception as e:
        logging.error(f"Failed to get question count: {e}")
        return 0
    finally:
        db.close()


def get_questions_by_page(page: int, per_page: int = 10):
    """Get questions for a specific page"""
    db = SessionLocal()
    try:
        offset = (page - 1) * per_page
        questions = db.query(ScrapedQuestion).order_by(
            ScrapedQuestion.id.desc()).offset(offset).limit(per_page).all()
        return [q.__dict__ for q in questions]
    except Exception as e:
        logging.error(f"Failed to fetch questions for page {page}: {e}")
        return []
    finally:
        db.close()
