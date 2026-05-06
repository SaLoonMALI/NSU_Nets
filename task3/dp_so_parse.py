# dp_so_parse.py Python-3.11.14
# Sam Lunev. 2026. All Rights Reserved.
import sys
import time
import json
import csv
from contextlib import contextmanager
from DrissionPage import ChromiumPage, ChromiumOptions


@contextmanager
def browser_session():
    options = ChromiumOptions()
    # Disable images to save bandwidth/speed
    options.set_pref('profile.managed_default_content_settings.images', 2)
    # Disable popups to save bandwidth/speed
    options.set_pref('profile.managed_default_content_settings.popups', 2)
    # Enable JS for bypass CloudFlare
    options.set_pref('profile.managed_default_content_settings.javascript', 1)

    page = None
    try:
        print("[INFO] Initializing browser...")
        page = ChromiumPage(addr_or_opts=options)
        yield page  # 'with' block executes here
    except Exception as e:
        print(f"[FAIL] Critical Error in browser session: {e}",
              file=sys.stderr)
        raise
    finally:
        if page:
            print("\n[INFO] Closing browser session...")
            page.quit()


def wait_for_cookie(page, cookie_name, timeout=10):
    start_time = time.time()
    print(f"[INFO] Waiting for cookie: '{cookie_name}'...")

    while time.time() - start_time < timeout:
        cookies = page.cookies()
        if any(cookie['name'] == cookie_name for cookie in cookies):
            print(f"[SUCCESS] Cookie '{cookie_name}' is present")
            return True

        time.sleep(0.5)

    print("[FAIL] Cookie waiting timeout reached")
    return False


def extract_stackoverflow_data(
        page,
        max_pages=8,
        target_limit=100,
        url=f"https://stackoverflow.com/questions?tab=newest&page="):
    all_scraped_data = []
    total_count = 0

    for page_number in range(1, max_pages + 1):
        if total_count >= target_limit:
            break

        current_url = url + f"{page_number}"
        print(f"[INFO] Navigating to {current_url}")
        page.get(current_url, timeout=25, retry=2, interval=4)

        if not wait_for_cookie(page, 'cf_clearance', timeout=15):
            print(f"[WARN] 'cf_clearance' cookie isn't loaded. Check that JS/Cookies enabled")

        print("[INFO] Wait for target element")
        sample_element = page.ele('.s-post-summary--content-excerpt',
                                  timeout=100)
        if not sample_element:
            print(
                "\n[FAIL] Could not find elements. Check if the site structure changed or for CloudFlare 'box' check\n"
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
                text = q.ele('.s-post-summary--content-excerpt').text

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
                print(f"[INFO] -> Extracted: {title[:50]}...")
                total_count += 1
                if total_count >= target_limit:
                    break
            except Exception as e:
                print(f"[FAIL]    Erorr while parsing an item: {e}")
                continue

    return all_scraped_data


def main():
    try:
        # The 'with' statement manages the browser lifetime automatically
        with browser_session() as page:
            data = extract_stackoverflow_data(page)

            if data:
                output_file = 'scraped_data.json'
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                print(
                    f"\n[SUCCESS] Extracted {len(data)} items to {output_file}"
                )
                output_file_csv = 'scraped_data.csv'
                csv_rows = []
                for item in data:
                    row = item.copy()
                    if isinstance(pop_stats := row.get('raw_stats'), list):
                        row['raw_stats'] = "; ".join(pop_stats)
                    csv_rows.append(row)

                keys = csv_rows[0].keys()

                with open(output_file_csv, 'w', newline='',
                          encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(csv_rows)
            else:
                print("\n[INFO] No data was extracted.")

    except Exception as e:
        print(f"\n[FAIL] Scraper stopped due to error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
