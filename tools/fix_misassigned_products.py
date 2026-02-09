import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database


def main():
    config = Config()
    db = Database(config)

    print('=' * 80)
    print('MISASSIGNED PRODUCT FINDER AND FIXER')
    print('=' * 80)

    # Step 1: Load all sets
    print('\n[1] Loading all sets from Supabase...')
    all_sets = db.client.table('sets').select('*').execute().data
    print(f'    Found {len(all_sets)} sets total.')

    set_name_to_record = {}
    set_id_to_record = {}
    for s in all_sets:
        set_name_to_record[s['name']] = s
        set_id_to_record[s['id']] = s

    print('\n    All set names in DB:')
    for s in sorted(all_sets, key=lambda x: x.get('name', '')):
        code_val = s.get('code', '?')
        sid = s['id'][:8]
        print(f'      - {s["name"]} (code={code_val}, id={sid}...)')

    # Step 2: Load ALL products
    print('\n[2] Loading all products from Supabase...')
    all_products = (
        db.client.table('products')
        .select('*, sets(id, name, code)')
        .order('name')
        .execute()
        .data
    )
    print(f'    Found {len(all_products)} products total.')

    # Step 3: Detect misassigned products
    print('\n[3] Scanning for misassigned products...')
    print('-' * 80)

    sorted_set_names = sorted(set_name_to_record.keys(), key=len, reverse=True)

    misassigned = []
    for product in all_products:
        product_name = product['name']
        current_set = product.get('sets') or {}
        current_set_name = current_set.get('name', 'UNKNOWN')
        current_set_id = product['set_id']

        for set_name in sorted_set_names:
            if set_name.lower() in product_name.lower():
                correct_set = set_name_to_record[set_name]
                if correct_set['id'] != current_set_id:
                    misassigned.append({
                        'product': product,
                        'product_name': product_name,
                        'current_set_name': current_set_name,
                        'current_set_id': current_set_id,
                        'correct_set_name': set_name,
                        'correct_set_id': correct_set['id'],
                        'correct_set_code': correct_set.get('code', '?'),
                    })
                break

    print(f'\n    Found {len(misassigned)} misassigned products.\n')

    # Step 4: Check known problem sets
    print('\n[4] Checking known problem sets...')
    print('-' * 80)

    known_problem_sets = {
        'sm5': 'Ultra Prism',
        'sm9': 'Team Up',
    }

    for code_key, expected_name in known_problem_sets.items():
        matching_sets = [s for s in all_sets if s.get('code') == code_key]
        if matching_sets:
            s = matching_sets[0]
            sid = s['id'][:8]
            print(f'\n    Set: {s["name"]} (code={code_key}, id={sid}...)')
            set_products = [p for p in all_products if p['set_id'] == s['id']]
            print(f'    Products assigned ({len(set_products)}):')
            for p in set_products:
                marker = ''
                for m in misassigned:
                    if m['product']['id'] == p['id']:
                        marker = f'  *** MISASSIGNED -> should be {m["correct_set_name"]}'
                        break
                print(f'      - {p["name"]} (type={p["product_type"]}){marker}')
        else:
            print(f'\n    Set with code "{code_key}" not found in DB!')

    # Step 5: Fix misassigned products
    print('\n\n[5] Fixing misassigned products...')
    print('=' * 80)

    changes_made = []

    for m in misassigned:
        product_name = m['product_name']
        correct_set_id = m['correct_set_id']
        correct_set_name = m['correct_set_name']
        current_set_name = m['current_set_name']
        product_id = m['product']['id']

        print(f'\n  Product: {product_name}')
        cur_short = m['current_set_id'][:8]
        cor_short = correct_set_id[:8]
        print(f'    BEFORE: set_id -> {current_set_name} ({cur_short}...)')
        print(f'    AFTER:  set_id -> {correct_set_name} ({cor_short}...)')

        result = (
            db.client.table('products')
            .update({'set_id': correct_set_id})
            .eq('id', product_id)
            .execute()
        )

        if result.data:
            print(f'    STATUS: UPDATED SUCCESSFULLY')
            changes_made.append({
                'product_name': product_name,
                'from_set': current_set_name,
                'to_set': correct_set_name,
            })
        else:
            print(f'    STATUS: UPDATE FAILED - no data returned')

    # Step 6: Check Cosmic Eclipse booster packs
    print('\n\n[6] Cosmic Eclipse (sm12) Booster Pack check...')
    print('=' * 80)

    cosmic_sets = [s for s in all_sets if s.get('code') == 'sm12']
    if cosmic_sets:
        cosmic = cosmic_sets[0]
        cid = cosmic['id'][:8]
        print(f'\n    Set: {cosmic["name"]} (code=sm12, id={cid}...)')

        cosmic_products = [p for p in all_products if p['set_id'] == cosmic['id']]
        booster_packs = [p for p in cosmic_products if p.get('product_type') == 'Booster Pack']

        print(f'\n    All booster packs in Cosmic Eclipse ({len(booster_packs)}):')
        for bp in booster_packs:
            latest = db.get_latest_price(bp['id'])
            price_str = ''
            if latest:
                mp = latest.get('market_price')
                lp = latest.get('low_price')
                price_str = f' | market=, low='
            bpid = bp['id'][:8]
            tcg_id = bp.get('tcgplayer_product_id')
            print(f'      - {bp["name"]} (id={bpid}..., tcgplayer_id={tcg_id}){price_str}')

        print(f'\n    All products in Cosmic Eclipse ({len(cosmic_products)}):')
        for p in cosmic_products:
            latest = db.get_latest_price(p['id'])
            price_str = ''
            if latest:
                mp = latest.get('market_price')
                lp = latest.get('low_price')
                price_str = f' | market=, low='
            print(f'      - [{p["product_type"]}] {p["name"]}{price_str}')
    else:
        print('    Cosmic Eclipse (sm12) not found in DB!')

    # Step 7: Summary
    print('\n\n' + '=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'\n  Total products scanned: {len(all_products)}')
    print(f'  Misassigned products found: {len(misassigned)}')
    print(f'  Products reassigned: {len(changes_made)}')

    if changes_made:
        print('\n  Changes made:')
        for c in changes_made:
            pn = c['product_name']
            fs = c['from_set']
            ts = c['to_set']
            print(f'    - "{pn}": {fs} -> {ts}')

    print('\nDone.')


if __name__ == '__main__':
    main()