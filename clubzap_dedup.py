"""
ClubZap Duplicate Fixture Cleaner

Scans all fixtures in ClubZap, identifies duplicates (same date + team + opponent),
and deletes the extras — keeping the one with the lowest fixture ID (oldest).

Usage:
  python clubzap_dedup.py              -> dry run (show duplicates, don't delete)
  python clubzap_dedup.py --delete     -> delete duplicates

Requires environment variables:
  CLUBZAP_EMAIL    - ClubZap login email
  CLUBZAP_PASSWORD - ClubZap login password
"""

import asyncio
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

from playwright.async_api import async_playwright

from config import (
    CLUBZAP_BASE_URL as BASE_URL,
    CLUBZAP_FIXTURES_URL as FIXTURES_URL,
)


def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")


async def scan_all_fixtures(page):
    """Scan all fixture pages and return a list of (fixture_id, info_dict)."""
    all_fixtures = []
    page_num = 1

    while True:
        url = f"{FIXTURES_URL}?page={page_num}" if page_num > 1 else FIXTURES_URL
        await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(3000)

        rows = await page.query_selector_all('table tbody tr')
        if not rows:
            break

        rows_on_page = 0
        for row in rows:
            try:
                link = await row.query_selector('a[href*="/fixtures/"]')
                if not link:
                    continue
                href = await link.get_attribute('href') or ''
                match = re.search(r'/fixtures/(\d+)$', href)
                if not match:
                    continue
                fixture_id = match.group(1)

                cells = await row.query_selector_all('td')
                if len(cells) < 7:
                    continue

                date_text = (await cells[0].inner_text()).strip()
                time_text = (await cells[1].inner_text()).strip()
                competition = (await cells[3].inner_text()).strip()
                team = (await cells[4].inner_text()).strip()
                opponent = (await cells[5].inner_text()).strip()
                venue = (await cells[6].inner_text()).strip()

                all_fixtures.append((fixture_id, {
                    'date': date_text,
                    'time': time_text,
                    'competition': competition,
                    'team': team,
                    'opponent': opponent,
                    'venue': venue,
                }))
                rows_on_page += 1
            except Exception as e:
                log(f"  WARNING: Error parsing row: {e}")

        log(f"  Page {page_num}: {rows_on_page} fixtures")
        if rows_on_page == 0:
            break

        next_link = await page.query_selector(f'a[href*="page={page_num + 1}"]')
        if next_link:
            page_num += 1
        else:
            break

    return all_fixtures


def find_duplicates(fixtures):
    """Group fixtures by (date, team, opponent) and return duplicates to delete.

    Keeps the fixture with the lowest ID (oldest) and marks the rest for deletion.
    """
    groups = defaultdict(list)
    for fixture_id, info in fixtures:
        key = (
            info['date'].strip().lower(),
            info['team'].strip().lower(),
            info['opponent'].strip().lower(),
        )
        groups[key].append((fixture_id, info))

    to_delete = []
    for key, group in groups.items():
        if len(group) > 1:
            # Sort by fixture ID (lowest = oldest = keep)
            group.sort(key=lambda x: int(x[0]))
            keep = group[0]
            dupes = group[1:]
            for fixture_id, info in dupes:
                to_delete.append((fixture_id, info, keep[0]))

    return to_delete


async def delete_fixture(page, fixture_id):
    """Delete a fixture by ID."""
    view_url = f"{BASE_URL}/fixtures/{fixture_id}"
    await page.goto(view_url, wait_until='domcontentloaded')
    await page.wait_for_timeout(2000)

    page.once('dialog', lambda dialog: asyncio.ensure_future(dialog.accept()))

    delete_btn = await page.query_selector(
        'a:has-text("Delete"), input[value="Delete"]'
    )
    if not delete_btn:
        return False

    await delete_btn.click()
    await page.wait_for_timeout(3000)

    if f'/fixtures/{fixture_id}' not in page.url:
        return True
    return False


async def main():
    do_delete = '--delete' in sys.argv

    email = os.environ.get('CLUBZAP_EMAIL')
    password = os.environ.get('CLUBZAP_PASSWORD')
    if not email or not password:
        print("Set CLUBZAP_EMAIL and CLUBZAP_PASSWORD environment variables")
        sys.exit(1)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    page.set_default_timeout(30000)

    # Login
    log("Logging in to ClubZap...")
    await page.goto(f"{BASE_URL}/signin", wait_until='domcontentloaded')
    await page.wait_for_timeout(3000)
    await page.fill('input[type="email"], input[name*="email"]', email)
    await page.fill('input[type="password"]', password)
    await page.click('input[type="submit"], button[type="submit"]')
    await page.wait_for_timeout(5000)
    if '/signin' in page.url:
        log("Login failed")
        sys.exit(1)
    log("Logged in")

    # Scan
    log("Scanning all fixtures...")
    fixtures = await scan_all_fixtures(page)
    log(f"Total fixtures: {len(fixtures)}")

    # Find duplicates
    to_delete = find_duplicates(fixtures)

    if not to_delete:
        log("No duplicates found!")
        await browser.close()
        await pw.stop()
        return

    log(f"\nFound {len(to_delete)} duplicate(s) to delete:")
    for fixture_id, info, keep_id in to_delete:
        log(f"  DELETE #{fixture_id}: {info['date']} {info['team']} vs {info['opponent']}"
            f" (keeping #{keep_id})")

    if not do_delete:
        log(f"\nDry run — re-run with --delete to remove {len(to_delete)} duplicates")
        await browser.close()
        await pw.stop()
        return

    # Delete
    log(f"\nDeleting {len(to_delete)} duplicates...")
    deleted = 0
    failed = 0
    for fixture_id, info, keep_id in to_delete:
        log(f"  Deleting #{fixture_id}: {info['date']} {info['team']} vs {info['opponent']}...")
        if await delete_fixture(page, fixture_id):
            log(f"    Deleted")
            deleted += 1
        else:
            log(f"    FAILED to delete")
            failed += 1

    log(f"\nDone: {deleted} deleted, {failed} failed")

    await browser.close()
    await pw.stop()


if __name__ == '__main__':
    asyncio.run(main())
