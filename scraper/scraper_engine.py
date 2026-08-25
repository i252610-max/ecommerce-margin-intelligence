import sys, functools
print = functools.partial(print, flush=True)   # keep for quick debug if needed, but we'll use logging

import json
import asyncio
import random
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Setup logging
logger = logging.getLogger("scraper_engine")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Ensure logs directory exists
log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_dir / "scraper.log")
file_handler.setLevel(logging.WARNING)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Import db_manager (add project root to sys.path)
sys.path.append(str(Path(__file__).resolve().parent.parent))
from database import db_manager

def load_all_targets() -> dict:
    script_dir = Path(__file__).resolve().parent
    config_path = script_dir.parent / "config" / "targets.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

async def human_delay(min_delay: float, max_delay: float):
    delay = random.uniform(min_delay, max_delay)
    logger.info(f"Polite delay: Pausing for {delay:.2f} seconds to mimic human browsing rhythm.")
    await asyncio.sleep(delay)

async def extract_products(page, selectors, target_name, page_label, seen_products):
    """
    Extract product titles and prices, clean them, deduplicate, and return list of tuples.
    Handles per-product errors gracefully.
    """
    logger.info(f"Extracting products from {target_name} (page/label: {page_label})")
    cards = await page.locator(selectors["card"]).all()
    num_cards = len(cards)
    logger.info(f"Found {num_cards} product cards.")

    products = []
    for card in cards:
        try:
            # Title
            title_el = card.locator(selectors["title"]).first
            if title_el:
                title = (await title_el.text_content()).strip()
            else:
                title = "Unknown Title"

            # Price
            price_el = card.locator(selectors["price"]).first
            price = None
            if price_el:
                raw_price = (await price_el.text_content()).strip()
                # Clean price string
                clean = raw_price.replace("Regular Price: ", "").replace("Sale Price ", "")
                for sym in ["$", "£", "€", ","]:
                    clean = clean.replace(sym, "")
                try:
                    price = float(clean)
                except ValueError:
                    price = None
            if price is None:
                logger.warning(f"Missing or unparseable price for '{title}'. Skipping item.")
                continue

            # Timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Deduplication fingerprint
            fingerprint = f"{target_name}|{title}|{price:.2f}"
            if fingerprint in seen_products:
                logger.debug(f"Duplicate skipped: {title} ({price:.2f})")
                continue

            seen_products.add(fingerprint)
            products.append((target_name, title, price, timestamp))
        except Exception as e:
            logger.error(f"Error extracting product in {target_name}: {e}", exc_info=True)
            continue

    logger.info(f"Extracted {len(products)} new products from {target_name} (page {page_label}).")
    return products

async def run_target(target_name: str, config: dict) -> bool:
    """
    Run a single target. Returns True if succeeded, False otherwise.
    Implements three-layer safety net: target, page, product.
    """
    url = config["url"]
    pagination_type = config["pagination_type"]
    max_interactions = config["max_interactions"]
    selectors = config["selectors"]
    delays = config["delays"]
    min_delay = delays["min"]
    max_delay = delays["max"]
    headless = config.get("headless", True)

    logger.info(f"Starting target: {target_name} ({url})")
    seen_products = set()   # dedup set for this target

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()

            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            if pagination_type == "load_more_button":
                logger.info("Using 'Load More' button pagination.")
                try:
                    await page.goto(url)
                    await page.wait_for_selector(selectors["card"], state="attached", timeout=15000)
                    logger.info("Initial products loaded.")

                    load_more_btn = page.locator(selectors["load_more_btn"])
                    clicks = 0
                    while await load_more_btn.is_visible() and clicks < max_interactions:
                        logger.info(f"Clicking 'Load more' (click {clicks+1}/{max_interactions})...")
                        await load_more_btn.click()
                        await page.wait_for_timeout(1500)
                        clicks += 1

                    if await load_more_btn.is_visible():
                        logger.info("Max clicks reached, but more products may exist.")
                    else:
                        logger.info("All products loaded – 'Load more' button is gone.")

                    # Extract all products
                    all_products = await extract_products(page, selectors, target_name, "all", seen_products)
                    if all_products:
                        db_manager.insert_products(all_products)
                        logger.info(f"Inserted {len(all_products)} products for {target_name} (all pages).")
                except Exception as e:
                    logger.error(f"Error during {target_name} load_more flow: {e}", exc_info=True)
                    raise  # propagate to target-level catch

            elif pagination_type == "url_parameter":
                logger.info("Using URL parameter pagination.")
                page_success = False   # will become True if at least one page succeeds
                for page_num in range(1, max_interactions + 1):
                    try:
                        if page_num == 1:
                            page_url = url
                        else:
                            if "pagination_url_format" in config:
                                page_url = config["pagination_url_format"].format(url=url, page=page_num)
                            else:
                                separator = "&" if "?" in url else "?"
                                page_url = f"{url}{separator}page={page_num}"
                        logger.info(f"Navigating to page {page_num}: {page_url}")
                        await page.goto(page_url)
                        await page.wait_for_selector(selectors["card"], state="attached", timeout=15000)
                        page_products = await extract_products(page, selectors, target_name, page_num, seen_products)
                        if page_products:
                            db_manager.insert_products(page_products)
                            logger.info(f"Inserted {len(page_products)} products for {target_name} page {page_num}.")
                        page_success = True   # mark that this page worked
                    except Exception as e:
                        logger.error(f"Error on {target_name} page {page_num}: {e}", exc_info=True)
                        continue
                    if page_num < max_interactions:
                        await human_delay(min_delay, max_delay)

                # If no page succeeded, raise to trigger target-level failure
                if not page_success:
                    raise Exception(f"All pages failed for {target_name}")
            else:
                logger.error(f"Unknown pagination type: {pagination_type}")
                raise ValueError(f"Unknown pagination type: {pagination_type}")

            await page.close()
            await context.close()
            await browser.close()
        logger.info(f"Completed target: {target_name} successfully.")
        return True
    except Exception as e:
        logger.critical(f"Target {target_name} failed: {e}", exc_info=True)
        return False

def main():
    db_manager.init_db()
    all_targets = load_all_targets()
    results = {}
    for target_name, config in all_targets.items():
        success = asyncio.run(run_target(target_name, config))
        results[target_name] = success
    if success:
        logger.info(f"[SUCCESS] {target_name} succeeded.")
    else:
        logger.error(f"[FAILURE] {target_name} failed.")

    # Final summary
    succeeded = sum(1 for s in results.values() if s)
    failed = len(results) - succeeded
    logger.info(f"Run complete: {succeeded} target(s) succeeded, {failed} target(s) failed.")

if __name__ == "__main__":
    main()