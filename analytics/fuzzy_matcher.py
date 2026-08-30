import sqlite3
import re
from pathlib import Path

from rapidfuzz import fuzz, process

DB_PATH = Path("database/competitor_data.db")

# ---------- Normalization ----------
def normalize_name(s: str) -> str:
    """
    Lowercase, remove punctuation, collapse whitespace.
    This is essential for matching keyword-stuffed Etsy titles.
    """
    s = s.lower()
    # Replace anything that's not a word or whitespace with a space
    s = re.sub(r'[^\w\s]', ' ', s)
    # Collapse multiple spaces/newlines into one
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ---------- Custom scorer ----------
def combined_scorer(s1: str, s2: str, score_cutoff: float = None) -> float:
    score = max(
        fuzz.token_sort_ratio(s1, s2),
        fuzz.token_set_ratio(s1, s2)
    )
    # If score_cutoff provided and score below cutoff, we can return 0 for early exit,
    # but process.extract will still handle it. We'll just return the score.
    return score

def run_fuzzy_matching():
    """
    Compare internal products against competitor products, store top 3 candidates.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    # Create staging table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_product_id TEXT,
            competitor TEXT,
            competitor_product_name TEXT,
            score REAL
        )
    """)
    # Clear previous candidates (staging is re-runnable)
    cur.execute("DELETE FROM match_candidates")
    conn.commit()

    # Load internal products
    cur.execute("SELECT product_id, product_name FROM internal_products")
    internal_rows = cur.fetchall()

    # Load distinct competitor product names with competitor
    cur.execute("""
        SELECT DISTINCT competitor, product_name
        FROM price_history
    """)
    competitor_rows = cur.fetchall()

    # Prepare normalized pools
    internal_normalized = [(pid, normalize_name(pname)) for pid, pname in internal_rows]
    # For competitor choices, we need normalized names for matching and original for storage
    comp_choices_normalized = [normalize_name(pname) for _, pname in competitor_rows]
    comp_original = [(comp, pname) for comp, pname in competitor_rows]

    print(f"Internal pool size: {len(internal_normalized)}")
    print(f"Competitor pool size: {len(comp_choices_normalized)}")
    print("Sample normalized internal names:")
    for pid, norm in internal_normalized[:3]:
        print(f"  {pid}: {norm}")
    print("Sample normalized competitor names:")
    for _, norm in list(zip(competitor_rows, comp_choices_normalized))[:3]:
        print(f"  {norm}")

    # For each internal product, find top 3 matches
    all_candidates = []
    for pid, norm_internal in internal_normalized:
        # process.extract returns list of (choice, score, index)
        matches = process.extract(
            norm_internal,
            comp_choices_normalized,
            scorer=combined_scorer,
            limit=3,
            score_cutoff=40   # discard very low scores
        )
        for match_choice, score, idx in matches:
            comp, original_name = comp_original[idx]
            all_candidates.append((pid, comp, original_name, score))

    # Insert into staging table
    cur.executemany("""
        INSERT INTO match_candidates (internal_product_id, competitor, competitor_product_name, score)
        VALUES (?, ?, ?, ?)
    """, all_candidates)
    conn.commit()
    conn.close()

    # Print distribution of best scores
    print("\nScore distribution (best candidate per internal product):")
    # We'll re-open connection to query distribution
    conn = sqlite3.connect(DB_PATH)
    best_scores = []
    for pid, _ in internal_rows:
        cur = conn.cursor()
        cur.execute("""
            SELECT MAX(score) FROM match_candidates WHERE internal_product_id = ?
        """, (pid,))
        best = cur.fetchone()[0]
        if best is not None:
            best_scores.append(best)
    conn.close()

    high = sum(1 for s in best_scores if s >= 90)
    medium = sum(1 for s in best_scores if 70 <= s < 90)
    low = sum(1 for s in best_scores if s < 70)
    print(f"High (>=90): {high}")
    print(f"Medium (70-89): {medium}")
    print(f"Low (<70): {low}")

    # Known-answers test (approximate; we print top score for each rig pair)
    print("\nKnown-answers check:")
    test_pairs = [
        ("P002", "gymshark", "Crest T-Shirt"),
        ("P004", "gymshark", "Power T-Shirt"),
        ("P033", "etsy", "Magic Owl Keycaps Set"),
        ("P001", "gymshark", "Geo Seamless T-Shirt"),
    ]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for internal_id, comp, comp_name in test_pairs:
        cur.execute("""
            SELECT MAX(score) FROM match_candidates
            WHERE internal_product_id = ? AND competitor = ? AND competitor_product_name = ?
        """, (internal_id, comp, comp_name))
        score = cur.fetchone()[0]
        if score is not None:
            print(f"{internal_id} vs {comp} '{comp_name}': score = {score:.2f}")
        else:
            print(f"{internal_id} vs {comp} '{comp_name}': not found in top 3")
    conn.close()

if __name__ == "__main__":
    run_fuzzy_matching()