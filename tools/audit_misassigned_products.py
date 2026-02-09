"""
Audit ALL sets for products that appear to be assigned to the wrong set.

READ-ONLY: This script only reports findings; it does not modify any data.

Usage:
    python tools/audit_misassigned_products.py
"""

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database


def normalize(text):
    """Normalize a string for fuzzy matching."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[\u2013\u2014\u2015\u2212]", "-", text)
    text = text.replace(" & ", " and ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_false_positive(product_name_norm, matched_set_name_norm, current_set_name_norm):
    """Determine if a match is a false positive. Returns True to skip."""
    if matched_set_name_norm in current_set_name_norm:
        return True
    return False


def main():
    config = Config()
    db = Database(config)

    print("=" * 90)
    print("MISASSIGNED PRODUCT AUDIT (READ-ONLY)")
    print("=" * 90)

    print()
    print("[1] Loading all sets from Supabase...")
    all_sets = db.client.table("sets").select("*").execute().data
    print("    Found " + str(len(all_sets)) + " sets.")

    set_by_id = {}
    set_by_name_norm = {}
    for s in all_sets:
        set_by_id[s["id"]] = s
        norm_name = normalize(s["name"])
        set_by_name_norm[norm_name] = s

    sorted_set_names_norm = sorted(set_by_name_norm.keys(), key=len, reverse=True)

    print("    Set names sorted by length (longest first, showing top 10):")
    for name in sorted_set_names_norm[:10]:
        original = set_by_name_norm[name]["name"]
        print("      [" + str(len(name)).rjust(3) + " chars] " + original)
    if len(sorted_set_names_norm) > 10:
        print("      ... and " + str(len(sorted_set_names_norm) - 10) + " more")
    print()

    print("[2] Loading all products from Supabase...")
    all_products = []
    page_size = 1000
    offset = 0
    while True:
        batch = (
            db.client.table("products")
            .select("*, sets(id, name, code)")
            .order("name")
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        )
        all_products.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    print("    Found " + str(len(all_products)) + " products.")

    print()
    print("[3] Scanning for misassigned products...")
    print("    (Checking each product name against all set names)")
    print()

    flagged = []

    for product in all_products:
        product_name = product["name"]
        product_name_norm = normalize(product_name)
        current_set_data = product.get("sets") or {}
        current_set_name = current_set_data.get("name", "UNKNOWN")
        current_set_name_norm = normalize(current_set_name)
        current_set_id = product["set_id"]

        for set_name_norm in sorted_set_names_norm:
            if set_name_norm not in product_name_norm:
                continue

            matched_set = set_by_name_norm[set_name_norm]

            if matched_set["id"] == current_set_id:
                break

            if is_false_positive(product_name_norm, set_name_norm, current_set_name_norm):
                continue

            flagged.append({
                "product_id": product["id"],
                "product_name": product_name,
                "product_type": product.get("product_type", "?"),
                "current_set_name": current_set_name,
                "current_set_code": current_set_data.get("code", "?"),
                "current_set_id": current_set_id,
                "suspected_set_name": matched_set["name"],
                "suspected_set_code": matched_set.get("code", "?"),
                "suspected_set_id": matched_set["id"],
            })
            break

    print("=" * 90)
    print("RESULTS: " + str(len(flagged)) + " potentially misassigned products found")
    print("=" * 90)

    if not flagged:
        print()
        print("    No misassigned products detected. All products look correct.")
        return

    by_current_set = defaultdict(list)
    for item in flagged:
        key = item["current_set_name"] + " (" + item["current_set_code"] + ")"
        by_current_set[key].append(item)

    for current_set_label in sorted(by_current_set.keys()):
        items = by_current_set[current_set_label]
        print()
        print("  Current set: " + current_set_label)
        print("  " + "-" * (len(current_set_label) + 14))
        for item in items:
            print("    Product:        " + item["product_name"])
            print("    Type:           " + item["product_type"])
            print("    Suspected set:  " + item["suspected_set_name"] + " (" + item["suspected_set_code"] + ")")
            pid_short = item["product_id"][:8] if item["product_id"] else "?"
            print("    Product ID:     " + pid_short + "...")
            print()

    print("=" * 90)
    print("SUMMARY BY SUSPECTED CORRECT SET")
    print("=" * 90)

    by_suspected_set = defaultdict(list)
    for item in flagged:
        key = item["suspected_set_name"] + " (" + item["suspected_set_code"] + ")"
        by_suspected_set[key].append(item)

    for suspected_set_label in sorted(by_suspected_set.keys()):
        items = by_suspected_set[suspected_set_label]
        print()
        print("  Should be in: " + suspected_set_label)
        for item in items:
            from_set = item["current_set_name"] + " (" + item["current_set_code"] + ")"
            print("    <- [" + item["product_type"] + "] " + item["product_name"] + "  (currently in: " + from_set + ")")

    print()
    print("=" * 90)
    print("FINAL STATS")
    print("=" * 90)
    print("  Total products scanned:       " + str(len(all_products)))
    print("  Total sets:                   " + str(len(all_sets)))
    print("  Potentially misassigned:      " + str(len(flagged)))
    print("  Sets with misassigned items:  " + str(len(by_current_set)))
    print()
    print("  NOTE: This is a READ-ONLY audit. No changes were made.")
    print("  Review the flagged items above and decide which to fix.")
    print()


if __name__ == "__main__":
    main()
