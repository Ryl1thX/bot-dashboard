import json
import os
from pathlib import Path
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json"
}

# 1. Fetch existing bots
resp = requests.get(f"{SUPABASE_URL}/rest/v1/user_bots?select=bot_id", headers=headers)
if not resp.ok:
    print(f"Error fetching existing bots: {resp.text}")
    exit(1)

existing_ids = set([str(x['bot_id']) for x in resp.json()])
print(f"Found {len(existing_ids)} bots in Supabase.")

inserted = 0
for bot_file in Path("user_bots").glob("*.json"):
    with open(bot_file) as f:
        try:
            b = json.load(f)
            bot_id = str(b.get('id') or b.get('bot_id') or bot_file.stem)
            
            if bot_id not in existing_ids:
                cfg = b.get('config', b)
                name = cfg.get('name') or b.get('bot_name') or "Unknown"
                user_id = str(cfg.get('owner_id') or b.get('user_id') or "Unknown")
                print(f"Inserting missing bot: {name} ({bot_id})")
                
                insert_resp = requests.post(f"{SUPABASE_URL}/rest/v1/user_bots", headers=headers, json={
                    "user_id": user_id,
                    "bot_id": bot_id,
                    "bot_name": name,
                    "settings": cfg,
                    "is_public": cfg.get("privacy", "public") != "private",
                    "created_at": datetime.datetime.utcnow().isoformat()
                })
                
                if insert_resp.ok:
                    inserted += 1
                    existing_ids.add(bot_id)
                else:
                    print(f"Failed to insert {name}: {insert_resp.text}")
        except Exception as e:
            print(f"Error processing {bot_file}: {e}")

print(f"Done! Inserted {inserted} missing bots.")
