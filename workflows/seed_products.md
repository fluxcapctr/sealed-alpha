# Workflow: Seed Pokemon Sets and Products

## Objective
Populate the database with all Pokemon TCG sets (2018-present) and their sealed products from TCGPlayer.

## When to Use
- Initial project setup (run once for full seed)
- When new sets are released (run for specific new set)
- When product types are added to tracking

## Required Inputs
- Supabase credentials configured in `.env`
- TCGPlayer API endpoints discovered (see `workflows/investigate_tcgplayer.md`)

## Tools to Run

### Step 1: Seed Sets
```bash
python tools/seed_sets.py
python tools/seed_sets.py --year-from 2020 --year-to 2025
```

### Step 2: Seed Products
```bash
python tools/seed_products.py
python tools/seed_products.py --set-id UUID
python tools/seed_products.py --product-type "Booster Box"
```

## Step-by-Step
1. Run `seed_sets.py` to discover and insert all sets from 2018-present
2. Verify sets in Supabase dashboard (check counts, release dates)
3. Run `seed_products.py` to discover sealed products for each set
4. Verify products in Supabase dashboard
5. Spot-check a few products by visiting their TCGPlayer URLs

## Product Types Tracked
- Booster Box
- Elite Trainer Box
- Pokemon Center Elite Trainer Box (usually has "Pokemon Center" in name)
- Booster Pack
- Collection Box

## Set Classification
- **In print**: Sets released within the last ~2 years
- **In rotation**: Sets legal in Standard format (~2 years from release for standard sets)
- **Specialty sets**: Celebrations, Crown Zenith, Prismatic Evolutions, etc. — no booster boxes, different product types

## Edge Cases
- Some sets have alternate names on TCGPlayer vs official names
- Pokemon Center exclusives may be listed as separate products or variants
- Specialty/subset releases have different product lineups
- Pre-release products may appear before the set's official release date
- TCGPlayer group IDs are the most reliable identifier for sets

## Output
- Sets table populated with all 2018-present sets
- Products table populated with sealed products per set
- Console output shows success/failure counts
