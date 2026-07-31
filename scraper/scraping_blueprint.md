TARGET 1: GYM SHARK (The Enterprise Retailer)
Architecture: Shopify Plus / Headless SPA.
Pagination: Standard URL (?page=X).
Extraction Strategy: Hunt for the native Shopify /products.json API or the hidden GraphQL endpoint in the Network tab. Fallback to Playwright DOM State Extraction (__NEXT_DATA__ or window.Shopify) if the direct API is blocked.
Data Yield: Clean, structured, predictable.
TARGET 2: ETSY (The Messy Marketplace)
Architecture: React SPA with Datadome WAF.
Pagination: Standard URL (?page=X).
Extraction Strategy: Playwright with playwright-stealth to bypass Datadome. Extract raw DOM elements.
Data Yield: Highly unstructured, messy text strings (perfect for Phase 4 Fuzzy Matching).
DAY 3 ATTACK PLAN:
Write a unified Python script using Playwright. The script will accept a target configuration (Gymshark or Etsy), route to the correct URL pattern, handle the pagination loop, and extract the data into our SQLite database with a timestamp.