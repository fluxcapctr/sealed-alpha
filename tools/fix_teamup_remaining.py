"""Fix remaining misassigned products in Team Up (sm9)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database


def main():
    config = Config()
    db = Database(config)
    client = db.client

    sep = "=" * 80
    print(sep)
    print("FIX REMAINING MISASSIGNED PRODUCTS IN TEAM UP")
    print(sep)

    print()
    print("[1] Looking up Team Up set (code: sm9)...")
    tu_rows = client.table("sets").select("*").eq("code", "sm9").execute().data
    if not tu_rows:
        print("    ERROR: Team Up set not found! Aborting.")
        return
    team_up = tu_rows[0]
    tu_id = team_up["id"]
    print(f"    Found: {team_up['name']} (id: {tu_id})")

    print()
    print("[2] Looking up Pokemon GO set...")
    all_sets = client.table("sets").select("*").execute().data
    pokemon_go_set = None
    e_accent = chr(233)
    for s in all_sets:
        nl = s["name"].lower()
        if "pokemon go" in nl or f"pok{e_accent}mon go" in nl:
            pokemon_go_set = s
            break
    if pokemon_go_set:
        print(f"    Found: {pokemon_go_set['name']} (id: {pokemon_go_set['id']}, code: {pokemon_go_set.get('code', '?')})")
    else:
        print("    WARNING: Pokemon GO set not found! Will skip moving GO products.")

    print()
    print("[3] Looking up Paldean Fates set...")
    paldean_fates_set = None
    for s in all_sets:
        if "paldean fates" in s["name"].lower():
            paldean_fates_set = s
            break
    if paldean_fates_set:
        print(f"    Found: {paldean_fates_set['name']} (id: {paldean_fates_set['id']}, code: {paldean_fates_set.get('code', '?')})")
    else:
        print("    WARNING: Paldean Fates set not found! Will skip moving Iono product.")

    print()
    print("[4] Querying all products currently in Team Up...")
    team_up_products = (
        client.table("products")
        .select("*")
        .eq("set_id", tu_id)
        .order("name")
        .execute()
        .data
    )
    print(f"    Found {len(team_up_products)} products in Team Up:")
    print()
    for p in team_up_products:
        pt = p["product_type"]
        pn = p["name"]
        pid_short = p["id"][:12]
        print(f"      - [{pt}] {pn} (id: {pid_short}...)")

    print()
    print(sep)
    print("[5] FIXING PRODUCTS")
    print(sep)

    changes = []

    for p in team_up_products:
        name = p["name"]
        pid = p["id"]
        name_lower = name.lower()

        if "furious fists" in name_lower:
            print()
            print(f'  DELETE: "{name}"')
            print("    Reason: Pre-2018 set product, should not be tracked")
            snap_result = client.table("price_snapshots").delete().eq("product_id", pid).execute()
            snap_count = len(snap_result.data) if snap_result.data else 0
            print(f"    Deleted {snap_count} price snapshots")
            sales_result = client.table("sales_snapshots").delete().eq("product_id", pid).execute()
            sales_count = len(sales_result.data) if sales_result.data else 0
            print(f"    Deleted {sales_count} sales snapshots")
            sig_result = client.table("signals").delete().eq("product_id", pid).execute()
            sig_count = len(sig_result.data) if sig_result.data else 0
            print(f"    Deleted {sig_count} signals")
            alert_result = client.table("alerts").delete().eq("product_id", pid).execute()
            alert_count = len(alert_result.data) if alert_result.data else 0
            print(f"    Deleted {alert_count} alerts")
            result = client.table("products").delete().eq("id", pid).execute()
            if result.data:
                print("    STATUS: DELETED SUCCESSFULLY")
                changes.append(("DELETE", name, "Team Up", "N/A"))
            else:
                print("    STATUS: DELETE FAILED")
            continue

        if "pokemon go" in name_lower or f"pok{e_accent}mon go" in name_lower:
            if pokemon_go_set:
                print()
                print(f'  MOVE: "{name}"')
                go_name = pokemon_go_set["name"]
                print(f"    From: Team Up -> To: {go_name}")
                result = (
                    client.table("products")
                    .update({"set_id": pokemon_go_set["id"]})
                    .eq("id", pid)
                    .execute()
                )
                if result.data:
                    print("    STATUS: MOVED SUCCESSFULLY")
                    changes.append(("MOVE", name, "Team Up", go_name))
                else:
                    print("    STATUS: MOVE FAILED")
            else:
                print()
                print(f'  SKIP: "{name}" - Pokemon GO set not found')
            continue

        if "iono" in name_lower and "bellibolt" in name_lower:
            if paldean_fates_set:
                print()
                print(f'  MOVE: "{name}"')
                pf_name = paldean_fates_set["name"]
                print(f"    From: Team Up -> To: {pf_name}")
                result = (
                    client.table("products")
                    .update({"set_id": paldean_fates_set["id"]})
                    .eq("id", pid)
                    .execute()
                )
                if result.data:
                    print("    STATUS: MOVED SUCCESSFULLY")
                    changes.append(("MOVE", name, "Team Up", pf_name))
                else:
                    print("    STATUS: MOVE FAILED")
            else:
                print()
                print(f'  SKIP: "{name}" - Paldean Fates set not found')
            continue

    print()
    print(sep)
    print("[6] AFTER-FIX VERIFICATION")
    print(sep)

    remaining = (
        client.table("products")
        .select("*")
        .eq("set_id", tu_id)
        .order("name")
        .execute()
        .data
    )
    print()
    print(f"  Products remaining in Team Up: {len(remaining)}")
    for p in remaining:
        print(f"    - [{p['product_type']}] {p['name']}")

    print()
    print(sep)
    print("SUMMARY")
    print(sep)
    print()
    print(f"  Total changes: {len(changes)}")
    for action, name, from_set, to_set in changes:
        if action == "DELETE":
            print(f'    [{action}] "{name}" (was in {from_set})')
        else:
            print(f'    [{action}] "{name}": {from_set} -> {to_set}')
    print()
    print(f"  Products now in Team Up: {len(remaining)}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
