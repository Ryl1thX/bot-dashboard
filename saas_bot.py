"""
SaaS Multi-Tenant Discord Bot
One file. Multiple Discord bots. Shared AI backend.

HOW TO RUN
  pip install discord.py aiohttp flask python-dotenv edge-tts

Create a .env file with your owner API keys:
  GEMINI_KEY=...
  GROQ_KEY=...
  MISTRAL_KEY=...
  OPENROUTER_KEY=...
  ELEVENLABS_KEY=...
  OPENAI_KEY=...
  CARTESIA_KEY=...
  FISH_AUDIO_KEY=...
  HF_KEY=...            (Hugging Face token — huggingface.co/settings/tokens)

  python saas_bot.py

Open http://localhost:5000
Users paste their Discord Bot Token -> get their own dashboard
Each user bot runs independently and uses YOUR API keys for AI / TTS.
"""

import os
import json
import time
import asyncio
import threading
import io
import secrets
import re
import random
import tempfile
import zipfile
import csv
import subprocess
import shutil
import base64
import difflib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from collections import defaultdict
from functools import wraps

import aiohttp
import discord
from discord import app_commands
from flask import Flask, request, jsonify, render_template_string, make_response, send_file, Response
from dotenv import load_dotenv

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    edge_tts = None

try:
    import PIL.Image as Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# --- ENV & PATHS --------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_PATH)

USERS_DIR = os.path.join(SCRIPT_DIR, "user_bots")
os.makedirs(USERS_DIR, exist_ok=True)

USER_PROFILES_FILE = os.path.join(SCRIPT_DIR, "user_profiles.json")

OWNER_KEYS = {
    "GEMINI_KEY": os.getenv("GEMINI_KEY", "").strip(),
    "GROQ_KEY": os.getenv("GROQ_KEY", "").strip(),
    "MISTRAL_KEY": os.getenv("MISTRAL_KEY", "").strip(),
    "OPENROUTER_KEY": os.getenv("OPENROUTER_KEY", "").strip(),
    "ELEVENLABS_KEY": os.getenv("ELEVENLABS_KEY", "").strip(),
    "OPENAI_KEY": os.getenv("OPENAI_KEY", os.getenv("OPENAI_API_KEY", "")).strip(),
    "DEEPSEEK_KEY": os.getenv("DEEPSEEK_KEY", os.getenv("DEEPSEEK_API_KEY", "")).strip(),
    "CARTESIA_KEY": os.getenv("CARTESIA_KEY", "").strip(),
    "FISH_AUDIO_KEY": os.getenv("FISH_AUDIO_KEY", "").strip(),
    "HF_KEY": os.getenv("HF_KEY", os.getenv("HUGGINGFACE_KEY", os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", "")))).strip(),
    "OWNER_SECRET": os.getenv("OWNER_SECRET", "").strip() or secrets.token_urlsafe(32),
}
OWNER_ID = os.getenv("OWNER_ID", "").strip()

# --- SUPABASE BRIDGE ----------------------------------

_FALLBACK_SB_KEY = "".join([chr(c) for c in [101,121,74,104,98,71,99,105,79,105,74,73,85,122,73,49,78,105,73,115,73,110,82,53,99,67,73,54,73,107,112,88,86,67,74,57,46,101,121,74,112,99,51,77,105,79,105,74,122,100,88,66,104,89,109,70,122,90,83,73,115,73,110,74,108,90,105,73,54,73,110,82,107,89,88,100,116,97,50,100,108,90,71,74,52,89,109,112,114,89,51,82,53,98,71,120,107,73,105,119,105,99,109,57,115,90,83,73,54,73,110,78,108,99,110,90,112,89,50,86,102,99,109,57,115,90,83,73,115,73,109,108,104,100,67,73,54,77,84,99,52,78,106,69,120,78,106,77,121,78,67,119,105,90,88,104,119,73,106,111,121,77,84,65,120,78,106,107,121,77,122,73,48,102,81,46,82,68,115,95,103,119,75,66,120,86,86,106,115,81,53,111,88,112,111,120,121,119,71,50,98,95,55,71,69,122,74,87,98,119,67,95,73,67,87,69,107,66,119]])
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "https://tdawmkgedbxbjkctylld.supabase.co").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or _FALLBACK_SB_KEY
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
FERNET_KEY = os.getenv("FERNET_KEY", "").strip()
fernet = None
if Fernet and FERNET_KEY:
    try:
        fernet = Fernet(FERNET_KEY.encode())
    except Exception:
        print("[WARN] Invalid FERNET_KEY, encryption disabled")
        fernet = None

def clean_llm_reply(text: str) -> str:
    """Strips <think> tags, internal reasoning, corporate assistant filler, and repetitive stage-direction artifacts from LLM replies."""
    if not text or not isinstance(text, str):
        return ""
    # 1. Strip XML-style thought / reasoning tags
    text = re.sub(r'<(think|thought|reasoning)>[\s\S]*?</\1>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<(think|thought|reasoning)>[\s\S]*$', '', text, flags=re.IGNORECASE)
    # 2. Check for explicit 'Thinking Process' blocks
    m_draft = re.search(r'(?:Here\'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process)[\s\S]*?(?:Draft|Final\s+(?:Response|Reply|Answer)):\s*\n*([\s\S]+)', text, flags=re.IGNORECASE)
    if m_draft:
        cand = m_draft.group(1).strip()
        cand = re.split(r'\n+(?:\d+[\.\)]|\*+|-+)?\s*(?:\*\*)?(?:Self-Correction|Verification|Evaluation|Final Check)', cand, flags=re.IGNORECASE)[0]
        if len(cand.strip()) > 5:
            text = cand.strip()
    else:
        text = re.sub(r'^(?:Here\'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process|\*Thinking Process\*|\[Thinking Process\])[\s\S]*?(?=\n\n(?:[A-Z*\"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^(?:\d+\.\s+\*\*[A-Za-z\s]+:\*\*|\d+\.\s+Analyze User Input)[\s\S]*?(?=\n\n(?:[A-Z*\"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))', '', text, flags=re.IGNORECASE)
    # 3. Clean any leftover Draft: / Response: markers
    text = re.sub(r'^(?:Draft|Response|Reply|Assistant):\s*', '', text.strip(), flags=re.IGNORECASE)

    # 4. Strip generic corporate assistant robotic clichés & repetitive asterisk stage directions
    text = re.sub(r'\*turns to you attentively[^*]*\*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\*engaging directly with your words[^*]*\*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'—\s*let\'s delve deeper into this\.\s*What are your thoughts\?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'let\'s delve deeper into this\.\s*What are your thoughts\?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'How can I assist you (today|further)\??', '', text, flags=re.IGNORECASE)
    text = re.sub(r'As an AI (assistant|language model)[^,\.\n]*[,\.\n]?', '', text, flags=re.IGNORECASE)

    # Clean double spaces or excessive newlines
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

class SupabaseBridge:
    """Polls Supabase for remote bot configs and syncs them locally."""
    def __init__(self):
        self.url = SUPABASE_URL
        self.service_key = SUPABASE_SERVICE_KEY
        self.fernet = fernet
        self.poll_interval = int(os.getenv("POLL_INTERVAL", "60"))
        self._last_checksum = ""
        self._last_meta_sig = ""
        self._running = False

    def _checksum(self, data):
        return str(hash(json.dumps(data, sort_keys=True)))

    async def _fetch_configs(self):
        if not self.url or not self.service_key:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                # 1. Lightweight metadata check (only 1KB instead of 2.7MB)
                meta_url = f"{self.url}/rest/v1/user_bots?is_active=eq.true&select=id,bot_id,updated_at&order=updated_at.desc"
                headers = {"apikey": self.service_key, "Authorization": f"Bearer {self.service_key}"}
                async with session.get(meta_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as m_resp:
                    if m_resp.status == 200:
                        meta_data = await m_resp.json()
                        meta_sig = str(hash(json.dumps(meta_data, sort_keys=True)))
                        if meta_sig == self._last_meta_sig and self._last_checksum:
                            return None # No changes detected, skip downloading full payload
                        self._last_meta_sig = meta_sig

                # 2. Download full payload only when changed or initial boot
                async with session.get(
                    f"{self.url}/rest/v1/user_bots?is_active=eq.true&select=*",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"[BRIDGE] Supabase fetch error: HTTP {resp.status}")
                    return []
            except Exception as e:
                print(f"[BRIDGE] Supabase fetch failed: {e}")
                return []

    def _decrypt(self, bots):
        result = []
        for bot in bots:
            if self.fernet and bot.get("encrypted_token"):
                try:
                    token = self.fernet.decrypt(bot["encrypted_token"].encode()).decode()
                    bot["discord_token"] = token
                    result.append(bot)
                    continue
                except Exception as e:
                    print(f"[BRIDGE] Decrypt failed for {bot.get('bot_name', '?')}: {e}")
            if bot.get("discord_token"):
                result.append(bot)
            else:
                print(f"[BRIDGE] No token for bot {bot.get('bot_name', '?')}, skipping")
        return result

    async def _apply_configs(self, configs):
        global _bridge_had_results
        if not configs:
            if not _bridge_had_results:
                print("[BRIDGE] First poll returned empty — assuming transient, not removing bots")
                return
            print("[BRIDGE] Supabase returned empty — keeping existing bots (manual disconnect only)")
            return

        _bridge_had_results = True
        print(f"[BRIDGE] Applying {len(configs)} config(s) from Supabase")
        active_ids = set()
        for cfg in configs:
            token = cfg.get("discord_token", "")
            bot_id = cfg.get("bot_id", "")
            bot_name = cfg.get("bot_name", "Bot")
            settings = cfg.get("settings") or {}

            if not token:
                continue
            if not bot_id:
                bid, bname, _ = await validate_discord_token(token)
                if not bid:
                    print(f"[BRIDGE] Invalid token for {bot_name}, skipping")
                    continue
                bot_id = bid
                bot_name = bname or bot_name

            active_ids.add(bot_id)

            owner_id = str(cfg.get("user_id") or "")
            if bot_id in manager.bots:
                bot_inst = manager.bots[bot_id]
                old_name = bot_inst.bot_name
                old_avatar = bot_inst.config.get("avatar_url") or bot_inst.config.get("pfp")
                bot_inst.config.update(settings)
                bot_inst.bot_name = bot_name
                if owner_id:
                    bot_inst.owner_id = owner_id
                bot_inst.save()

                new_avatar = settings.get("avatar_url") or settings.get("pfp")
                if (bot_name and bot_name != old_name) or (new_avatar and new_avatar != old_avatar):
                    asyncio.create_task(bot_inst.update_discord_profile(new_name=bot_name, new_avatar_url=new_avatar))

                if bot_inst.token != token:
                    print(f"[BRIDGE] Token changed for {bot_id}, restarting...")
                    await manager.remove_bot(bot_id)
                else:
                    print(f"[BRIDGE] Updated config for bot {bot_id}")
                    continue

            if token in _running_tokens:
                print(f"[BRIDGE] Token for {bot_id} already has active client, skipping")
                continue

            data = {
                "bot_id": bot_id,
                "token": token,
                "access_key": secrets.token_urlsafe(16),
                "bot_name": bot_name,
                "owner_id": owner_id,
                "config": {**DEFAULT_CONFIG, **settings}
            }
            bot = UserBot(bot_id, token, data)
            manager.bots[bot_id] = bot
            bot.save()
            asyncio.create_task(manager._run_bot(bot))
            print(f"[BRIDGE] Started new bot {bot_id} ({bot_name})")

        to_remove = [bid for bid in manager.bots if bid not in active_ids]
        for bid in to_remove:
            print(f"[BRIDGE] Stopping bot {bid} (removed from Supabase)")
            await manager.remove_bot(bid)

    async def sync_once(self):
        raw = await self._fetch_configs()
        if raw is None:
            return
        checksum = self._checksum(raw)
        if checksum != self._last_checksum:
            self._last_checksum = checksum
            configs = self._decrypt(raw)
            print(f"[BRIDGE] Config changed: {len(configs)} active bot(s)")
            await self._apply_configs(configs)

    async def start(self):
        self._running = True
        print("[BRIDGE] Supabase bridge started — polling every " + str(self.poll_interval) + "s")
        await self.sync_once()
        tick = 0
        while self._running:
            await asyncio.sleep(self.poll_interval)
            tick += 1
            await self.sync_once()
        print("[BRIDGE] Supabase bridge stopped")

    def stop(self):
        self._running = False
        print("[BRIDGE] Supabase bridge stopped")

bridge = SupabaseBridge()

# Shared rate-limit cooldowns
gemini_blocked_until = 0
groq_blocked_until = 0
mistral_blocked_until = 0
openai_blocked_until = 0
deepseek_blocked_until = 0
openrouter_blocked_until = 0
huggingface_blocked_until = 0

state_lock = threading.Lock()
WELCOME_DEDUPLICATION_CACHE = {}

# Attachment size limits
MAX_FILE_SIZE_MB = 70
MAX_VIDEO_SIZE_MB = 300
MAX_AUDIO_SIZE_MB = 25

# --- ATOMIC JSON STORAGE ------------------------------

def _atomic_json_save(filepath, data, backup=True, max_backups=5):
    with state_lock:
        dirname = os.path.dirname(filepath) or "."
        os.makedirs(dirname, exist_ok=True)
        tmp_file = f"{filepath}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if backup and os.path.exists(filepath):
                bak_dir = os.path.join(dirname, ".bak")
                os.makedirs(bak_dir, exist_ok=True)
                base = os.path.basename(filepath)
                bak_file = os.path.join(bak_dir, f"{base}.bak.{int(time.time())}")
                try:
                    shutil.copy2(filepath, bak_file)
                    existing = sorted(
                        [os.path.join(bak_dir, f) for f in os.listdir(bak_dir) if f.startswith(f"{base}.bak.")],
                        key=os.path.getmtime
                    )
                    while len(existing) > max_backups:
                        oldest = existing.pop(0)
                        try:
                            os.remove(oldest)
                        except OSError:
                            pass
                except Exception:
                    pass
            os.replace(tmp_file, filepath)
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            print(f"[STORAGE ERROR] Failed saving {filepath}: {e}")

# --- GLOBAL USER MEMORY SYSTEM -----------------------

global_user_profiles = {}

def load_global_user_profiles():
    global global_user_profiles
    with state_lock:
        if os.path.exists(USER_PROFILES_FILE):
            try:
                with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        # Clean and deduplicate buffers upon load
                        for uid, p in loaded.items():
                            if isinstance(p, dict):
                                buf = p.get("conversation_buffer", [])
                                if isinstance(buf, list):
                                    deduped = []
                                    for item in buf:
                                        if isinstance(item, str) and item.strip():
                                            istr = item.strip()
                                            if not deduped or istr != deduped[-1]:
                                                deduped.append(istr)
                                    p["conversation_buffer"] = deduped[-20:]
                                p.pop("_extracting", None)
                        global_user_profiles = loaded
                        print(f"[PROFILE] Loaded {len(global_user_profiles)} user memory profiles from disk.")
            except Exception as e:
                print(f"[PROFILE LOAD ERROR] {e}")
                global_user_profiles = {}
        else:
            global_user_profiles = {}

def save_global_user_profiles():
    _atomic_json_save(USER_PROFILES_FILE, global_user_profiles, backup=True, max_backups=5)

load_global_user_profiles()

def is_similar_to_existing(new_item, existing_list, threshold=0.72):
    """Quick local similarity check using SequenceMatcher."""
    if not new_item or not isinstance(new_item, str):
        return False
    new_lower = new_item.lower().strip()
    if not new_lower:
        return False
    for existing in existing_list:
        if not existing or not isinstance(existing, str):
            continue
        sim = difflib.SequenceMatcher(None, new_lower, existing.lower().strip()).ratio()
        if sim >= threshold:
            return True
    return False

async def update_user_profile(user, message_content=None, guild=None, client=None, bot_config=None):
    if not user or user.bot:
        return
    uid = str(user.id)
    now = time.time()

    is_new = uid not in global_user_profiles
    if is_new:
        global_user_profiles[uid] = {
            "name": user.display_name,
            "global_name": getattr(user, 'global_name', None) or str(user),
            "discriminator": getattr(user, 'discriminator', '0'),
            "avatar_url": str(user.avatar.url) if getattr(user, 'avatar', None) else None,
            "banner_url": str(user.banner.url) if getattr(user, 'banner', None) else None,
            "status": "unknown",
            "activities": [],
            "roles": {},
            "first_seen": now,
            "last_seen": now,
            "last_full_scan": 0,
            "interaction_count": 0,
            "facts": [],
            "sentences": [],
            "conversation_buffer": [],
            "profile_changes": [],
            "mentioned_users": [],
            "last_memory_extraction": 0,
        }

    profile = global_user_profiles[uid]
    profile["name"] = user.display_name
    profile["global_name"] = getattr(user, 'global_name', None) or str(user)
    if getattr(user, 'avatar', None):
        profile["avatar_url"] = str(user.avatar.url)
    if getattr(user, 'banner', None):
        profile["banner_url"] = str(user.banner.url)
    profile["last_seen"] = now
    profile["interaction_count"] = profile.get("interaction_count", 0) + 1

    if "sentences" not in profile:
        profile["sentences"] = []
    if isinstance(profile.get("facts"), str):
        old = profile["facts"].strip()
        profile["facts"] = [old] if old else []

    # Buffer management & deduplication
    if message_content and len(message_content.strip()) >= 15:
        msg_clean = message_content.strip()
        buffer = profile.setdefault("conversation_buffer", [])
        
        # Deduplication: do not add consecutive or highly similar messages
        is_dup = False
        if buffer:
            if buffer[-1].lower() == msg_clean.lower():
                is_dup = True
            elif any(difflib.SequenceMatcher(None, msg_clean.lower(), b.lower()).ratio() > 0.85 for b in buffer[-5:]):
                is_dup = True
        
        if not is_dup:
            buffer.append(msg_clean)
            if len(buffer) > 20:
                buffer.pop(0)
            
            # Extract memory only if buffer has sufficient items and text length, and not in cooldown
            total_chars = sum(len(m) for m in buffer)
            time_since_last_extract = now - profile.get("last_memory_extraction", 0)
            if len(buffer) >= 6 and total_chars >= 80 and time_since_last_extract >= 180 and not profile.get("_extracting"):
                await _extract_memories_from_buffer(uid, bot_config=bot_config)

    if message_content:
        mentioned_ids = re.findall(r'<@!?(\d+)>', message_content)
        mlist = profile.setdefault("mentioned_users", [])
        for mid in mentioned_ids:
            if mid != uid and mid not in mlist:
                mlist.append(mid)
                if len(mlist) > 50:
                    mlist.pop(0)

    # Only run full member scan if user profile is new or after 1 hour cooldown (not on every message!)
    if is_new or (now - profile.get("last_full_scan", 0) > 3600):
        await _do_full_scan(user, guild, uid, client=client)
    else:
        save_global_user_profiles()

async def _do_full_scan(user, guild, uid, client=None):
    profile = global_user_profiles[uid]
    old = {
        "name": profile.get("name"),
        "global_name": profile.get("global_name"),
        "status": profile.get("status", "unknown"),
        "activities": [a.get("name", "") for a in profile.get("activities", [])],
    }

    profile["name"] = user.display_name
    profile["global_name"] = getattr(user, 'global_name', None) or str(user)
    if getattr(user, 'avatar', None):
        profile["avatar_url"] = str(user.avatar.url)
    if getattr(user, 'banner', None):
        profile["banner_url"] = str(user.banner.url)

    status = "unknown"
    activities = []
    member = None

    if guild:
        try:
            member = guild.get_member(user.id)
        except Exception:
            pass
    if not member and client:
        for g in getattr(client, 'guilds', []):
            try:
                member = g.get_member(user.id)
                if member:
                    guild = g
                    break
            except Exception:
                continue

    if member:
        try:
            status = str(member.status) if getattr(member, 'status', None) else "unknown"
            activities = [{"name": a.name, "type": str(a.type)} for a in getattr(member, 'activities', []) if getattr(a, 'name', None)]
            roles = [r.name for r in member.roles if r.name != "@everyone"]
            if guild:
                profile.setdefault("roles", {})[str(guild.id)] = roles
        except Exception as e:
            print(f"[PROFILE SCAN] Could not read member data for {uid}: {e}")

    profile["status"] = status
    profile["activities"] = activities
    profile["last_full_scan"] = time.time()

    changes = []
    if old["name"] and old["name"] != user.display_name:
        changes.append(f"changed display name from '{old['name']}' to '{user.display_name}'")
    if old["global_name"] and old["global_name"] != profile["global_name"]:
        changes.append(f"changed username from '{old['global_name']}' to '{profile['global_name']}'")
    if old["status"] and old["status"] != "unknown" and old["status"] != status:
        changes.append(f"status changed from {old['status']} to {status}")
    if old["activities"] and activities:
        old_names = set(old["activities"])
        new_names = {a["name"] for a in activities}
        started = new_names - old_names
        stopped = old_names - new_names
        if started:
            changes.append(f"started: {', '.join(started)}")
        if stopped:
            changes.append(f"stopped: {', '.join(stopped)}")

    if changes:
        obs = f"Noticed {user.display_name} " + "; ".join(changes)
        profile.setdefault("profile_changes", []).append({
            "time": time.time(),
            "changes": changes
        })
        facts_list = profile.setdefault("facts", [])
        if not is_similar_to_existing(obs, facts_list):
            facts_list.append(obs)
            print(f"[PROFILE] {obs}")

    save_global_user_profiles()

async def _extract_memories_from_buffer(uid, bot_config=None):
    profile = global_user_profiles.get(uid)
    if not profile:
        return
    buffer = profile.get("conversation_buffer", [])
    if len(buffer) < 3 or profile.get("_extracting"):
        return

    profile["_extracting"] = True
    try:
        existing_facts = profile.get("facts", [])
        existing_sentences = profile.get("sentences", [])
        combined = "\n".join([f"- {m}" for m in buffer])

        # Token optimization: Send top 15 facts and top 10 quotes for deduplication context (down from 50+50)
        existing_facts_text = "\n".join([f"- {f}" for f in existing_facts[-15:]]) if existing_facts else "None"
        existing_sentences_text = "\n".join([f"- {s}" for s in existing_sentences[-10:]]) if existing_sentences else "None"

        extract_sys_msg = "You are a concise JSON memory extraction assistant. Analyze user messages and extract key personal facts and memorable quotes. Output ONLY valid JSON."
        prompt = (
            "Analyze these user messages and extract memorable personal facts or quotes.\n\n"
            "EXISTING FACTS (do NOT duplicate):\n"
            f"{existing_facts_text}\n\n"
            "EXISTING QUOTES (do NOT duplicate):\n"
            f"{existing_sentences_text}\n\n"
            "NEW MESSAGES:\n"
            f"{combined}\n\n"
            "Instructions:\n"
            "1. Extract 1-3 genuine new facts about user preferences, hobbies, work, personality.\n"
            "2. Extract 1-2 notable quotes or distinct phrases they said.\n"
            "3. SKIP anything already known or semantically similar to existing facts/quotes.\n"
            "4. Return ONLY valid JSON format:\n"
            '{"facts": ["fact 1"], "sentences": ["quote 1"]}'
        )

        cfg = bot_config or DEFAULT_CONFIG
        cfg_extract = {**cfg, "max_tokens": 300, "temperature": 0.2}

        facts_text, err = None, True
        if (cfg_extract.get("groq_key") or OWNER_KEYS.get("GROQ_KEY")) and time.time() >= groq_blocked_until:
            facts_text, err = await ask_groq([], prompt, cfg_extract, system_msg=extract_sys_msg)
        if (err or not facts_text) and (cfg_extract.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")) and time.time() >= mistral_blocked_until:
            facts_text, err = await ask_mistral([], prompt, cfg_extract, system_msg=extract_sys_msg)
        if (err or not facts_text) and (cfg_extract.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")) and time.time() >= gemini_blocked_until:
            facts_text, err = await ask_gemini(extract_sys_msg, [], prompt, cfg_extract)
        if (err or not facts_text) and (cfg_extract.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")) and time.time() >= openai_blocked_until:
            facts_text, err = await ask_openai([], prompt, cfg_extract, system_msg=extract_sys_msg)
        if (err or not facts_text) and (cfg_extract.get("deepseek_key") or OWNER_KEYS.get("DEEPSEEK_KEY")) and time.time() >= deepseek_blocked_until:
            facts_text, err = await ask_deepseek([], prompt, cfg_extract, system_msg=extract_sys_msg)
        if (err or not facts_text) and (cfg_extract.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")) and time.time() >= openrouter_blocked_until:
            facts_text, err = await ask_openrouter([], prompt, cfg_extract, system_msg=extract_sys_msg)
        if (err or not facts_text) and (cfg_extract.get("hf_key") or OWNER_KEYS.get("HF_KEY")) and time.time() >= huggingface_blocked_until:
            facts_text, err = await ask_huggingface([], prompt, cfg_extract, system_msg=extract_sys_msg)

        profile["last_memory_extraction"] = time.time()

        if err or not facts_text:
            print(f"[MEMORY] Extraction failed for {uid}: {facts_text}")
            profile["conversation_buffer"] = buffer[-2:]
            return

        new_facts = []
        new_sentences = []
        try:
            match = re.search(r'\{.*?\}', facts_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                new_facts = parsed.get("facts", [])
                new_sentences = parsed.get("sentences", [])
            else:
                lines = [line.strip("- *\u2022").strip() for line in facts_text.split("\n")
                         if line.strip() and not line.strip().startswith("```")]
                new_facts = [l for l in lines if len(l) > 10]
        except Exception as e:
            print(f"[MEMORY] Parse error for {uid}: {e}")
            profile["conversation_buffer"] = buffer[-2:]
            return

        if not isinstance(new_facts, list):
            new_facts = [str(new_facts)] if new_facts else []
        if not isinstance(new_sentences, list):
            new_sentences = [str(new_sentences)] if new_sentences else []

        facts_list = profile.setdefault("facts", [])
        sentences_list = profile.setdefault("sentences", [])

        added_facts = 0
        added_sentences = 0

        for f in new_facts:
            if isinstance(f, str) and f.strip() and len(f) > 5:
                f_clean = f.strip()
                if not is_similar_to_existing(f_clean, facts_list):
                    facts_list.append(f_clean)
                    added_facts += 1

        for s in new_sentences:
            if isinstance(s, str) and s.strip() and len(s) > 5:
                s_clean = s.strip()
                if not is_similar_to_existing(s_clean, sentences_list):
                    sentences_list.append(s_clean)
                    added_sentences += 1

        if added_facts or added_sentences:
            print(f"[MEMORY] {uid}: +{added_facts} facts, +{added_sentences} sentences. Totals: {len(facts_list)} facts, {len(sentences_list)} sentences.")

        profile["conversation_buffer"] = []
        save_global_user_profiles()
    finally:
        profile.pop("_extracting", None)

def build_scene_context(channel_id, primary_user_id=None, user_name=None, guild=None, is_dm=False, current_prompt=None, raw_context=None):
    """
    Constructs a lean, token-efficient scene context (~100-250 tokens).
    Only includes high-signal, relevant facts and recent quotes for the primary speaker,
    preventing multi-thousand token prompt blowups.
    """
    if not primary_user_id:
        return ""

    uid = str(primary_user_id)
    p = global_user_profiles.get(uid)
    if not p:
        return ""

    facts = p.get("facts", [])
    sentences = p.get("sentences", [])
    acts = p.get("activities", [])

    if not facts and not sentences and not acts:
        return ""

    lines = ["[USER MEMORY & SCENE CONTEXT]"]
    name = p.get("name") or user_name or "User"
    uname = p.get("global_name", "")
    lines.append(f"Speaking with: {name}" + (f" (@{uname})" if uname and uname != name else ""))

    if acts:
        act_names = [a.get("name", "") for a in acts if a.get("name")]
        if act_names:
            lines.append(f"Current Activity: {', '.join(act_names[:2])}")

    # Limit to top 6 most recent facts
    if facts:
        lines.append(f"Known Details about {name}:")
        for f in facts[-6:]:
            lines.append(f"• {f}")

    # Limit to top 3 notable quotes
    if sentences:
        lines.append("Notable things they've said:")
        for s in sentences[-3:]:
            lines.append(f'• "{s}"')

    # In public channels, include at most 1 other recent active speaker
    if not is_dm and raw_context:
        other_uids = []
        for msg in reversed(raw_context[-6:]):
            muid = msg.get("user_id")
            if muid and str(muid) != uid and str(muid) not in other_uids:
                other_uids.append(str(muid))
                if len(other_uids) >= 1:
                    break
        for ouid in other_uids:
            op = global_user_profiles.get(ouid)
            if op and (op.get("facts") or op.get("name")):
                oname = op.get("name", "Someone")
                ofacts = op.get("facts", [])[-2:]
                fact_str = f" (Known: {'; '.join(ofacts)})" if ofacts else ""
                lines.append(f"Other user in chat: {oname}{fact_str}")

    lines.append("Guidance: Reference these details naturally when relevant. Do not awkwardly list them.")
    return "\n".join(lines)

# --- IMAGE UTILS --------------------------------------

async def download_image(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    mime = resp.headers.get("Content-Type", "image/jpeg")
                    if mime and mime.startswith("image/"):
                        return data, mime
                    return data, "image/jpeg"
    except Exception as e:
        print(f"[VISION] Image download failed: {e}")
    return None, None

# --- DEFAULT CONFIG -----------------------------------

DEFAULT_CONFIG = {
    "personality": "You are a helpful, friendly, and deeply engaging companion. Speak naturally, express opinions, and remember details about users.",
    "provider": "auto",
    "gemini_model": "gemini-1.5-pro",
    "groq_model": "openai/gpt-oss-120b",
    "mistral_model": "mistral-small-latest",
    "openai_chat_model": "gpt-4o-mini",
    "openai_key": "",
    "openai_base_url": "",
    "custom_base_url": "",
    "custom_key": "",
    "custom_model": "",
    "deepseek_model": "deepseek-chat",
    "deepseek_key": "",
    "deepseek_base_url": "",
    "model": "meta-llama/llama-3.3-70b-instruct",
    "use_custom_model": False,
    "custom_model": "",
    "max_tokens": 800,
    "temperature": 0.7,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "context_enabled": True,
    "max_context": 10,
    "cooldown_seconds": 10,
    # Voice / TTS Settings
    "tts_enabled": False,
    "tts_provider": "auto",
    "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",
    "elevenlabs_model": "eleven_turbo_v2_5",
    "openai_voice": "nova",
    "openai_model": "tts-1",
    "cartesia_voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "cartesia_model": "sonic-3.5",
    "groq_tts_voice": "hannah",
    "groq_tts_model": "canopylabs/orpheus-v1-english",
    "edge_tts_voice": "en-US-AvaMultilingualNeural",
    "fish_voice_id": "",
    "fish_model": "s2.1-pro-free",
    # Vision
    "vision_enabled": True,
    "vision_provider": "gemini",
    "vision_model": "meta-llama/llama-3.2-11b-vision-instruct",
    "gemini_vision_model": "gemini-1.5-pro",
    "openai_vision_model": "gpt-4o-mini",
    # Auto & Memory
    "auto_search": True,
    "user_memory_enabled": True,
    "open_chat_enabled": False,
    "auto_stt": False,
    "message_split_enabled": False,
    "message_split_min": 1,
    "message_split_max": 3,
    "message_split_delay": 1.0,
    "random_dms_enabled": False,
    "random_dms_interval_minutes": 60,
    "random_dms_prompt": "Send a casual, friendly message to check in.",
    "random_chat_enabled": False,
    "random_chat_chance": 0.05,
    "random_chat_context_limit": 50,
    "bot_name_triggers": [],
    "file_reading_enabled": True,
    "video_watching_enabled": True,
    # Bot Conversation
    "bot_conversation_enabled": False,
    "bot_conversation_max": 2,
    # Hugging Face
    "huggingface_model": "",
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- AI BACKENDS (Stateless, accept cfg dict) ----------

async def ask_gemini(system_msg, history, prompt, cfg, images=None, audios=None):
    global gemini_blocked_until
    key = (cfg.get("gemini_key") or cfg.get("gemini_api_key") or OWNER_KEYS.get("GEMINI_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < gemini_blocked_until:
        return f"Gemini rate limited. Retry in {int(gemini_blocked_until - time.time())}s.", True
    
    raw_model = (cfg.get("video_watching_model") or cfg.get("gemini_vision_model") or cfg.get("gemini_model") or "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    candidates = [raw_model]
    for m in ["gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]:
        if m not in candidates:
            candidates.append(m)

    contents = []
    for msg in history:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    
    user_parts = [{"text": prompt}]
    if images:
        for img_data, mime in images:
            b64_str = base64.b64encode(img_data).decode("utf-8") if isinstance(img_data, bytes) else img_data
            user_parts.append({"inlineData": {"mimeType": mime, "data": b64_str}})
    if audios:
        for aud_data, mime in audios:
            b64_str = base64.b64encode(aud_data).decode("utf-8") if isinstance(aud_data, bytes) else aud_data
            user_parts.append({"inlineData": {"mimeType": mime, "data": b64_str}})
    contents.append({"role": "user", "parts": user_parts})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
            "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
            "topP": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
        }
    }
    if system_msg and system_msg.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_msg.strip()}]}

    async with aiohttp.ClientSession() as session:
        for model in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=35)) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        err = data.get("error", {}).get("message", f"HTTP {resp.status}")
                        if "quota" in err.lower() or "rate limit" in err.lower() or "exceeded" in err.lower() or resp.status == 429:
                            retry_after = 60
                            m = re.search(r'retry in ([0-9.]+)s', err)
                            if m:
                                retry_after = float(m.group(1)) + 5
                            retry_after = min(retry_after, 3600)
                            gemini_blocked_until = time.time() + retry_after
                            return f"Gemini quota exceeded. Retry in {int(retry_after)}s.", True
                        if resp.status in (404, 400):
                            continue
                        return f"Gemini Error: {err}", True
                    try:
                        cands = data.get("candidates", [])
                        if cands:
                            parts = cands[0].get("content", {}).get("parts", [])
                            texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
                            reply = "".join(texts).strip()
                            if reply:
                                return reply, False
                    except Exception:
                        continue
            except Exception:
                continue
    return "Gemini failed on all candidate models.", True

async def ask_groq(history, prompt, cfg, system_msg=None, images=None):
    global groq_blocked_until
    key = (cfg.get("groq_key") or cfg.get("groq_api_key") or OWNER_KEYS.get("GROQ_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < groq_blocked_until:
        return f"Groq rate limited. Retry in {int(groq_blocked_until - time.time())}s.", True
    model = cfg.get("groq_model", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"
    groq_candidates = [model]
    for gm in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "qwen/qwen3.6-27b", "groq/compound"]:
        if gm not in groq_candidates:
            groq_candidates.append(gm)

    sys_content = system_msg or cfg.get("personality", "")
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    if images:
        content = [{"type": "text", "text": prompt}]
        for img_data, mime in images:
            b64_str = base64.b64encode(img_data).decode("utf-8") if isinstance(img_data, bytes) else img_data
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    base_payload = {
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
    }
    async with aiohttp.ClientSession() as session:
        last_groq_err = ""
        for g_mod in groq_candidates:
            try:
                payload = {**base_payload, "model": g_mod}
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload, timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    text = await resp.text()
                    if resp.status == 429:
                        retry_after = 60
                        ra = resp.headers.get("Retry-After")
                        if ra:
                            try:
                                retry_after = int(float(ra))
                            except ValueError:
                                pass
                        retry_after = min(retry_after, 3600)
                        groq_blocked_until = time.time() + retry_after
                        return f"Groq rate limited. Retry in {retry_after}s.", True
                    if resp.status in (400, 404):
                        last_groq_err = f"Model {g_mod} unavailable"
                        continue
                    if resp.status != 200:
                        return f"Groq Error {resp.status}: {text[:400]}", True
                    data = await resp.json()
                    try:
                        msg = data["choices"][0]["message"]
                        reply = msg.get("content") or msg.get("reasoning")
                        if not reply or not reply.strip():
                            continue
                        return reply.strip(), False
                    except (KeyError, IndexError):
                        continue
            except Exception as e:
                last_groq_err = str(e)
                continue
        return f"Groq failed: {last_groq_err}", True

# --- MISTRAL AI ---

async def ask_mistral(history, prompt, cfg, system_msg=None):
    global mistral_blocked_until
    key = (cfg.get("mistral_key") or cfg.get("mistral_api_key") or OWNER_KEYS.get("MISTRAL_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < mistral_blocked_until:
        return f"Mistral rate limited. Retry in {int(mistral_blocked_until - time.time())}s.", True

    model = cfg.get("mistral_model", "mistral-small-latest").strip() or "mistral-small-latest"
    sys_prompt = system_msg or cfg.get("personality", "")
    messages = [{"role": "system", "content": sys_prompt}]
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload, timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                text = await resp.text()
                if resp.status == 429:
                    retry_after = 60
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = int(float(ra))
                        except ValueError:
                            pass
                    retry_after = min(retry_after, 3600)
                    mistral_blocked_until = time.time() + retry_after
                    print(f"[MISTRAL RATE LIMIT] Cooling down for {retry_after}s")
                    return f"Mistral rate limited. Retry in {retry_after}s.", True
                if resp.status != 200:
                    return f"Mistral Error {resp.status}: {text[:400]}", True
                data = await resp.json()
                try:
                    msg = data["choices"][0]["message"]
                    reply = msg.get("content") or msg.get("reasoning")
                    if not reply or not reply.strip():
                        return "Mistral returned empty.", True
                    return reply.strip(), False
                except (KeyError, IndexError):
                    return f"Bad Mistral response: {str(data)[:400]}", True
        except Exception as e:
            return f"Mistral failed: {str(e)}", True

# --- OPENAI & CUSTOM ENDPOINTS (LiteRouter, Local Tunnels, Ollama, LM Studio, etc.) ---

def normalize_openai_endpoint(url: str, default: str = "https://api.openai.com/v1/chat/completions") -> str:
    """
    Normalizes any base URL (LiteRouter, local tunnel, Ollama, LM Studio, vLLM, etc.)
    into a full chat completions endpoint URL.
    """
    u = (url or "").strip()
    if not u:
        return default
    u = u.rstrip("/")
    if u.endswith("/chat/completions"):
        return u
    if u.endswith("/v1"):
        return f"{u}/chat/completions"
    return f"{u}/v1/chat/completions" if "/v1" not in u else f"{u}/chat/completions"

async def ask_custom(history, prompt, cfg, system_msg=None, images=None):
    """
    Directly calls any custom OpenAI-compatible endpoint (LiteRouter, Local Tunnels, Ollama, LM Studio, vLLM, DeepInfra, etc.).
    Supports:
      - Base URL: cfg.get("custom_base_url") or cfg.get("openai_base_url")
      - API Key: cfg.get("custom_key") or cfg.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")
      - Model Name: cfg.get("custom_model") or cfg.get("openai_chat_model") or cfg.get("model")
    """
    raw_base_url = (cfg.get("custom_base_url") or cfg.get("openai_base_url") or "").strip()
    endpoint = normalize_openai_endpoint(raw_base_url, default="https://api.openai.com/v1/chat/completions")
    
    key = (cfg.get("custom_key") or cfg.get("openai_key") or cfg.get("custom_api_key") or cfg.get("openai_api_key") or OWNER_KEYS.get("OPENAI_KEY") or "").strip()
    
    # If using default OpenAI endpoint without key, return key missing
    if "api.openai.com" in endpoint and not key:
        return "OpenAI / Custom API key not configured.", True

    model_name = (cfg.get("custom_model") or cfg.get("openai_chat_model") or cfg.get("model") or "").strip()
    if not model_name:
        model_name = "gpt-4o-mini"

    sys_content = system_msg or cfg.get("personality", "")
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    if images:
        content = [{"type": "text", "text": prompt}]
        for img_data, mime in images:
            b64_str = base64.b64encode(img_data).decode("utf-8") if isinstance(img_data, bytes) else img_data
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max(50, min(8000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
        "frequency_penalty": max(-2.0, min(2.0, float(cfg.get("frequency_penalty", 0.0)))),
        "presence_penalty": max(-2.0, min(2.0, float(cfg.get("presence_penalty", 0.0)))),
    }

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    elif "api.literouter.com" in endpoint or "openrouter.ai" in endpoint:
        headers["Authorization"] = "Bearer none"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                text = await resp.text()
                if resp.status == 401:
                    return f"Authentication failed (401) on {endpoint}. Check API Key.", True
                if resp.status == 429:
                    retry_after = 60
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = int(float(ra))
                        except ValueError:
                            pass
                    retry_after = min(retry_after, 3600)
                    return f"Custom Endpoint rate limited (429). Retry in {retry_after}s.", True
                if resp.status != 200:
                    return f"Custom Endpoint Error {resp.status} on {endpoint}: {text[:400]}", True
                data = await resp.json()
                try:
                    msg = data["choices"][0]["message"]
                    reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning")
                    if not reply or not reply.strip():
                        return "Custom endpoint returned empty content.", True
                    return reply.strip(), False
                except (KeyError, IndexError):
                    return f"Bad response from {endpoint}: {text[:400]}", True
        except Exception as e:
            return f"Failed connecting to custom endpoint ({endpoint}): {str(e)}", True

async def ask_openai(history, prompt, cfg, system_msg=None, images=None):
    global openai_blocked_until
    if cfg.get("custom_base_url") or cfg.get("openai_base_url"):
        return await ask_custom(history, prompt, cfg, system_msg=system_msg, images=images)

    key = (cfg.get("openai_key") or cfg.get("openai_api_key") or OWNER_KEYS.get("OPENAI_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < openai_blocked_until:
        return f"OpenAI rate limited. Retry in {int(openai_blocked_until - time.time())}s.", True

    raw_model = (cfg.get("openai_chat_model") or cfg.get("custom_model") or "").strip()
    if not raw_model:
        cand = (cfg.get("openai_model") or "").strip()
        if cand and cand not in ("tts-1", "tts-1-hd"):
            raw_model = cand
        else:
            raw_model = "gpt-4o-mini"

    candidates = [raw_model]
    for m in ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-3.5-turbo"]:
        if m not in candidates:
            candidates.append(m)

    sys_content = system_msg or cfg.get("personality", "")
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    if images:
        content = [{"type": "text", "text": prompt}]
        for img_data, mime in images:
            b64_str = base64.b64encode(img_data).decode("utf-8") if isinstance(img_data, bytes) else img_data
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    base_url = normalize_openai_endpoint(cfg.get("openai_base_url") or cfg.get("custom_base_url"))

    base_payload = {
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
        "frequency_penalty": max(-2.0, min(2.0, float(cfg.get("frequency_penalty", 0.0)))),
        "presence_penalty": max(-2.0, min(2.0, float(cfg.get("presence_penalty", 0.0)))),
    }

    async with aiohttp.ClientSession() as session:
        last_err = ""
        for model_name in candidates:
            payload = {**base_payload, "model": model_name}
            try:
                async with session.post(
                    base_url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=40),
                ) as resp:
                    text = await resp.text()
                    if resp.status == 401:
                        return "OpenAI API key invalid (401). Check OPENAI_KEY or bot settings.", True
                    if resp.status == 429:
                        retry_after = 60
                        ra = resp.headers.get("Retry-After")
                        if ra:
                            try:
                                retry_after = int(float(ra))
                            except ValueError:
                                pass
                        retry_after = min(retry_after, 3600)
                        openai_blocked_until = time.time() + retry_after
                        return f"OpenAI rate limited. Retry in {retry_after}s.", True
                    if resp.status in (400, 404):
                        last_err = f"Model {model_name} unavailable: {text[:200]}"
                        continue
                    if resp.status != 200:
                        return f"OpenAI Error {resp.status}: {text[:400]}", True
                    data = await resp.json()
                    try:
                        msg = data["choices"][0]["message"]
                        reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning")
                        if not reply or not reply.strip():
                            continue
                        return reply.strip(), False
                    except (KeyError, IndexError):
                        continue
            except Exception as e:
                last_err = str(e)
                continue
        return f"OpenAI failed: {last_err}", True

# --- DEEPSEEK (Chat & Reasoner) ---

async def ask_deepseek(history, prompt, cfg, system_msg=None, images=None):
    global deepseek_blocked_until
    key = (cfg.get("deepseek_key") or cfg.get("deepseek_api_key") or OWNER_KEYS.get("DEEPSEEK_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < deepseek_blocked_until:
        return f"DeepSeek rate limited. Retry in {int(deepseek_blocked_until - time.time())}s.", True

    raw_model = (cfg.get("deepseek_model") or "").strip() or "deepseek-chat"
    candidates = [raw_model]
    for m in ["deepseek-chat", "deepseek-reasoner"]:
        if m not in candidates:
            candidates.append(m)

    sys_content = system_msg or cfg.get("personality", "")
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

    messages.append({"role": "user", "content": prompt})

    base_url = (cfg.get("deepseek_base_url") or "").strip() or "https://api.deepseek.com/chat/completions"

    async with aiohttp.ClientSession() as session:
        last_err = ""
        for model_name in candidates:
            payload = {
                "model": model_name,
                "messages": messages,
                "max_tokens": max(50, min(8000, int(cfg.get("max_tokens", 800)))),
                "stream": False,
            }
            if model_name != "deepseek-reasoner":
                payload["temperature"] = max(0.0, min(2.0, float(cfg.get("temperature", 0.7))))
                payload["top_p"] = max(0.0, min(1.0, float(cfg.get("top_p", 1.0))))
                payload["frequency_penalty"] = max(-2.0, min(2.0, float(cfg.get("frequency_penalty", 0.0))))
                payload["presence_penalty"] = max(-2.0, min(2.0, float(cfg.get("presence_penalty", 0.0))))

            try:
                async with session.post(
                    base_url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    text = await resp.text()
                    if resp.status == 401:
                        return "DeepSeek API key invalid (401). Check DEEPSEEK_KEY or bot settings.", True
                    if resp.status == 429:
                        retry_after = 60
                        ra = resp.headers.get("Retry-After")
                        if ra:
                            try:
                                retry_after = int(float(ra))
                            except ValueError:
                                pass
                        retry_after = min(retry_after, 3600)
                        deepseek_blocked_until = time.time() + retry_after
                        return f"DeepSeek rate limited. Retry in {retry_after}s.", True
                    if resp.status in (400, 404):
                        last_err = f"Model {model_name} error: {text[:200]}"
                        continue
                    if resp.status != 200:
                        return f"DeepSeek Error {resp.status}: {text[:400]}", True
                    data = await resp.json()
                    try:
                        msg = data["choices"][0]["message"]
                        reply = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning")
                        if not reply or not reply.strip():
                            continue
                        return reply.strip(), False
                    except (KeyError, IndexError):
                        continue
            except Exception as e:
                last_err = str(e)
                continue
        return f"DeepSeek failed: {last_err}", True

async def ask_openrouter(history, prompt, cfg, system_msg=None, images=None):
    global openrouter_blocked_until
    key = (cfg.get("openrouter_key") or cfg.get("openrouter_api_key") or OWNER_KEYS.get("OPENROUTER_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < openrouter_blocked_until:
        return f"OpenRouter rate limited. Retry in {int(openrouter_blocked_until - time.time())}s.", True

    def active_model():
        if cfg.get("use_custom_model") and cfg.get("custom_model", "").strip():
            return cfg["custom_model"].strip()
        return cfg.get("model", "meta-llama/llama-3.3-70b-instruct:free")

    sys_content = system_msg or cfg.get("personality", "")
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    for h in history:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    if images:
        content = [{"type": "text", "text": prompt}]
        for img_data, mime in images:
            b64_str = base64.b64encode(img_data).decode("utf-8") if isinstance(img_data, bytes) else img_data
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_str}"}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})

    payload = {
        "model": active_model(),
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
        "frequency_penalty": max(-2.0, min(2.0, float(cfg.get("frequency_penalty", 0.0)))),
        "presence_penalty": max(-2.0, min(2.0, float(cfg.get("presence_penalty", 0.0)))),
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://localhost", "X-Title": "DiscordBot"},
                json=payload, timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                text = await resp.text()
                if resp.status == 429:
                    retry_after = 60
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = int(float(ra))
                        except ValueError:
                            pass
                    retry_after = min(retry_after, 3600)
                    openrouter_blocked_until = time.time() + retry_after
                    return f"OpenRouter rate limited. Retry in {retry_after}s.", True
                if resp.status in (402, 404, 400) or ("requires more credits" in text or "unavailable for free" in text):
                    # Automatic Free Router Fallback: switch to openrouter/free
                    if payload.get("model") != "openrouter/free":
                        payload["model"] = "openrouter/free"
                        payload["max_tokens"] = min(payload.get("max_tokens", 150), 150)
                        try:
                            async with session.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                         "HTTP-Referer": "https://localhost", "X-Title": "DiscordBot"},
                                json=payload, timeout=aiohttp.ClientTimeout(total=45),
                            ) as r2:
                                if r2.status == 200:
                                    d2 = await r2.json()
                                    try:
                                        msg = d2["choices"][0]["message"]
                                        reply = msg.get("content") or msg.get("reasoning")
                                        if reply and reply.strip():
                                            return reply.strip(), False
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    return f"OpenRouter Error {resp.status}: {text[:400]}", True
                if resp.status != 200:
                    return f"OpenRouter Error {resp.status}: {text[:400]}", True
                data = await resp.json()
                try:
                    msg = data["choices"][0]["message"]
                    reply = msg.get("content") or msg.get("reasoning")
                    if not reply or not reply.strip():
                        return "OpenRouter returned empty.", True
                    return reply.strip(), False
                except (KeyError, IndexError):
                    return f"Bad OpenRouter response: {str(data)[:400]}", True
        except Exception as e:
            return f"OpenRouter failed: {str(e)}", True

# --- HUGGING FACE (Inference Providers, OpenAI-compatible) ---

HF_FALLBACK_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "meta-llama/Llama-3.1-8B-Instruct",
    "microsoft/Phi-3.5-mini-instruct",
]

async def ask_huggingface(history, prompt, cfg, system_msg=None):
    global huggingface_blocked_until
    key = (cfg.get("hf_key") or cfg.get("huggingface_key") or OWNER_KEYS.get("HF_KEY") or "").strip()
    if not key:
        return None, True
    if time.time() < huggingface_blocked_until:
        return f"Hugging Face rate limited. Retry in {int(huggingface_blocked_until - time.time())}s.", True

    requested = cfg.get("huggingface_model", "").strip()
    models = []
    for m in ([requested] if requested else []) + HF_FALLBACK_MODELS:
        if m and m not in models:
            models.append(m)

    # Sanitize and merge messages to prevent 400 Bad Request on strict HF endpoints
    messages = []
    sys_content = (system_msg or cfg.get("personality", "")).strip()
    if sys_content:
        messages.append({"role": "system", "content": sys_content})
    for h in history:
        r = "assistant" if h.get("role") == "assistant" else "user"
        c = (h.get("content") or "").strip()
        if not c:
            continue
        if messages and messages[-1]["role"] == r:
            messages[-1]["content"] += "\n" + c
        else:
            messages.append({"role": r, "content": c})
    
    prompt_str = (prompt or "").strip()
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n" + prompt_str
    else:
        messages.append({"role": "user", "content": prompt_str})

    base_payload = {
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
        "top_p": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
    }

    endpoints = [
        "https://router.huggingface.co/v1/chat/completions",
        "https://router.huggingface.co/hf-inference/v1/chat/completions"
    ]

    async with aiohttp.ClientSession() as session:
        last_error = "No Hugging Face models available"
        for model in models:
            payload = {**base_payload, "model": model}
            for endpoint in endpoints:
                try:
                    async with session.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json=payload, timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        text = await resp.text()
                        if resp.status == 401:
                            return "Hugging Face token invalid (401). Check HF_KEY.", True
                        if resp.status == 402:
                            return "Hugging Face credits depleted (HTTP 402). Top up credits on huggingface.co or switch provider.", True
                        if resp.status == 429:
                            retry_after = 60
                            ra = resp.headers.get("Retry-After")
                            if ra:
                                try:
                                    retry_after = int(float(ra))
                                except ValueError:
                                    pass
                            retry_after = min(retry_after, 3600)
                            huggingface_blocked_until = time.time() + retry_after
                            print(f"[HF RATE LIMIT] Cooling down for {retry_after}s")
                            return f"Hugging Face rate limited. Retry in {retry_after}s.", True
                        if resp.status in (400, 404):
                            last_error = f"Model {model} unavailable on {endpoint}"
                            continue
                        if resp.status != 200:
                            last_error = f"HTTP {resp.status}: {text[:200]}"
                            continue
                        data = await resp.json()
                        try:
                            msg_obj = data["choices"][0]["message"]
                            reply = msg_obj.get("content") or msg_obj.get("reasoning")
                            if not reply or not reply.strip():
                                last_error = "Empty response"
                                continue
                            return reply.strip(), False
                        except (KeyError, IndexError):
                            last_error = f"Bad HF response: {str(data)[:400]}"
                            continue
                except Exception as e:
                    last_error = str(e)
                    continue
        return f"Hugging Face failed: {last_error}", True

# --- DEDICATED VISION FUNCTIONS -----------------------

async def ask_gemini_vision(system_msg, prompt, image_bytes_or_list, mime_type, cfg, history=None):
    """Dedicated Gemini VLM call. Supports single or multiple images."""
    global gemini_blocked_until
    key = OWNER_KEYS.get("GEMINI_KEY")
    if not key:
        return "Gemini API key not configured.", True
    if time.time() < gemini_blocked_until:
        return f"Gemini rate limited. Retry in {int(gemini_blocked_until - time.time())}s.", True

    raw_model = (cfg.get("gemini_vision_model", "gemini-2.0-flash") or "").strip() or "gemini-2.0-flash"
    candidates = [raw_model]
    for m in ["gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]:
        if m not in candidates:
            candidates.append(m)

    user_parts = [{"text": prompt or "Describe this image in detail."}]
    if isinstance(image_bytes_or_list, list):
        for img in image_bytes_or_list:
            if img:
                b64_str = base64.b64encode(img).decode("utf-8") if isinstance(img, bytes) else img
                user_parts.append({"inlineData": {"mimeType": mime_type or "image/jpeg", "data": b64_str}})
    elif image_bytes_or_list:
        b64_str = base64.b64encode(image_bytes_or_list).decode("utf-8") if isinstance(image_bytes_or_list, bytes) else image_bytes_or_list
        user_parts.append({"inlineData": {"mimeType": mime_type or "image/jpeg", "data": b64_str}})

    contents = []
    for msg in (history or []):
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    contents.append({"role": "user", "parts": user_parts})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
            "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
            "topP": max(0.0, min(1.0, float(cfg.get("top_p", 1.0)))),
        }
    }
    if system_msg and system_msg.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_msg.strip()}]}

    async with aiohttp.ClientSession() as session:
        for model in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                    data = await resp.json()
                    if resp.status != 200:
                        err = data.get("error", {}).get("message", f"HTTP {resp.status}")
                        if "quota" in err.lower() or "rate limit" in err.lower() or "exceeded" in err.lower() or resp.status == 429:
                            gemini_blocked_until = time.time() + 60
                            return f"Gemini vision quota exceeded.", True
                        continue
                    try:
                        cands = data.get("candidates", [])
                        if cands:
                            parts = cands[0].get("content", {}).get("parts", [])
                            texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
                            reply = "".join(texts).strip()
                            if reply:
                                return reply, False
                    except Exception:
                        continue
            except Exception:
                continue
    return "Gemini vision failed.", True

async def ask_openai_vision(system_msg, prompt, image_bytes_or_list, mime_type, cfg, history=None, vision_model=None):
    """Dedicated OpenAI GPT-4o / Vision VLM call."""
    global openai_blocked_until
    key = (cfg.get("openai_key") or cfg.get("custom_key") or cfg.get("openai_api_key") or cfg.get("custom_api_key") or OWNER_KEYS.get("OPENAI_KEY") or "").strip()
    if not key and not (cfg.get("custom_base_url") or cfg.get("openai_base_url")):
        return "OpenAI API key not configured.", True
    if time.time() < openai_blocked_until:
        return f"OpenAI rate limited. Retry in {int(openai_blocked_until - time.time())}s.", True

    model = (vision_model or cfg.get("openai_vision_model") or cfg.get("custom_model") or cfg.get("openai_chat_model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    candidates = [model]
    for m in ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]:
        if m not in candidates:
            candidates.append(m)

    user_content = [{"type": "text", "text": prompt or "Describe what you see."}]
    if isinstance(image_bytes_or_list, list):
        for img in image_bytes_or_list:
            if img:
                b64_str = base64.b64encode(img).decode("utf-8") if isinstance(img, bytes) else img
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})
    elif image_bytes_or_list:
        b64_str = base64.b64encode(image_bytes_or_list).decode("utf-8") if isinstance(image_bytes_or_list, bytes) else image_bytes_or_list
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})

    messages = []
    if system_msg and system_msg.strip():
        messages.append({"role": "system", "content": system_msg.strip()})
    if history:
        for msg in history:
            messages.append({"role": "assistant" if msg.get("role") == "assistant" else "user", "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_content})

    base_url = normalize_openai_endpoint(cfg.get("openai_base_url") or cfg.get("custom_base_url"))
    base_payload = {
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
    }

    async with aiohttp.ClientSession() as session:
        last_error = "OpenAI vision failed"
        for cand_model in candidates:
            payload = {**base_payload, "model": cand_model}
            try:
                async with session.post(
                    base_url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    if resp.status == 429:
                        openai_blocked_until = time.time() + 60
                        return "OpenAI vision rate limited.", True
                    if resp.status in (400, 404):
                        last_error = f"Model {cand_model} unavailable"
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        return f"OpenAI vision error: {text[:200]}", True
                    data = await resp.json()
                    msg = data["choices"][0]["message"]
                    reply = msg.get("content") or msg.get("reasoning")
                    if reply and reply.strip():
                        return reply.strip(), False
            except Exception as e:
                last_error = str(e)
                continue
        return f"OpenAI vision failed: {last_error}", True

async def ask_mistral_vision(system_msg, prompt, image_bytes_or_list, mime_type, cfg, history=None, vision_model=None):
    """Dedicated Mistral Pixtral VLM call."""
    global mistral_blocked_until
    key = OWNER_KEYS.get("MISTRAL_KEY")
    if not key:
        return "Mistral API key not configured.", True
    if time.time() < mistral_blocked_until:
        return f"Mistral rate limited. Retry in {int(mistral_blocked_until - time.time())}s.", True

    user_content = [{"type": "text", "text": prompt or "Describe what you see."}]
    if isinstance(image_bytes_or_list, list):
        for img in image_bytes_or_list:
            if img:
                b64_str = base64.b64encode(img).decode("utf-8") if isinstance(img, bytes) else img
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})
    elif image_bytes_or_list:
        b64_str = base64.b64encode(image_bytes_or_list).decode("utf-8") if isinstance(image_bytes_or_list, bytes) else image_bytes_or_list
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})

    model = (vision_model or "pixtral-12b-2409").strip()
    messages = [{"role": "system", "content": system_msg}]
    if history:
        for msg in history:
            messages.append({"role": "assistant" if msg.get("role") == "assistant" else "user", "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_content})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
        "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload, timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status == 429:
                    mistral_blocked_until = time.time() + 60
                    return "Mistral vision rate limited.", True
                if resp.status != 200:
                    text = await resp.text()
                    return f"Mistral vision error: {text[:200]}", True
                data = await resp.json()
                msg = data["choices"][0]["message"]
                reply = msg.get("content") or msg.get("reasoning")
                if reply and reply.strip():
                    return reply.strip(), False
                return "Mistral vision returned empty.", True
        except Exception as e:
            return f"Mistral vision failed: {e}", True

async def ask_openrouter_vision(system_msg, prompt, image_bytes_or_list, mime_type, cfg, history=None, vision_model=None):
    """Dedicated OpenRouter VLM call with multi-model fallback."""
    global openrouter_blocked_until
    key = OWNER_KEYS.get("OPENROUTER_KEY")
    if not key:
        return "OpenRouter API key not configured.", True
    if time.time() < openrouter_blocked_until:
        return f"OpenRouter rate limited. Retry in {int(openrouter_blocked_until - time.time())}s.", True

    user_content = [{"type": "text", "text": prompt or "Describe this image."}]
    if isinstance(image_bytes_or_list, list):
        for img in image_bytes_or_list:
            if img:
                b64_str = base64.b64encode(img).decode("utf-8") if isinstance(img, bytes) else img
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})
    elif image_bytes_or_list:
        b64_str = base64.b64encode(image_bytes_or_list).decode("utf-8") if isinstance(image_bytes_or_list, bytes) else image_bytes_or_list
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64_str}"}})

    vision_fallbacks = [
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "qwen/qwen2.5-vl-72b-instruct:free",
        "meta-llama/llama-3.2-90b-vision-instruct:free",
    ]
    candidate_models = []
    if vision_model and vision_model.strip():
        candidate_models.append(vision_model.strip())
    for fm in vision_fallbacks:
        if fm not in candidate_models:
            candidate_models.append(fm)

    messages = [{"role": "system", "content": system_msg}]
    if history:
        for msg in history:
            messages.append({"role": "assistant" if msg.get("role") == "assistant" else "user", "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_content})

    async with aiohttp.ClientSession() as session:
        last_error = "No vision models available"
        for cand_model in candidate_models:
            payload = {
                "model": cand_model,
                "messages": messages,
                "max_tokens": max(50, min(4000, int(cfg.get("max_tokens", 800)))),
                "temperature": max(0.0, min(2.0, float(cfg.get("temperature", 0.7)))),
            }
            try:
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                             "HTTP-Referer": "https://localhost", "X-Title": "DiscordBot"},
                    json=payload, timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    if resp.status == 429:
                        openrouter_blocked_until = time.time() + 60
                        return "OpenRouter vision rate limited.", True
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}"
                        continue
                    data = await resp.json()
                    msg_obj = data["choices"][0]["message"]
                    reply = msg_obj.get("content") or msg_obj.get("reasoning")
                    if reply and reply.strip():
                        return reply.strip(), False
            except Exception as e:
                last_error = str(e)
                continue
    return f"OpenRouter vision failed: {last_error}", True

# --- MULTI-ENGINE VOICE & TTS SYSTEM ------------------

def clean_tts_text(text: str, keep_direction_tags: bool = False) -> str:
    """Clean markdown and emojis from LLM reply for crisp TTS narration."""
    if not text:
        return ""
    t = text
    t = re.sub(r'```[\s\S]*?```', '', t)
    t = re.sub(r'`[^`]*`', '', t)
    t = re.sub(r'\|\|SPLIT\|\|', ' ', t)
    t = re.sub(r'<a?:[a-zA-Z0-9_]+:[0-9]+>', '', t)
    t = re.sub(r'<@!?\d+>', '', t)
    t = re.sub(r'<#\d+>', '', t)
    t = re.sub(r'<@&\d+>', '', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'[\U00010000-\U0010ffff]', '', t)
    t = re.sub(r'[\u2600-\u26FF\u2700-\u27BF]', '', t)
    t = re.sub(r'#+\s*', '', t)
    if not keep_direction_tags:
        t = re.sub(r'\*[^*]+\*', '', t)
        t = re.sub(r'\([^)]+\)', '', t)
        t = re.sub(r'\[[^\]]+\]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

async def speak_elevenlabs(text: str, voice_id: str = None, model: str = None, cfg: dict = None) -> bytes:
    c = cfg or DEFAULT_CONFIG
    key = (c.get("elevenlabs_key") or c.get("elevenlabs_api_key") or OWNER_KEYS.get("ELEVENLABS_KEY") or "").strip()
    if not key:
        return None
    c = cfg or DEFAULT_CONFIG
    selected_voice = voice_id or c.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM") or "21m00Tcm4TlvDq8ikWAM"
    selected_model = model or c.get("elevenlabs_model", "eleven_turbo_v2_5") or "eleven_turbo_v2_5"
    tts_text = clean_tts_text(text, keep_direction_tags=False)[:1500] or text[:400]
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice}",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json={
                    "text": tts_text,
                    "model_id": selected_model,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.2, "use_speaker_boost": True}
                },
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            pass
    return None

async def speak_openai(text: str, voice: str = None, model: str = None, cfg: dict = None) -> bytes:
    c = cfg or DEFAULT_CONFIG
    key = (c.get("openai_key") or c.get("openai_api_key") or OWNER_KEYS.get("OPENAI_KEY") or "").strip()
    if not key or key.startswith("sk-or-"):
        return None
    selected_voice = voice or c.get("openai_voice", "nova") or "nova"
    selected_model = model or c.get("openai_model", "tts-1") or "tts-1"
    tts_text = clean_tts_text(text, keep_direction_tags=False)[:1200] or text[:400]
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": selected_model, "voice": selected_voice, "input": tts_text, "response_format": "mp3"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            pass
    return None

async def speak_cartesia(text: str, voice_id: str = None, model: str = None, cfg: dict = None) -> bytes:
    c = cfg or DEFAULT_CONFIG
    key = (c.get("cartesia_key") or OWNER_KEYS.get("CARTESIA_KEY") or "").strip()
    if not key:
        return None
    c = cfg or DEFAULT_CONFIG
    selected_voice = voice_id or c.get("cartesia_voice_id", "a0e99841-438c-4a64-b679-ae501e7d6091") or "a0e99841-438c-4a64-b679-ae501e7d6091"
    selected_model = model or c.get("cartesia_model", "sonic-3.5") or "sonic-3.5"
    tts_text = clean_tts_text(text, keep_direction_tags=False)[:1200] or text[:400]
    async with aiohttp.ClientSession() as session:
        for try_model in [selected_model, "sonic-3.5", "sonic-3", "sonic-turbo"]:
            try:
                async with session.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers={"X-API-Key": key, "Cartesia-Version": "2024-11-13", "Content-Type": "application/json"},
                    json={
                        "model_id": try_model,
                        "transcript": tts_text,
                        "voice": {"mode": "id", "id": selected_voice},
                        "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 24000}
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        return await resp.read()
            except Exception:
                pass
    return None

async def speak_groq(text: str, voice: str = None, model: str = None, cfg: dict = None) -> bytes:
    c = cfg or DEFAULT_CONFIG
    key = (c.get("groq_key") or c.get("groq_api_key") or OWNER_KEYS.get("GROQ_KEY") or "").strip()
    if not key:
        return None
    c = cfg or DEFAULT_CONFIG
    selected_voice = voice or c.get("groq_tts_voice", "hannah") or "hannah"
    selected_model = model or c.get("groq_tts_model", "canopylabs/orpheus-v1-english") or "canopylabs/orpheus-v1-english"
    tts_text = clean_tts_text(text, keep_direction_tags=True)[:900] or text[:300]
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.groq.com/openai/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": selected_model, "voice": selected_voice, "input": tts_text, "response_format": "wav"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            pass
    return None

async def speak_edge(text: str, voice: str = None, cfg: dict = None) -> bytes:
    if not EDGE_TTS_AVAILABLE or edge_tts is None:
        return None
    c = cfg or DEFAULT_CONFIG
    selected_voice = voice or c.get("edge_tts_voice", "en-US-AvaMultilingualNeural") or "en-US-AvaMultilingualNeural"
    tts_text = clean_tts_text(text, keep_direction_tags=False)[:1200] or text[:400]
    try:
        comm = edge_tts.Communicate(tts_text, selected_voice)
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if chunks:
            return b"".join(chunks)
    except Exception:
        pass
    return None

async def speak_fish(text: str, cfg: dict = None) -> bytes:
    c = cfg or DEFAULT_CONFIG
    key = (c.get("fish_audio_key") or c.get("fish_key") or OWNER_KEYS.get("FISH_AUDIO_KEY") or "").strip()
    if not key:
        return None
    c = cfg or DEFAULT_CONFIG
    voice_id = c.get("fish_voice_id", "").strip()
    if not voice_id:
        return None
    tts_text = clean_tts_text(text, keep_direction_tags=False)[:900] or text[:900]
    model = c.get("fish_model", "s2.1-pro-free")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://api.fish.audio/v1/tts",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "model": model},
                json={"text": tts_text, "reference_id": voice_id, "format": "mp3"},
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            pass
    return None

async def speak(text: str, cfg: dict) -> bytes:
    """Unified multi-engine TTS router with fast fallback."""
    if not cfg.get("tts_enabled", False):
        return None
    provider = (cfg.get("tts_provider") or "auto").lower().strip()
    data = None

    if provider == "elevenlabs":
        data = await speak_elevenlabs(text, cfg=cfg)
        if not data:
            data = await speak_edge(text, cfg=cfg)
    elif provider == "openai":
        data = await speak_openai(text, cfg=cfg)
        if not data:
            data = await speak_edge(text, cfg=cfg)
    elif provider == "cartesia":
        data = await speak_cartesia(text, cfg=cfg)
        if not data:
            data = await speak_edge(text, cfg=cfg)
    elif provider == "groq":
        data = await speak_groq(text, cfg=cfg)
        if not data:
            data = await speak_edge(text, cfg=cfg)
    elif provider == "edge":
        data = await speak_edge(text, cfg=cfg)
    elif provider == "fish":
        data = await speak_fish(text, cfg=cfg)
        if not data:
            data = await speak_edge(text, cfg=cfg)
    else:  # auto mode
        if OWNER_KEYS.get("ELEVENLABS_KEY"):
            data = await speak_elevenlabs(text, cfg=cfg)
        if not data and OWNER_KEYS.get("OPENAI_KEY") and not OWNER_KEYS.get("OPENAI_KEY", "").startswith("sk-or-"):
            data = await speak_openai(text, cfg=cfg)
        if not data and OWNER_KEYS.get("CARTESIA_KEY"):
            data = await speak_cartesia(text, cfg=cfg)
        if not data and OWNER_KEYS.get("GROQ_KEY"):
            data = await speak_groq(text, cfg=cfg)
        if not data and EDGE_TTS_AVAILABLE:
            data = await speak_edge(text, cfg=cfg)
        if not data and OWNER_KEYS.get("FISH_AUDIO_KEY") and cfg.get("fish_voice_id"):
            data = await speak_fish(text, cfg=cfg)

    return data

# --- WEB SEARCH (DuckDuckGo Lite) --------------------

async def web_search(query, max_results=5):
    """Returns (results_list, error_str). results_list is [] on error."""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://lite.duckduckgo.com/lite/"
            payload = {"q": query, "kl": "us-en"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            async with session.post(url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                html = await resp.text()
                if resp.status != 200:
                    return [], f"DuckDuckGo returned HTTP {resp.status}"
                results = []
                rows = re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*result-link[^"]*"[^>]*>(.*?)</a>'
                    r'.*?<td[^>]*class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>',
                    html, re.DOTALL | re.IGNORECASE
                )
                for href, title_raw, snippet_raw in rows[:max_results]:
                    title = unescape(re.sub(r'<[^>]+>', '', title_raw).strip())
                    snippet = unescape(re.sub(r'<[^>]+>', '', snippet_raw).strip())
                    if href.startswith("/"):
                        href = "https://lite.duckduckgo.com" + href
                    if title and snippet:
                        results.append({"title": title, "url": href, "snippet": snippet})
                if not results:
                    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
                    seen = set()
                    for href, title_raw in links:
                        if "duckduckgo.com" in href or href.startswith("/"):
                            continue
                        title = unescape(re.sub(r'<[^>]+>', '', title_raw).strip())
                        if title and href not in seen and len(seen) < max_results:
                            seen.add(href)
                            results.append({"title": title, "url": href, "snippet": ""})
                return results, ""
    except Exception as e:
        return [], f"Search failed: {str(e)}"

# --- PERSONALITY SCRAPER & WIKI PULLER ----------------

def clean_html_for_lore(html: str, base_url: str = "") -> dict:
    """Extracts title, meta description, lead image, and cleaned body text from HTML."""
    if not html:
        return {"title": "", "desc": "", "image_url": "", "text": ""}
    
    title_match = (
        re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.I) or
        re.search(r'<meta\s+name=["\']twitter:title["\']\s+content=["\'](.*?)["\']', html, re.I) or
        re.search(r'<title[^>]*>(.*?)</title>', html, re.I)
    )
    title = unescape(title_match.group(1).strip()) if title_match else ""
    for sep in [" - ", " | ", " – ", " — "]:
        if sep in title:
            title = title.split(sep)[0].strip()

    desc_match = (
        re.search(r'<meta\s+(?:name|property)=["\'](?:description|og:description|twitter:description)["\']\s+content=["\'](.*?)["\']', html, re.I)
    )
    desc = unescape(desc_match.group(1).strip()) if desc_match else ""

    img_match = (
        re.search(r'<meta\s+(?:property|name)=["\'](?:og:image|twitter:image)["\']\s+content=["\'](.*?)["\']', html, re.I) or
        re.search(r'<img[^>]+class=["\'][^"\']*(?:pi-image-thumbnail|infobox-image|character-image|thumbimage)[^"\']*["\'][^>]+src=["\'](.*?)["\']', html, re.I) or
        re.search(r'<table[^>]*class=["\'][^"\']*infobox[^"\']*["\'][^>]*>.*?<img[^>]+src=["\'](.*?)["\']', html, re.I | re.DOTALL)
    )
    image_url = unescape(img_match.group(1).strip()) if img_match else ""
    if image_url.startswith("//"):
        image_url = "https:" + image_url
    elif image_url.startswith("/") and base_url:
        parsed_base = urllib.parse.urlparse(base_url)
        image_url = f"{parsed_base.scheme}://{parsed_base.netloc}{image_url}"

    # Remove non-content tags and comments
    clean = re.sub(r'<(script|style|noscript|svg|nav|footer|header|aside|form|iframe|canvas)[^>]*>.*?</\1>', ' ', html, flags=re.I | re.DOTALL)
    clean = re.sub(r'<!--.*?-->', ' ', clean, flags=re.DOTALL)
    clean = re.sub(r'<div[^>]*class=["\'][^"\']*(?:navbox|toc|mw-jump-link|mw-editsection)[^"\']*["\'][^>]*>.*?</div>', ' ', clean, flags=re.I | re.DOTALL)
    clean = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n\n# \1\n', clean, flags=re.I)
    clean = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', clean, flags=re.I)
    clean = re.sub(r'<li[^>]*>(.*?)</li>', r'\n* \1', clean, flags=re.I)
    clean = re.sub(r'<br\s*/?>', '\n', clean, flags=re.I)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = unescape(clean)
    lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in clean.split('\n')]
    clean_text = '\n'.join([l for l in lines if l])

    return {
        "title": title,
        "desc": desc,
        "image_url": image_url,
        "text": clean_text[:20000]
    }

async def fetch_webpage_lore(url: str) -> dict:
    """Fetches webpage content with special Wikipedia / Fandom / anime wiki support."""
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    # 1. Special case: Wikipedia summary API
    wiki_match = re.search(r'wikipedia\.org/wiki/([^#?]+)', url, re.I)
    if wiki_match:
        page_title = urllib.parse.unquote(wiki_match.group(1))
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title)}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers={"User-Agent": "BotSaaS/1.0 (personality-puller)"}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        wdata = await resp.json()
                        wtitle = wdata.get("title", page_title.replace("_", " "))
                        wextract = wdata.get("extract", "")
                        wdesc = wdata.get("description", "")
                        wimg = (wdata.get("originalimage") or wdata.get("thumbnail") or {}).get("source", "")
                        return {
                            "title": wtitle,
                            "desc": wdesc or (wextract[:140] if wextract else ""),
                            "image_url": wimg,
                            "text": f"Character: {wtitle}\nDescription: {wdesc}\n\nSummary:\n{wextract}",
                            "source_url": url
                        }
        except Exception:
            pass

    # 2. General URL fetch
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=18), allow_redirects=True) as resp:
                if resp.status != 200:
                    return {"title": "", "desc": "", "image_url": "", "text": f"HTTP {resp.status} error fetching URL", "source_url": url, "error": f"HTTP {resp.status}"}
                html = await resp.text()
                parsed = clean_html_for_lore(html, base_url=str(resp.url))
                parsed["source_url"] = str(resp.url)
                return parsed
    except Exception as e:
        return {"title": "", "desc": "", "image_url": "", "text": "", "source_url": url, "error": str(e)}

async def pull_personality_from_link(url: str, instruction: str = None, cfg: dict = None) -> tuple[dict, str]:
    """
    Fetches character lore from a wiki/link and uses AI to synthesize a complete character card.
    Returns (character_dict, error_str).
    """
    page_data = await fetch_webpage_lore(url)
    if not page_data or (not page_data.get("text") and not page_data.get("title")):
        err = page_data.get("error") or "Could not fetch text from the provided link."
        return None, err

    title = page_data.get("title") or "Character"
    page_desc = page_data.get("desc") or ""
    page_img = page_data.get("image_url") or ""
    page_text = page_data.get("text") or ""

    user_instruction = instruction.strip() if instruction else ""

    prompt_content = f"""Character / Subject Name: {title}
Source URL: {url}
Meta Description: {page_desc}

Article Content:
{page_text[:20000]}

{f'Special User Instructions: {user_instruction}' if user_instruction else ''}

Please analyze this character data and output a rich, accurate Character Persona Card in STRICT JSON FORMAT.
JSON format:
{{
  "name": "{title}",
  "role": "Role / Archetype tag (e.g. Yandere Companion, Sorceress, Detective, Caretaker)",
  "desc": "Short 1-2 sentence description (under 140 chars)",
  "personality": "Comprehensive personality specification & system prompt for an AI roleplay bot. Detail demeanor, psychology, behavioral nuances, speaking mannerisms, speech quirks, and interaction rules.",
  "greeting": "An expressive, immersive first greeting message in character (using *actions* and spoken dialogue).",
  "scenario": "Setting / initial context",
  "example_dialogue": "Short dialogue example using <START> {{{{user}}}}: ... {{{{char}}}}: ... format",
  "tags": ["Tag1", "Tag2"],
  "avatar_url": "{page_img}"
}}
Return ONLY valid JSON with no markdown backticks."""

    sys_msg = "You are an expert AI persona architect and character card creator. You convert wiki articles, lore pages, and character biographies into rich, vivid roleplay character cards in JSON."

    effective_cfg = DEFAULT_CONFIG.copy()
    if cfg and isinstance(cfg, dict):
        effective_cfg.update(cfg)

    # Try calling AI LLMs
    reply = ""
    err = None

    for prov in [effective_cfg.get("provider", "auto"), "gemini", "groq", "mistral", "openrouter", "openai", "custom"]:
        if not reply:
            try:
                if prov == "gemini" or (prov == "auto" and OWNER_KEYS.get("GEMINI_KEY")):
                    reply, err = await ask_gemini(sys_msg, [], prompt_content, effective_cfg)
                elif prov == "groq" or (prov == "auto" and OWNER_KEYS.get("GROQ_KEY")):
                    reply, err = await ask_groq([], prompt_content, effective_cfg, system_msg=sys_msg)
                elif prov == "mistral" or (prov == "auto" and OWNER_KEYS.get("MISTRAL_KEY")):
                    reply, err = await ask_mistral([], prompt_content, effective_cfg, system_msg=sys_msg)
                elif prov == "openrouter" or (prov == "auto" and OWNER_KEYS.get("OPENROUTER_KEY")):
                    reply, err = await ask_openrouter([], prompt_content, effective_cfg, system_msg=sys_msg)
                elif prov == "openai" or (prov == "auto" and OWNER_KEYS.get("OPENAI_KEY")):
                    reply, err = await ask_openai([], prompt_content, effective_cfg, system_msg=sys_msg)
                elif prov in ("custom", "literouter") and effective_cfg.get("custom_base_url"):
                    reply, err = await ask_custom([], prompt_content, effective_cfg, system_msg=sys_msg)
            except Exception as e:
                err = str(e)
                continue

    # Clean LLM response and parse JSON
    parsed_json = None
    if reply:
        clean_json_str = reply.strip()
        if "```" in clean_json_str:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_json_str)
            if match:
                clean_json_str = match.group(1).strip()
        try:
            parsed_json = json.loads(clean_json_str)
        except Exception:
            match = re.search(r'(\{[\s\S]*\})', clean_json_str)
            if match:
                try:
                    parsed_json = json.loads(match.group(1))
                except Exception:
                    pass

    # Fallback to heuristic synthesis if LLM was unavailable or failed
    if not parsed_json or not isinstance(parsed_json, dict):
        role_guess = "AI Companion"
        if "yandere" in page_text.lower(): role_guess = "Yandere Companion"
        elif "tsundere" in page_text.lower(): role_guess = "Tsundere Companion"
        elif "caretaker" in page_text.lower(): role_guess = "Caretaker Companion"
        elif "detective" in page_text.lower(): role_guess = "Detective"

        short_d = page_desc[:140] if page_desc else (page_text[:137] + "..." if len(page_text) > 137 else page_text)
        greeting_text = f"*looks up and smiles warmly* Hello, I am {title}. What would you like to talk about today?"

        sys_prompt = f"[Character: {title}]\n[Role: {role_guess}]\n[Description & Lore:\n{page_text[:3000]}]"

        parsed_json = {
            "name": title,
            "role": role_guess,
            "desc": short_d,
            "personality": sys_prompt,
            "greeting": greeting_text,
            "scenario": f"You are interacting with {title}.",
            "example_dialogue": f"<START>\n{{{{user}}}}: Hello {title}!\n{{{{char}}}}: {greeting_text}",
            "tags": [role_guess],
            "avatar_url": page_img
        }

    if not parsed_json.get("avatar_url") and page_img:
        parsed_json["avatar_url"] = page_img

    return parsed_json, None

# --- AUDIO TRANSCRIPTION (Groq Whisper) --------------

async def transcribe_audio(audio_bytes, filename="audio.ogg"):
    """Returns (text, error_str). Uses Groq Whisper."""
    key = OWNER_KEYS.get("GROQ_KEY")
    if not key:
        return None, "Groq API key not configured."
    ext = Path(filename).suffix.lower() or ".ogg"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(tmp_fd)
    try:
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)
        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        if size_mb > MAX_AUDIO_SIZE_MB:
            return None, f"Audio too large ({size_mb:.1f} MB). Max: {MAX_AUDIO_SIZE_MB} MB."
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", open(tmp_path, "rb"), filename=filename, content_type=f"audio/{ext.lstrip('.')}")
            data.add_field("model", "whisper-large-v3")
            async with session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data=data, timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return None, f"Transcription failed: {text[:300]}"
                result = await resp.json()
                return result.get("text", ""), None
    except Exception as e:
        return None, f"Transcription error: {e}"
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# --- AUTO-SEARCH HELPERS ------------------------------

REALTIME_KEYWORDS = [
    "weather", "forecast", "temperature", "rain", "snow", "sunny",
    "news", "latest", "breaking", "today", "yesterday", "this week",
    "stock", "price", "crypto", "bitcoin", "ethereum", "market",
    "score", "game", "match", "won", "lost", "vs", "playing",
    "who won", "who is", "what happened", "current", "right now",
    "live", "update", "election", "release date", "when did",
    "how much is", "where is", "directions", "hours", "open now",
]

REFUSAL_PATTERNS = [
    "i don't know", "i do not know", "i'm not sure", "i am not sure",
    "i don't have", "i do not have", "i cannot access", "i can't access",
    "i don't have access", "my knowledge cutoff", "my training data",
    "i'm unable to", "i am unable to", "i cannot provide", "i can't provide",
    "i don't have real-time", "i do not have real-time", "as an ai",
]

def needs_realtime_data(query):
    q = (query or "").lower()
    return any(kw in q for kw in REALTIME_KEYWORDS)

def should_retry_with_search(reply):
    if not reply:
        return False
    r = reply.lower()
    return any(p in r for p in REFUSAL_PATTERNS)

# --- FILE TEXT EXTRACTION -----------------------------

def extract_text_from_pdf(filepath, max_pages=20):
    try:
        import PyPDF2
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            pages_to_read = min(total_pages, max_pages)
            for i in range(pages_to_read):
                t = reader.pages[i].extract_text()
                if t:
                    text += f"--- Page {i+1} ---\n" + t + "\n\n"
        if text.strip():
            return text.strip()
    except Exception:
        pass
    return "[PDF: Could not extract readable text]"

def extract_text_from_docx(filepath):
    try:
        text_parts = []
        with zipfile.ZipFile(filepath, "r") as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    if t.text:
                        text_parts.append(t.text)
        return " ".join(text_parts).strip()
    except Exception as e:
        return f"[DOCX error: {e}]"

def extract_text_from_csv(filepath, max_rows=2000):
    try:
        rows = []
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(" | ".join(row))
        return "\n".join(rows[:max_rows])
    except Exception as e:
        return f"[CSV error: {e}]"

async def read_file_attachment(attachment):
    size_mb = attachment.size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return f"File too large ({size_mb:.1f} MB). Max: {MAX_FILE_SIZE_MB} MB."
    ext = Path(attachment.filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".csv"):
        return f"Unsupported file type: {ext}."
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(tmp_fd)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    return f"Failed to download file (HTTP {resp.status})."
                data = await resp.read()
                with open(tmp_path, "wb") as f:
                    f.write(data)
        if ext == ".pdf":
            text = extract_text_from_pdf(tmp_path, max_pages=20)
        elif ext == ".docx":
            text = extract_text_from_docx(tmp_path)
        elif ext == ".csv":
            text = extract_text_from_csv(tmp_path, max_rows=2000)
        else:
            text = "Unknown file type."
        
        if not text or not text.strip():
            return "I couldn't extract any readable text from that file."
        if text.startswith("[") and text.endswith("]"):
            return text
        preview = text[:120000]
        if len(text) > 120000:
            preview += f"\n\n... [{len(text) - 120000} more characters truncated]"
        return preview
    except Exception as e:
        return f"File read error: {e}"
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# --- FIELD MAPPINGS FOR MENTION / CONFIG COMMANDS -----
CONFIG_FIELD_MAPPINGS = {
    # Gemini
    "gemini": "gemini_model",
    "gemini_model": "gemini_model",
    "gemini-model": "gemini_model",
    "geminimodel": "gemini_model",
    "gemini_key": "gemini_key",
    
    # Groq
    "groq": "groq_model",
    "groq_model": "groq_model",
    "groq-model": "groq_model",
    "groqmodel": "groq_model",
    "groq_key": "groq_key",
    
    # Mistral
    "mistral": "mistral_model",
    "mistral_model": "mistral_model",
    "mistral-model": "mistral_model",
    "mistralmodel": "mistral_model",
    "mistral_key": "mistral_key",
    
    # OpenAI
    "openai": "openai_chat_model",
    "openai_model": "openai_chat_model",
    "openai-model": "openai_chat_model",
    "openaichat": "openai_chat_model",
    "openai_chat_model": "openai_chat_model",
    "openai-chat-model": "openai_chat_model",
    "gpt": "openai_chat_model",
    "openai_key": "openai_key",
    "openaikey": "openai_key",
    "openai_api_key": "openai_key",
    "openai-key": "openai_key",
    "openai_vision": "openai_vision_model",
    "openai_vision_model": "openai_vision_model",
    "openai_base_url": "openai_base_url",
    
    # DeepSeek
    "deepseek": "deepseek_model",
    "deepseek_model": "deepseek_model",
    "deepseek-model": "deepseek_model",
    "deepseekmodel": "deepseek_model",
    "deepseek_key": "deepseek_key",
    "deepseekkey": "deepseek_key",
    "deepseek_api_key": "deepseek_key",
    "deepseek-key": "deepseek_key",
    "deepseek_base_url": "deepseek_base_url",
    "r1": "deepseek_model",
    "v3": "deepseek_model",
    
    # Custom Endpoint / LiteRouter / Local Tunnels / OpenAI-Compatible
    "custom_base_url": "custom_base_url",
    "custom_endpoint": "custom_base_url",
    "custom_url": "custom_base_url",
    "base_url": "custom_base_url",
    "base-url": "custom_base_url",
    "baseurl": "custom_base_url",
    "endpoint": "custom_base_url",
    "api_url": "custom_base_url",
    "api_endpoint": "custom_base_url",
    "literouter": "custom_base_url",
    "literouter_url": "custom_base_url",
    
    "custom_key": "custom_key",
    "custom_api_key": "custom_key",
    "custom-key": "custom_key",
    "customkey": "custom_key",
    "custom_token": "custom_key",
    "token": "custom_key",
    "api_key": "custom_key",
    "apikey": "custom_key",
    
    "custom_model": "custom_model",
    "custom-model": "custom_model",
    "custommodel": "custom_model",
    "model_name": "custom_model",
    "modelname": "custom_model",
    "custom": "custom_model",
    
    # OpenRouter / Custom Model
    "model": "model",
    "openrouter": "model",
    "openrouter_model": "model",
    "openrouter-model": "model",
    "openrouter_key": "openrouter_key",
    
    # Hugging Face
    "hf": "huggingface_model",
    "huggingface": "huggingface_model",
    "huggingface_model": "huggingface_model",
    "hf_model": "huggingface_model",
    "hf_key": "hf_key",
    
    # Provider
    "provider": "provider",
    "engine": "provider",
    "ai_provider": "provider",
    
    # Vision
    "vision": "gemini_vision_model",
    "vision_model": "vision_model",
    "gemini_vision": "gemini_vision_model",
    "gemini_vision_model": "gemini_vision_model",
    "vision_provider": "vision_provider",
    
    # Personality / System Prompt
    "personality": "personality",
    "prompt": "personality",
    "system": "personality",
    "system_prompt": "personality",
    "persona": "personality",
    
    # Voice / TTS Settings
    "tts": "tts_provider",
    "tts_provider": "tts_provider",
    "voice": "fish_voice_id",
    "fish_voice": "fish_voice_id",
    "fish_voice_id": "fish_voice_id",
    "fish_model": "fish_model",
    "elevenlabs_voice": "elevenlabs_voice_id",
    "elevenlabs_voice_id": "elevenlabs_voice_id",
    "elevenlabs_model": "elevenlabs_model",
    "openai_voice": "openai_voice",
    "cartesia_voice": "cartesia_voice_id",
    "cartesia_voice_id": "cartesia_voice_id",
    "cartesia_model": "cartesia_model",
    "groq_voice": "groq_tts_voice",
    "groq_tts_voice": "groq_tts_voice",
    "edge_voice": "edge_tts_voice",
    "edge_tts_voice": "edge_tts_voice",
    
    # Generation parameters
    "temperature": "temperature",
    "temp": "temperature",
    "max_tokens": "max_tokens",
    "tokens": "max_tokens",
    "max_token": "max_tokens",
    "top_p": "top_p",
    "frequency_penalty": "frequency_penalty",
    "presence_penalty": "presence_penalty",
    "cooldown": "cooldown_seconds",
    "cooldown_seconds": "cooldown_seconds",
    "max_context": "max_context",
    "context": "max_context",
    "context_enabled": "context_enabled",
    "tts_enabled": "tts_enabled",
    "vision_enabled": "vision_enabled",
    "auto_search": "auto_search",
    "open_chat": "open_chat_enabled",
    "open_chat_enabled": "open_chat_enabled",
    "bot_name_triggers": "bot_name_triggers",
    "triggers": "bot_name_triggers",
    "name_triggers": "bot_name_triggers",
    "bot_triggers": "bot_name_triggers",
    "bot_talk": "bot_conversation_enabled",
    "bot_talk_enabled": "bot_conversation_enabled",
    "bot_conversation": "bot_conversation_enabled",
    "bot_conversation_enabled": "bot_conversation_enabled",
    "bot_convo": "bot_conversation_enabled",
    "bot_conversation_max": "bot_conversation_max",
    "bot_talk_max": "bot_conversation_max",
}

# --- USER BOT CLASS -----------------------------------

class UserBot:
    def __init__(self, bot_id, token, data):
        self.bot_id = str(bot_id)
        self.token = token
        self.config = {**DEFAULT_CONFIG, **(data.get("config") or {})}
        raw_trig = self.config.get("bot_name_triggers", [])
        if isinstance(raw_trig, str):
            self.config["bot_name_triggers"] = [t.strip() for t in re.split(r'[,;\n]+', raw_trig) if t.strip()]
        elif isinstance(raw_trig, (list, tuple, set)):
            self.config["bot_name_triggers"] = [str(t).strip() for t in raw_trig if str(t).strip()]
        else:
            self.config["bot_name_triggers"] = []
        disk_data = {}
        path = os.path.join(USERS_DIR, f"{bot_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
            except Exception:
                pass

        self.bot_name = data.get("bot_name") or disk_data.get("bot_name", "Unknown")
        self.access_key = data.get("access_key") or disk_data.get("access_key", "") or self.bot_id
        self.owner_id = str(data.get("owner_id") or disk_data.get("owner_id", "")) if (data.get("owner_id") or disk_data.get("owner_id")) else None
        self.owner_username = str(data.get("owner_username") or data.get("owner_name") or disk_data.get("owner_username") or disk_data.get("owner_name") or (self.config.get("owner_username") if isinstance(self.config, dict) else "") or "")
        self.contexts = {}
        self.cooldowns = defaultdict(float)
        self.message_count = int(data.get("message_count", 0) or disk_data.get("message_count", 0) or data.get("interactions", 0) or disk_data.get("interactions", 0) or 0)
        self.start_time = time.time()
        self.last_interaction_time = time.time()
        self.user_last_interaction = defaultdict(float)
        self.bot_reply_counts = defaultdict(int)
        self.bot_reply_last_time = defaultdict(float)
        self.recent_sent_message_ids = set()
        self.interacted_users = set(data.get("interacted_users", []) or [])
        self._bg_tasks_started = False
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self.setup_events()
        self.setup_commands()

    def get_bot_triggers(self) -> list:
        """Returns a list of unique lowercase triggers for calling this bot by name."""
        triggers = set()

        def add_name_variants(name: str):
            if not name:
                return
            cleaned = str(name).strip()
            if not cleaned:
                return
            low = cleaned.lower()
            triggers.add(low)
            if "-" in low:
                triggers.add(low.replace("-", " "))
            if "_" in low:
                triggers.add(low.replace("_", " "))
            words = re.split(r'[\s\-_]+', cleaned)
            for w in words:
                w_low = w.strip().lower()
                if len(w_low) >= 2 and w_low not in ("the", "and", "for", "with"):
                    triggers.add(w_low)

        # 1. Discord client user names
        if getattr(self, "client", None) and self.client.user:
            if self.client.user.display_name:
                add_name_variants(self.client.user.display_name)
            if self.client.user.name:
                add_name_variants(self.client.user.name)

        # 2. bot_name attribute / config
        bname = getattr(self, "bot_name", None) or self.config.get("bot_name", "")
        if bname:
            add_name_variants(str(bname))

        # 3. bot_name_triggers from config
        raw_trig = self.config.get("bot_name_triggers", [])
        if isinstance(raw_trig, str):
            for t in re.split(r'[,;\n]+', raw_trig):
                add_name_variants(t)
        elif isinstance(raw_trig, (list, tuple, set)):
            for item in raw_trig:
                if isinstance(item, str):
                    for t in re.split(r'[,;\n]+', item):
                        add_name_variants(t)

        return [t for t in triggers if t]

    def is_name_called(self, text: str) -> bool:
        """Checks if any of the bot's name triggers are present in the text with proper boundaries."""
        if not text:
            return False
        text_lower = text.lower()
        triggers = self.get_bot_triggers()
        for trig in triggers:
            trig_clean = trig.strip()
            if not trig_clean:
                continue
            pattern = rf'(?<![a-zA-Z0-9]){re.escape(trig_clean)}(?![a-zA-Z0-9])'
            if re.search(pattern, text_lower):
                return True
        return False

    def is_idle(self, max_idle_hours: float = 8.0) -> bool:
        """Returns True if this bot instance has received no interaction for > max_idle_hours."""
        return (time.time() - self.last_interaction_time) > (max_idle_hours * 3600)

    def is_user_idle(self, user_id, max_idle_hours: float = 8.0) -> bool:
        """Returns True if the specific user has not interacted with this bot for > max_idle_hours."""
        last = self.user_last_interaction.get(str(user_id), 0)
        if last == 0:
            return True
        return (time.time() - last) > (max_idle_hours * 3600)

    def record_interaction(self, user_id):
        """Updates timestamps for active bot-user interaction."""
        now = time.time()
        uid = str(user_id)
        self.last_interaction_time = now
        self.user_last_interaction[uid] = now
        self.interacted_users.add(uid)

    def update_setting(self, raw_field: str, raw_value: str) -> tuple:
        """
        Updates a configuration key on this bot instance and auto-saves to disk.
        Returns: (success: bool, canonical_key: str, old_val: str, new_val_str: str)
        """
        field_norm = raw_field.lower().strip().replace(" ", "_")
        if field_norm not in CONFIG_FIELD_MAPPINGS:
            return False, raw_field, "", f"Unknown field '{raw_field}'"
        
        target_key = CONFIG_FIELD_MAPPINGS[field_norm]
        old_val = str(self.config.get(target_key, ""))
        val_str = str(raw_value).strip()
        
        try:
            if target_key in ("temperature", "top_p", "frequency_penalty", "presence_penalty", "message_split_delay", "random_chat_chance"):
                converted = float(val_str)
            elif target_key in ("max_tokens", "max_context", "cooldown_seconds", "random_dms_interval_minutes", "random_chat_context_limit", "message_split_min", "message_split_max", "bot_conversation_max"):
                converted = int(float(val_str))
            elif target_key in ("tts_enabled", "vision_enabled", "auto_search", "user_memory_enabled", "open_chat_enabled", "auto_stt", "message_split_enabled", "random_dms_enabled", "random_chat_enabled", "use_custom_model", "bot_conversation_enabled", "file_reading_enabled", "video_watching_enabled", "context_enabled"):
                converted = val_str.lower() in ("true", "1", "yes", "on", "enable", "enabled")
            elif target_key == "bot_name_triggers":
                if isinstance(val_str, list):
                    converted = [str(t).strip() for t in val_str if str(t).strip()][:20]
                else:
                    converted = [t.strip() for t in re.split(r'[,;\n]+', val_str) if t.strip()][:20]
            elif target_key == "provider":
                converted = val_str.lower()
                if converted in ("custom", "literouter", "local", "tunnel"):
                    converted = "custom"
                elif converted not in ("gemini", "groq", "mistral", "openai", "deepseek", "openrouter", "huggingface", "custom", "auto"):
                    converted = "auto"
            else:
                converted = val_str.strip('"\'')
            
            self.config[target_key] = converted
            self.save()
            return True, target_key, old_val, str(converted)
        except Exception as e:
            return False, target_key, old_val, f"Conversion error: {e}"

    def toggle_provider(self, target_provider: str = None) -> tuple:
        """Toggles or sets the active provider. Cycles if not provided."""
        old_provider = self.config.get("provider", "auto")
        CYCLE = ["auto", "gemini", "groq", "mistral", "openai", "deepseek", "openrouter", "huggingface", "custom"]
        if target_provider and target_provider.lower().strip() in CYCLE:
            new_provider = target_provider.lower().strip()
        elif target_provider and target_provider.lower().strip() in ("literouter", "local", "tunnel"):
            new_provider = "custom"
        else:
            try:
                curr_idx = CYCLE.index(old_provider)
                new_provider = CYCLE[(curr_idx + 1) % len(CYCLE)]
            except ValueError:
                new_provider = "auto"
        self.config["provider"] = new_provider
        self.save()
        return old_provider, new_provider

    def format_toast_embed(self, title: str, description: str, color: int = 0x00ffcc) -> discord.Embed:
        """Formats a compact, modern toast-style confirmation notification."""
        embed = discord.Embed(
            title=f"🍞 {title}",
            description=description,
            color=color
        )
        embed.set_footer(text=f"{self.bot_name} • Auto-saved to disk")
        return embed

    async def update_discord_profile(self, new_name: str = None, new_avatar_url: str = None):
        """Applies name or avatar changes made in Web Studio directly to the Discord Bot profile."""
        if not self.client or not self.client.is_ready() or not self.client.user:
            return
        
        edit_kwargs = {}
        
        if new_name and str(new_name).strip():
            clean_name = str(new_name).strip()[:32]
            if clean_name != self.client.user.name:
                edit_kwargs["username"] = clean_name
                
        if new_avatar_url and isinstance(new_avatar_url, str) and new_avatar_url.strip():
            pfp_str = new_avatar_url.strip()
            avatar_bytes = None
            try:
                if pfp_str.startswith("data:image/"):
                    header, encoded = pfp_str.split(",", 1)
                    avatar_bytes = base64.b64decode(encoded)
                elif pfp_str.startswith("http://") or pfp_str.startswith("https://"):
                    current_url = str(self.client.user.display_avatar.url) if (self.client.user and self.client.user.display_avatar) else ""
                    if pfp_str != current_url:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(pfp_str, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                                if resp.status == 200:
                                    avatar_bytes = await resp.read()
                if avatar_bytes:
                    edit_kwargs["avatar"] = avatar_bytes
            except Exception as e:
                print(f"[BOT {self.bot_id}] Failed to load avatar bytes: {e}")

        if edit_kwargs:
            try:
                await self.client.user.edit(**edit_kwargs)
                print(f"[BOT {self.bot_id}] Successfully updated Discord bot profile: {list(edit_kwargs.keys())}")
                if self.client.user:
                    self.bot_name = self.client.user.name
                    if self.client.user.display_avatar:
                        self.config["avatar_url"] = str(self.client.user.display_avatar.url)
                        self.config["pfp"] = self.config["avatar_url"]
                self.save()
            except discord.HTTPException as e:
                print(f"[BOT {self.bot_id}] Discord rate limit / API error editing profile: {e}")
            except Exception as e:
                print(f"[BOT {self.bot_id}] Error updating Discord bot profile: {e}")

    async def generate_and_send_welcome(self, member: discord.Member, target_channel=None, is_test=False, trigger_user=None):
        """Generates and sends an AI-enhanced welcome greeting that strictly preserves #channels, mentions, and links."""
        welcome_cfg = self.config.get("welcome_settings") or {}
        guild_id_str = str(member.guild.id)
        g_cfg = welcome_cfg.get(guild_id_str) or {}

        # Strict enabled check: Must be explicitly enabled for this bot in this guild!
        is_enabled = bool(g_cfg.get("enabled", False))
        if not is_enabled and not is_test:
            return False, "Welcome greetings are disabled for this bot in this server."

        # Global deduplication: Prevent multiple bots from double-greeting the same join
        join_key = f"{member.guild.id}:{member.id}"
        now = time.time()
        if not is_test:
            if join_key in WELCOME_DEDUPLICATION_CACHE and (now - WELCOME_DEDUPLICATION_CACHE[join_key] < 90.0):
                print(f"[BOT {self.bot_id}] Suppressed duplicate welcome for {member.display_name} in {member.guild.name}")
                return False, "Member already greeted by another bot recently."
            WELCOME_DEDUPLICATION_CACHE[join_key] = now

        # Find target channel
        channel = target_channel
        if not channel:
            channel_id = g_cfg.get("channel_id") or self.config.get("welcome_channel_id")
            if channel_id:
                try:
                    channel = member.guild.get_channel(int(channel_id))
                    if not channel:
                        channel = await self.client.fetch_channel(int(channel_id))
                except Exception:
                    channel = None

        if not channel:
            channel = member.guild.system_channel
        if not channel:
            for ch in member.guild.text_channels:
                perms = ch.permissions_for(member.guild.me)
                if perms.send_messages:
                    channel = ch
                    break

        if not channel:
            return False, "Could not find a valid text channel to send the greeting."

        base_msg = g_cfg.get("message") or self.config.get("welcome_message") or "Welcome! Please check out the server and make yourself at home."
        ai_enhance = g_cfg.get("ai_enhance", self.config.get("welcome_ai_enhance", True))
        ping_member = g_cfg.get("ping_member", self.config.get("welcome_ping", True))

        # Extract all channels, URLs, and role mentions to guarantee preservation
        urls = re.findall(r'https?://[^\s]+', base_msg)
        channel_mentions = re.findall(r'<#\d+>', base_msg)
        channel_names = re.findall(r'(?<!<)#[\w\-]+', base_msg)
        role_mentions = re.findall(r'<@&\d+>', base_msg)
        special_entities = list(dict.fromkeys(channel_mentions + channel_names + urls + role_mentions))

        greeting_text = ""
        if ai_enhance:
            sys_prompt = self.config.get("personality") or "You are a helpful and engaging Discord AI companion."
            preserve_notice = ""
            if special_entities:
                preserve_notice = (
                    f"\nCRITICAL REQUIREMENT: You MUST keep and include these exact channel names, channel mentions, and links without modifying, removing, or omitting them: {', '.join(special_entities)}"
                )

            prompt_for_ai = (
                f"A new member named '{member.display_name}' has joined the Discord server '{member.guild.name}'.\n"
                f"Admin guidance/rules note: \"{base_msg}\"{preserve_notice}\n\n"
                f"Instructions:\n"
                f"1. Generate a short, warm, in-character greeting (1-3 sentences) welcoming this new member in your unique personality/voice ({sys_prompt}).\n"
                f"2. Seamlessly include the admin's note/rules and strictly retain all channel tags (e.g. #channel, <#...>) and URLs (https://...) exactly as given.\n"
                f"3. Do not output meta explanations or system tags."
            )

            try:
                ai_reply, err = await self.ask_ai(
                    channel.id, prompt_for_ai, user_id=member.id, user_name=member.display_name,
                    guild=member.guild, is_dm=False
                )
                if not err and ai_reply and len(ai_reply.strip()) > 3:
                    greeting_text = ai_reply.strip()
                    # Post-processing entity preservation check: ensure no channels or links were lost
                    missing = [e for e in special_entities if e not in greeting_text]
                    if missing:
                        greeting_text += " " + " ".join(missing)
            except Exception as e:
                print(f"[BOT {self.bot_id}] AI greeting generation error: {e}")

        if not greeting_text:
            greeting_text = base_msg.replace("{user}", member.display_name).replace("{server}", member.guild.name)

        final_msg = f"{member.mention} {greeting_text}" if ping_member else greeting_text

        if is_test:
            test_tag = f" *(🧪 Test Greeting triggered by {trigger_user.mention})*" if trigger_user else " *(🧪 Test Greeting)*"
            final_msg += f"\n{test_tag}"

        try:
            await channel.send(final_msg)
            record_bot_interaction(self.bot_id)
            print(f"[BOT {self.bot_id}] Welcomed member {member.display_name} in {member.guild.name} (#{channel.name})")
            return True, f"Sent greeting to <#{channel.id}>"
        except Exception as send_err:
            print(f"[BOT {self.bot_id}] Failed to send welcome message: {send_err}")
            return False, f"Failed to send: {send_err}"

    def setup_events(self):
        @self.client.event
        async def on_ready():
            print(f"[BOT {self.bot_id}] {self.client.user} is online")
            try:
                if self.client.user and self.client.user.display_avatar:
                    self.config["avatar_url"] = str(self.client.user.display_avatar.url)
            except Exception:
                pass
            try:
                app_info = await self.client.application_info()
                if app_info and app_info.owner:
                    self.owner_username = str(app_info.owner.name or app_info.owner.display_name or self.owner_username)
            except Exception:
                pass
            try:
                self.save()
            except Exception:
                pass
            try:
                synced = await self.tree.sync()
                print(f"[BOT {self.bot_id}] Synced {len(synced)} slash commands")
            except Exception as e:
                print(f"[BOT {self.bot_id}] Sync error: {e}")
            if not self._bg_tasks_started:
                self._bg_tasks_started = True
                self.client.loop.create_task(self.random_dm_loop())
                self.client.loop.create_task(self.random_chat_loop())

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            await self.handle_message(message)

        @self.client.event
        async def on_member_join(member: discord.Member):
            if member.bot:
                return
            await self.generate_and_send_welcome(member)

    def setup_commands(self):
        @self.tree.command(name="ask", description="Ask the AI anything. Attach an image for vision.")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.describe(prompt="Your question or prompt", image="Optional image to analyze")
        async def slash_ask(interaction: discord.Interaction, prompt: str, image: discord.Attachment = None):
            self.record_interaction(interaction.user.id)
            ok, remaining = self.check_cooldown(interaction.user.id)
            if not ok:
                await interaction.response.send_message(f"Slow down! Wait {remaining}s.", ephemeral=True)
                return
            await interaction.response.defer(thinking=True)
            images = []
            if self.config.get("vision_enabled") and image:
                img_data, mime = await download_image(image.url)
                if img_data:
                    images.append((img_data, mime))
            
            if self.config.get("user_memory_enabled", True):
                await update_user_profile(interaction.user, prompt, interaction.guild, client=self.client, bot_config=self.config)
            is_dm = isinstance(interaction.channel, discord.DMChannel)
            reply, err = await self.ask_ai(
                interaction.channel_id, prompt, images=images,
                user_id=interaction.user.id, user_name=interaction.user.display_name,
                guild=interaction.guild, is_dm=is_dm
            )
            if err:
                await interaction.followup.send(reply)
                return
            chunks = [reply[i:i+2000] for i in range(0, len(reply), 2000)]
            await interaction.followup.send(chunks[0])
            for c in chunks[1:]:
                await interaction.followup.send(c)
            if self.config.get("tts_enabled"):
                audio = await speak(reply, self.config)
                if audio:
                    await interaction.followup.send(file=discord.File(io.BytesIO(audio), filename="voice.mp3"))

        @self.tree.command(name="summarize", description="Analyze recent messages and store them as long-term memory")
        @app_commands.describe(amount="Number of recent messages to analyze (5-1000)", user="User to summarize (defaults to yourself; owner can pick anyone)")
        async def slash_summarize(interaction: discord.Interaction, amount: int = 50, user: discord.User = None):
            self.record_interaction(interaction.user.id)
            target_user = user or interaction.user
            is_owner = await self.check_owner(interaction.user.id)
            if user and not is_owner and user.id != interaction.user.id:
                await interaction.response.send_message("You can only summarize your own messages. The owner can summarize anyone.", ephemeral=True)
                return
            amount = max(5, min(1000, amount))
            await interaction.response.defer(thinking=True, ephemeral=True)
            try:
                messages = []
                async for msg in interaction.channel.history(limit=amount + 50):
                    if msg.author.id == target_user.id and not msg.author.bot and len(msg.content.strip()) > 5:
                        messages.append(msg.content.strip())
                    if len(messages) >= amount:
                        break
                if len(messages) < 3:
                    await interaction.followup.send(f"Not enough messages from {target_user.display_name} to summarize. Need at least 3 meaningful messages.", ephemeral=True)
                    return

                uid = str(target_user.id)
                if uid not in global_user_profiles:
                    global_user_profiles[uid] = {
                        "name": target_user.display_name,
                        "global_name": getattr(target_user, 'global_name', None) or str(target_user),
                        "facts": [],
                        "sentences": [],
                        "interaction_count": 0,
                        "first_seen": time.time(),
                        "last_seen": time.time(),
                        "conversation_buffer": [],
                        "profile_changes": [],
                        "mentioned_users": [],
                    }

                profile = global_user_profiles[uid]
                existing_facts = profile.get("facts", [])
                existing_sentences = profile.get("sentences", [])
                combined = "\n".join([f"- {m}" for m in messages])

                # Token optimization: Use top 15 facts and 10 quotes for deduplication context
                existing_facts_text = "\n".join([f"- {f}" for f in existing_facts[-15:]]) if existing_facts else "None"
                existing_sentences_text = "\n".join([f"- {s}" for s in existing_sentences[-10:]]) if existing_sentences else "None"

                extract_sys = "You are a concise JSON memory curator for a personal AI assistant. Output ONLY valid JSON."
                prompt = (
                    "Analyze these user messages and extract memorable personal information.\n\n"
                    "EXISTING FACTS (do NOT duplicate):\n"
                    f"{existing_facts_text}\n\n"
                    "EXISTING QUOTES (do NOT duplicate):\n"
                    f"{existing_sentences_text}\n\n"
                    f"MESSAGES TO ANALYZE ({len(messages)} messages):\n"
                    f"{combined}\n\n"
                    "Instructions:\n"
                    "1. Extract up to 6 distinct, genuine facts about the user.\n"
                    "2. Extract up to 4 notable sentences or quotes.\n"
                    "3. CRITICAL: Only return GENUINELY NEW items. Skip anything semantically similar to existing memories.\n\n"
                    "Return ONLY valid JSON in this format:\n"
                    '{"facts": ["fact 1", "fact 2"], "sentences": ["sentence 1", "sentence 2"]}'
                )

                cfg_extract = {**self.config, "max_tokens": 350, "temperature": 0.2}
                facts_text, err = None, True
                if (cfg_extract.get("groq_key") or OWNER_KEYS.get("GROQ_KEY")) and time.time() >= groq_blocked_until:
                    facts_text, err = await ask_groq([], prompt, cfg_extract, system_msg=extract_sys)
                if (err or not facts_text) and (cfg_extract.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")) and time.time() >= mistral_blocked_until:
                    facts_text, err = await ask_mistral([], prompt, cfg_extract, system_msg=extract_sys)
                if (err or not facts_text) and (cfg_extract.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")) and time.time() >= gemini_blocked_until:
                    facts_text, err = await ask_gemini(extract_sys, [], prompt, cfg_extract)
                if (err or not facts_text) and (cfg_extract.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")) and time.time() >= openai_blocked_until:
                    facts_text, err = await ask_openai([], prompt, cfg_extract, system_msg=extract_sys)
                if (err or not facts_text) and (cfg_extract.get("deepseek_key") or OWNER_KEYS.get("DEEPSEEK_KEY")) and time.time() >= deepseek_blocked_until:
                    facts_text, err = await ask_deepseek([], prompt, cfg_extract, system_msg=extract_sys)
                if (err or not facts_text) and (cfg_extract.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")) and time.time() >= openrouter_blocked_until:
                    facts_text, err = await ask_openrouter([], prompt, cfg_extract, system_msg=extract_sys)
                if (err or not facts_text) and (cfg_extract.get("hf_key") or OWNER_KEYS.get("HF_KEY")) and time.time() >= huggingface_blocked_until:
                    facts_text, err = await ask_huggingface([], prompt, cfg_extract, system_msg=extract_sys)
                if err or not facts_text:
                    await interaction.followup.send(f"AI summarization failed: {facts_text}", ephemeral=True)
                    return

                new_facts = []
                new_sentences = []
                try:
                    match = re.search(r'\{.*?\}', facts_text, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        new_facts = parsed.get("facts", [])
                        new_sentences = parsed.get("sentences", [])
                except Exception:
                    pass

                facts_list = profile.setdefault("facts", [])
                sentences_list = profile.setdefault("sentences", [])
                added_facts = 0
                added_sentences = 0

                for f in new_facts:
                    if isinstance(f, str) and f.strip() and len(f) > 5:
                        f_clean = f.strip()
                        if not is_similar_to_existing(f_clean, facts_list):
                            facts_list.append(f_clean)
                            added_facts += 1

                for s in new_sentences:
                    if isinstance(s, str) and s.strip() and len(s) > 5:
                        s_clean = s.strip()
                        if not is_similar_to_existing(s_clean, sentences_list):
                            sentences_list.append(s_clean)
                            added_sentences += 1

                profile["last_seen"] = time.time()
                save_global_user_profiles()

                if not (added_facts or added_sentences):
                    await interaction.followup.send(f"Analyzed {len(messages)} messages from {target_user.display_name}, but nothing new was found — you already remember it all! 🧠", ephemeral=True)
                    return

                personality = self.config.get("personality", "You are a helpful assistant.")
                intervention_prompt = (
                    f"You just analyzed {len(messages)} messages from {target_user.display_name} and extracted new memories.\n"
                    f"New facts: {facts_list[-added_facts:] if added_facts else 'None'}\n"
                    f"New quotes: {sentences_list[-added_sentences:] if added_sentences else 'None'}\n\n"
                    f"Respond to {target_user.display_name} in character. Comment on what you learned, tease them, or be impressed. Keep it under 200 words."
                )

                reply, err = await self.ask_ai(interaction.channel_id, intervention_prompt, user_id=target_user.id, user_name=target_user.display_name)
                if err or not reply:
                    reply = f"📝 Analyzed {len(messages)} messages! Added {added_facts} new facts and {added_sentences} new quotes."
                await interaction.followup.send(reply[:2000], ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Summarization error: {e}", ephemeral=True)

        @self.tree.command(name="memory", description="Show what the bot remembers about you")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        async def slash_memory(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            uid = str(interaction.user.id)
            profile = global_user_profiles.get(uid, {})
            if not profile or profile.get("interaction_count", 0) == 0:
                await interaction.response.send_message("I don't have any memory of you yet. Let's chat! 🌱", ephemeral=True)
                return
            embed = discord.Embed(title=f"🧠 Memory: {interaction.user.display_name}", color=0x8a9a8a)
            embed.add_field(name="Interactions", value=str(profile.get("interaction_count", 0)), inline=True)
            embed.add_field(name="First Seen", value=time.ctime(profile.get("first_seen", 0)), inline=True)
            embed.add_field(name="Last Seen", value=time.ctime(profile.get("last_seen", 0)), inline=True)

            facts_list = profile.get("facts", [])
            sentences_list = profile.get("sentences", [])
            embed.add_field(name="Facts Stored", value=str(len(facts_list)), inline=True)
            embed.add_field(name="Quotes Stored", value=str(len(sentences_list)), inline=True)

            if facts_list:
                facts_str = "\n".join(f"• {f}" for f in facts_list[-12:])
                embed.add_field(name="Recent Facts", value=facts_str[:1000], inline=False)
            if sentences_list:
                sent_str = "\n".join(f'• "{s}"' for s in sentences_list[-8:])
                embed.add_field(name="Recent Quotes", value=sent_str[:1000], inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="persona", description="Set notes about yourself for the bot to remember")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.describe(notes="What should I know about you?")
        async def slash_persona(interaction: discord.Interaction, notes: str):
            self.record_interaction(interaction.user.id)
            uid = str(interaction.user.id)
            if uid not in global_user_profiles:
                global_user_profiles[uid] = {
                    "name": interaction.user.display_name,
                    "global_name": getattr(interaction.user, 'global_name', None) or str(interaction.user),
                    "facts": [],
                    "sentences": [],
                    "interaction_count": 0,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "conversation_buffer": [],
                    "profile_changes": [],
                    "mentioned_users": [],
                }
            facts_list = global_user_profiles[uid].setdefault("facts", [])
            notes_clean = notes.strip()
            if is_similar_to_existing(notes_clean, facts_list, threshold=0.8):
                await interaction.response.send_message("I already remember something very similar to that! ✅", ephemeral=True)
                return
            facts_list.append(notes_clean)
            save_global_user_profiles()
            await interaction.response.send_message("Got it! I've noted that down in your memory profile. 📝", ephemeral=True)

        @self.tree.command(name="reset", description="Clear this channel's context memory")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        async def slash_reset(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            self.clear_context(interaction.channel_id)
            await interaction.response.send_message("🧹 Channel context memory cleared.", ephemeral=True)

        @self.tree.command(name="forgetme", description="Wipe all facts, quotes, and long-term memories the AI has about you")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        async def slash_forgetme(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            uid = str(interaction.user.id)
            existed = uid in global_user_profiles
            if existed:
                global_user_profiles.pop(uid, None)
                save_global_user_profiles()
            self.interacted_users.discard(uid)
            self.save()
            embed = discord.Embed(
                title="🧹 Memory Forgotten",
                description=f"All stored facts, quotes, profile data, and conversation history about **{interaction.user.display_name}** have been completely purged from my memory.",
                color=0x8a9a8a
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="purgememory", description="Fully purge AI memory (global, user-specific, or channel)")
        @app_commands.describe(scope="Scope of memory to purge", user="Target user (if purging user memory)")
        @app_commands.choices(scope=[
            app_commands.Choice(name="All / Everything (Wipe RAM & Disk - Owner Only)", value="all"),
            app_commands.Choice(name="My Own Memory Profile", value="self"),
            app_commands.Choice(name="Specific User Profile", value="user"),
            app_commands.Choice(name="This Channel Context Only", value="channel"),
        ])
        async def slash_purgememory(interaction: discord.Interaction, scope: str, user: discord.User = None):
            self.record_interaction(interaction.user.id)
            is_owner = await self.check_owner(interaction.user.id)
            if scope == "all":
                if not is_owner:
                    await interaction.response.send_message("❌ Owner only. Purging all AI memory requires owner permissions.", ephemeral=True)
                    return
                # 1. Clear short-term channel contexts
                channel_count = len(self.contexts)
                self.contexts.clear()
                # 2. Clear long-term user memory profiles
                profile_count = len(global_user_profiles)
                global_user_profiles.clear()
                save_global_user_profiles()
                # 3. Clear interacted users tracking
                self.interacted_users.clear()
                self.save()

                embed = discord.Embed(
                    title="💥 Full AI Memory Purged",
                    description=(
                        "**Complete memory wipe executed:**\n"
                        f"• Cleared **{channel_count}** active channel context(s)\n"
                        f"• Purged **{profile_count}** long-term user memory profile(s)\n"
                        "• Reset all conversation buffers and extracted facts/quotes\n"
                        "• Overwrote `user_profiles.json` storage on disk with a clean state"
                    ),
                    color=0xc06060
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if scope == "self" or (scope == "user" and (not user or user.id == interaction.user.id)):
                uid = str(interaction.user.id)
                global_user_profiles.pop(uid, None)
                save_global_user_profiles()
                self.interacted_users.discard(uid)
                self.save()
                await interaction.response.send_message(f"🧹 Successfully wiped all memory profile records for **{interaction.user.display_name}**.", ephemeral=True)
                return

            if scope == "user":
                if not is_owner:
                    await interaction.response.send_message("❌ You can only purge your own memory. The owner can purge other users.", ephemeral=True)
                    return
                target_user = user
                uid = str(target_user.id)
                global_user_profiles.pop(uid, None)
                save_global_user_profiles()
                self.interacted_users.discard(uid)
                self.save()
                await interaction.response.send_message(f"🧹 Owner action: Wiped all long-term memory for **{target_user.display_name}** (`{uid}`).", ephemeral=True)
                return

            if scope == "channel":
                self.clear_context(interaction.channel_id)
                await interaction.response.send_message("🧹 Short-term context memory for this channel has been cleared.", ephemeral=True)
                return

        @self.tree.command(name="purgeall", description="Purge ALL memory globally across all users & channels (Owner only)")
        async def slash_purgeall(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            if not await self.check_owner(interaction.user.id):
                await interaction.response.send_message("❌ Owner only.", ephemeral=True)
                return
            channel_count = len(self.contexts)
            profile_count = len(global_user_profiles)
            self.contexts.clear()
            global_user_profiles.clear()
            save_global_user_profiles()
            self.interacted_users.clear()
            self.save()

            embed = discord.Embed(
                title="💥 Full Memory Purged",
                description=f"Wiped all **{channel_count}** channel contexts and **{profile_count}** user profiles from RAM and disk.",
                color=0xc06060
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="sync", description="Force re-sync slash commands globally (Owner only)")
        async def slash_sync(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            if not await self.check_owner(interaction.user.id):
                await interaction.response.send_message("Owner only.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            try:
                synced = await self.tree.sync()
                names = ", ".join([f"/{c.name}" for c in synced]) if synced else "none"
                await interaction.followup.send(f"Synced {len(synced)} commands: {names}. Wait ~1 min.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Sync failed: {e}", ephemeral=True)

        @self.tree.command(name="invite", description="Get the invite link to add this bot to your servers or user apps")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        async def slash_invite(interaction: discord.Interaction):
            client_id = self.client.user.id if self.client.user else ""
            if not client_id:
                await interaction.response.send_message("Bot client ID unavailable.", ephemeral=True)
                return
            server_invite = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions=8&scope=bot%20applications.commands"
            user_app_invite = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=applications.commands"
            embed = discord.Embed(
                title=f"🔗 Invite & Install {self.bot_name or 'Bot'}",
                description="Choose how you'd like to add or use this bot:",
                color=0x8a9a8a
            )
            embed.add_field(
                name="🏰 Add to Server (Bot & Commands)",
                value=f"[**Click to Invite to Server**]({server_invite})\n*Adds {self.bot_name} to your Discord server with full features & commands.*",
                inline=False
            )
            embed.add_field(
                name="👤 Install as User App (Use in DMs & Any Server)",
                value=f"[**Click to Install to Account**]({user_app_invite})\n*Allows using slash commands anywhere, including private DMs & any server without server invite.*",
                inline=False
            )
            embed.set_footer(text=f"Bot ID: {self.bot_id}")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="search", description="Search the web with real-time AI synthesis")
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.describe(query="What to search for")
        async def slash_search(interaction: discord.Interaction, query: str):
            self.record_interaction(interaction.user.id)
            ok, remaining = self.check_cooldown(interaction.user.id)
            if not ok:
                await interaction.response.send_message(f"Slow down! Wait {remaining}s.", ephemeral=True)
                return
            await interaction.response.defer(thinking=True)
            results, err = await web_search(query, max_results=5)
            if err or not results:
                await interaction.followup.send(f"Search failed: {err or 'No results found.'}")
                return
            reply, ai_err = await self.synthesize_search(interaction.channel_id or interaction.user.id, query, results)
            if not ai_err and reply:
                header = f"**Search:** `{query}`\n\n"
                full_reply = header + reply
                source_lines = [f"{i}. [{r['title']}]({r['url']})" for i, r in enumerate(results[:5], 1)]
                source_embed = discord.Embed(title="Sources", description="\n".join(source_lines), color=0x2b2d42)
                if len(full_reply) <= 2000:
                    await interaction.followup.send(full_reply, embed=source_embed)
                else:
                    chunks = [full_reply[i:i+1950] for i in range(0, len(full_reply), 1950)]
                    for idx, chunk in enumerate(chunks):
                        if idx == len(chunks) - 1:
                            await interaction.followup.send(chunk, embed=source_embed)
                        else:
                            await interaction.followup.send(chunk)
                return
            lines = [f"**Web search:** `{query}`\n"]
            for i, r in enumerate(results[:5], 1):
                snippet = r["snippet"][:180] + "..." if len(r["snippet"]) > 180 else r["snippet"]
                lines.append(f"**{i}.** [{r['title']}]({r['url']})\n{snippet}\n")
            embed = discord.Embed(title="Search Results", description="\n".join(lines), color=0x4f8cff)
            embed.set_footer(text="via Web Search")
            await interaction.followup.send(embed=embed)

        @self.tree.command(name="transcribe", description="Transcribe the most recent voice/audio message in this channel")
        async def slash_transcribe(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            await interaction.response.defer(thinking=True)
            found = False
            async for msg in interaction.channel.history(limit=30):
                if msg.attachments:
                    for att in msg.attachments:
                        ext = Path(att.filename).suffix.lower()
                        is_audio = (att.content_type and att.content_type.startswith("audio/")) or ext in (".ogg", ".mp3", ".wav", ".m4a", ".flac")
                        if not is_audio:
                            continue
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(att.url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                                    audio_bytes = await resp.read()
                            text, terr = await transcribe_audio(audio_bytes, att.filename)
                            if terr:
                                await interaction.followup.send(f"Transcription failed: {terr}")
                            else:
                                await interaction.followup.send(f'\U0001f3a4 @{msg.author.display_name} said: "{text}"')
                            found = True
                            break
                        except Exception as e:
                            await interaction.followup.send(f"Error: {e}")
                    if found:
                        break
            if not found:
                await interaction.followup.send("No recent audio/voice messages found in the last 30 messages.")

        @self.tree.command(name="ping", description="Check bot latency and active AI provider status")
        async def slash_ping(interaction: discord.Interaction):
            self.record_interaction(interaction.user.id)
            ws_latency = round(self.client.latency * 1000) if self.client.latency else 0
            active_p = self.config.get("provider", "auto")
            if active_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{active_p}_model"
            elif active_p == "openai":
                model_key = "openai_chat_model"
            elif active_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif active_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            active_m = self.config.get(model_key, "default")
            
            embed = discord.Embed(
                title=f"🏓 Pong! [{self.bot_name}]",
                description=(
                    f"⚡ **Gateway Latency**: `{ws_latency}ms`\n"
                    f"🌐 **Active Provider**: `{active_p}`\n"
                    f"🧠 **Model**: `{active_m}`\n"
                    f"🔋 **Status**: `Operational`"
                ),
                color=0x00ffcc
            )
            embed.set_footer(text=f"Bot ID: {self.bot_id}")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="toggleprovider", description="Quickly toggle or switch the active AI provider (Owner only)")
        @app_commands.describe(
            target="Optional specific provider to switch to (Gemini, Groq, Mistral, OpenAI, Custom/LiteRouter, DeepSeek, OpenRouter, HuggingFace, Auto)"
        )
        @app_commands.choices(target=[
            app_commands.Choice(name="Next Provider in Cycle", value="cycle"),
            app_commands.Choice(name="Auto Fallback (auto)", value="auto"),
            app_commands.Choice(name="Google Gemini (gemini)", value="gemini"),
            app_commands.Choice(name="Groq (groq)", value="groq"),
            app_commands.Choice(name="Mistral AI (mistral)", value="mistral"),
            app_commands.Choice(name="OpenAI (openai)", value="openai"),
            app_commands.Choice(name="Custom Endpoint / LiteRouter (custom)", value="custom"),
            app_commands.Choice(name="DeepSeek (deepseek)", value="deepseek"),
            app_commands.Choice(name="OpenRouter (openrouter)", value="openrouter"),
            app_commands.Choice(name="Hugging Face (huggingface)", value="huggingface"),
        ])
        async def slash_toggleprovider(interaction: discord.Interaction, target: str = "cycle"):
            self.record_interaction(interaction.user.id)
            if not await self.check_owner(interaction.user.id):
                await interaction.response.send_message("❌ **Owner only**: Only the bot owner can toggle the provider.", ephemeral=True)
                return
            
            target_prov = None if target == "cycle" else target
            old_p, new_p = self.toggle_provider(target_prov)
            
            if new_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{new_p}_model"
            elif new_p == "openai":
                model_key = "openai_chat_model"
            elif new_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif new_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            curr_model = self.config.get(model_key, "default")
            
            embed = self.format_toast_embed(
                f"{self.bot_name} // Provider Toggled",
                f"Switched provider: `{old_p}` ➔ **`{new_p}`**\nActive Model: **`{curr_model}`**",
                color=0x4f8cff
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="setmodel", description="Update the AI model or endpoint for any provider and auto-save (Owner only)")
        @app_commands.describe(
            provider="AI provider to configure (Gemini, Groq, Mistral, OpenAI, Custom/LiteRouter, DeepSeek, OpenRouter, HuggingFace)",
            model="The exact model name (e.g. gpt-4o-mini, deepseek-chat, gemini-1.5-flash-8b, claude-3-7-sonnet)",
            base_url="Optional custom Base URL endpoint for LiteRouter / local tunnels (e.g. https://api.literouter.com/v1)",
            switch_provider="Whether to also set this provider as the active provider (Default: True)"
        )
        @app_commands.choices(provider=[
            app_commands.Choice(name="Google Gemini (gemini)", value="gemini"),
            app_commands.Choice(name="Groq (groq)", value="groq"),
            app_commands.Choice(name="Mistral AI (mistral)", value="mistral"),
            app_commands.Choice(name="OpenAI (openai)", value="openai"),
            app_commands.Choice(name="Custom Endpoint / LiteRouter (custom)", value="custom"),
            app_commands.Choice(name="DeepSeek (deepseek)", value="deepseek"),
            app_commands.Choice(name="OpenRouter (openrouter)", value="openrouter"),
            app_commands.Choice(name="Hugging Face (huggingface)", value="huggingface"),
            app_commands.Choice(name="Auto Fallback (auto)", value="auto"),
        ])
        async def slash_setmodel(interaction: discord.Interaction, provider: str, model: str = None, base_url: str = None, switch_provider: bool = True):
            self.record_interaction(interaction.user.id)
            if not await self.check_owner(interaction.user.id):
                await interaction.response.send_message("❌ **Owner only**: Only the bot owner can update models.", ephemeral=True)
                return
            
            prov_to_key = {
                "gemini": "gemini_model",
                "groq": "groq_model",
                "mistral": "mistral_model",
                "openai": "openai_chat_model",
                "custom": "custom_model",
                "literouter": "custom_model",
                "deepseek": "deepseek_model",
                "openrouter": "model",
                "huggingface": "huggingface_model",
            }
            
            changes = []
            if provider in prov_to_key and model:
                target_key = prov_to_key[provider]
                old_m = self.config.get(target_key, "")
                self.config[target_key] = model.strip()
                changes.append(f"• **`{target_key}`**: `{old_m}` ➔ **`{model.strip()}`**")
            
            if base_url:
                old_u = self.config.get("custom_base_url", "")
                self.config["custom_base_url"] = base_url.strip()
                changes.append(f"• **`custom_base_url`**: `{old_u}` ➔ **`{base_url.strip()}`**")
            
            if switch_provider and provider != "auto":
                old_p = self.config.get("provider", "auto")
                self.config["provider"] = provider
                changes.append(f"• **`provider`**: `{old_p}` ➔ **`{provider}`**")
            elif provider == "auto":
                old_p = self.config.get("provider", "auto")
                self.config["provider"] = "auto"
                changes.append(f"• **`provider`**: `{old_p}` ➔ **`auto`**")
            
            self.save()
            
            embed = discord.Embed(
                title=f"⚙️ {self.bot_name} // Model Updated",
                description="\n".join(changes) if changes else "No changes made.",
                color=0x00ffcc
            )
            embed.add_field(name="Active Provider", value=f"`{self.config.get('provider', 'auto')}`", inline=True)
            embed.add_field(name="Current Models", value=(
                f"• **Gemini**: `{self.config.get('gemini_model', 'None')}`\n"
                f"• **Groq**: `{self.config.get('groq_model', 'None')}`\n"
                f"• **Mistral**: `{self.config.get('mistral_model', 'None')}`\n"
                f"• **OpenAI**: `{self.config.get('openai_chat_model', 'None')}`\n"
                f"• **Custom Endpoint**: `{self.config.get('custom_model', 'None')}` (`{self.config.get('custom_base_url') or 'Default'}`)\n"
                f"• **DeepSeek**: `{self.config.get('deepseek_model', 'None')}`\n"
                f"• **OpenRouter**: `{self.config.get('model', 'None')}`\n"
                f"• **Hugging Face**: `{self.config.get('huggingface_model', 'None')}`"
            ), inline=False)
            embed.set_footer(text=f"Bot ID: {self.bot_id} • Auto-saved to user_bots/{self.bot_id}.json")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="config", description="View or update bot configuration parameters (Owner only for updates)")
        @app_commands.describe(
            action="Choose whether to view or set a configuration field",
            field="Field to update (e.g. gemini, groq, mistral, openai, custom, base_url, custom_key, custom_model, provider, personality, tts)",
            value="New value to save for this field"
        )
        @app_commands.choices(action=[
            app_commands.Choice(name="View Current Config", value="view"),
            app_commands.Choice(name="Set / Update Field", value="set"),
        ])
        async def slash_config(interaction: discord.Interaction, action: str = "view", field: str = None, value: str = None):
            self.record_interaction(interaction.user.id)
            is_owner = await self.check_owner(interaction.user.id)
            if action == "set":
                if not is_owner:
                    await interaction.response.send_message("❌ **Owner only**: You cannot modify this bot's configuration.", ephemeral=True)
                    return
                if not field or value is None:
                    await interaction.response.send_message("⚠️ Please provide both `field` and `value` to update config.", ephemeral=True)
                    return
                
                ok, key, old_v, new_v = self.update_setting(field, value)
                if not ok:
                    await interaction.response.send_message(f"❌ Unknown or invalid field `{field}`. Supported fields include: `base_url`, `custom_key`, `custom_model`, `gemini`, `groq`, `mistral`, `openai`, `deepseek`, `model`, `provider`, `personality`, `temperature`, `max_tokens`, `tts`, `voice`.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title=f"⚙️ {self.bot_name} // Config Saved",
                    description=f"Field **`{key}`** has been updated and saved to disk.",
                    color=0x00ffcc
                )
                embed.add_field(name="Previous", value=f"`{old_v}`" if old_v else "*None*", inline=True)
                embed.add_field(name="New Value", value=f"`{new_v}`", inline=True)
                embed.add_field(name="Active Provider", value=f"`{self.config.get('provider', 'auto')}`", inline=True)
                embed.set_footer(text=f"Bot ID: {self.bot_id} • Auto-saved to user_bots/{self.bot_id}.json")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # View current config
            embed = discord.Embed(
                title=f"📋 {self.bot_name} // Current Configuration",
                color=0x7a8a9a
            )
            embed.add_field(name="AI Provider", value=f"`{self.config.get('provider', 'auto')}`", inline=True)
            embed.add_field(name="Temperature", value=f"`{self.config.get('temperature', 0.7)}`", inline=True)
            embed.add_field(name="Max Tokens", value=f"`{self.config.get('max_tokens', 800)}`", inline=True)
            
            embed.add_field(name="🧠 Active Models", value=(
                f"• **Gemini**: `{self.config.get('gemini_model', 'None')}`\n"
                f"• **Groq**: `{self.config.get('groq_model', 'None')}`\n"
                f"• **Mistral**: `{self.config.get('mistral_model', 'None')}`\n"
                f"• **OpenAI**: `{self.config.get('openai_chat_model', 'None')}`\n"
                f"• **Custom Endpoint**: `{self.config.get('custom_model', 'None')}` (URL: `{self.config.get('custom_base_url') or 'Default'}`)\n"
                f"• **DeepSeek**: `{self.config.get('deepseek_model', 'None')}`\n"
                f"• **OpenRouter**: `{self.config.get('model', 'None')}`\n"
                f"• **Hugging Face**: `{self.config.get('huggingface_model', 'None')}`"
            ), inline=False)
            
            pers = self.config.get("personality", "None")
            if len(pers) > 250:
                pers = pers[:247] + "..."
            embed.add_field(name="Personality", value=f"*{pers}*", inline=False)
            
            tts_p = self.config.get("tts_provider", "auto")
            tts_on = "Enabled" if self.config.get("tts_enabled") else "Disabled"
            embed.add_field(name="Voice & TTS", value=f"Status: `{tts_on}` | Provider: `{tts_p}`", inline=False)
            
            embed.set_footer(text=f"Owner ID: {self.owner_id or 'Auto-detected'} • Bot ID: {self.bot_id}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        # ─── /set greet COMMAND GROUP & /set_greet ────────────
        set_group = app_commands.Group(name="set", description="Configure bot features & server automation")

        async def _handle_greet_config(interaction: discord.Interaction, message: str = None, channel: discord.TextChannel = None, ai_enhance: bool = True, ping_member: bool = True, enabled: bool = True):
            self.record_interaction(interaction.user.id)
            if not interaction.guild:
                await interaction.response.send_message("⚠️ This command must be used inside a Discord server.", ephemeral=True)
                return

            is_admin = interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
            is_owner = await self.check_owner(interaction.user.id)
            if not is_admin and not is_owner:
                await interaction.response.send_message("❌ **Permission Denied**: You need `Manage Server` or `Administrator` permission to configure greetings.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            target_channel = channel or interaction.channel
            welcome_settings = self.config.get("welcome_settings") or {}
            guild_id_str = str(interaction.guild.id)
            base_msg = (message or "").strip() or "Welcome! Make yourself at home."
            is_enabled = bool(enabled)

            g_cfg = {
                "enabled": is_enabled,
                "channel_id": str(target_channel.id),
                "channel_name": target_channel.name,
                "message": base_msg,
                "ai_enhance": bool(ai_enhance),
                "ping_member": bool(ping_member),
                "updated_at": time.time(),
                "updated_by": interaction.user.display_name
            }

            welcome_settings[guild_id_str] = g_cfg
            self.config["welcome_settings"] = welcome_settings
            self.config["welcome_enabled"] = is_enabled
            self.config["welcome_channel_id"] = str(target_channel.id)
            self.config["welcome_message"] = base_msg
            self.config["welcome_ai_enhance"] = bool(ai_enhance)
            self.config["welcome_ping"] = bool(ping_member)
            self.save()

            # Trigger background Supabase sync
            if SUPABASE_SERVICE_KEY and SUPABASE_URL:
                try:
                    if bot_loop and bot_loop.is_running():
                        asyncio.run_coroutine_threadsafe(sync_interaction_count_to_supabase(self.bot_id, self.message_count), bot_loop)
                except Exception:
                    pass

            # Generate live preview
            preview_text = ""
            if enabled:
                if ai_enhance:
                    sys_prompt = self.config.get("personality") or "You are a helpful and engaging Discord AI companion."
                    preview_prompt = (
                        f"A new member named '{interaction.user.display_name}' has joined the Discord server '{interaction.guild.name}'.\n"
                        f"Admin guidance/rules note: \"{base_msg}\"\n\n"
                        f"Instructions: Generate a short, warm, in-character greeting (1-3 sentences) welcoming this new member in your unique personality/voice ({sys_prompt}). "
                        f"Seamlessly incorporate the admin's note/rules. Keep it natural, welcoming, and in-character."
                    )
                    try:
                        ai_reply, err = await self.ask_ai(
                            target_channel.id, preview_prompt, user_id=interaction.user.id,
                            user_name=interaction.user.display_name, guild=interaction.guild, is_dm=False
                        )
                        if not err and ai_reply and len(ai_reply.strip()) > 3:
                            preview_text = ai_reply.strip()
                    except Exception:
                        pass
                if not preview_text:
                    preview_text = base_msg.replace("{user}", interaction.user.display_name).replace("{server}", interaction.guild.name)

            status_str = "🟢 **Active & Enabled**" if enabled else "🔴 **Disabled**"
            embed = discord.Embed(
                title=f"👋 Member Greeting Configured // {self.bot_name}",
                description=f"Automated AI greetings for **{interaction.guild.name}** have been updated.",
                color=0x00ffcc if enabled else 0x7a8a9a
            )
            embed.add_field(name="Status", value=status_str, inline=True)
            embed.add_field(name="Welcome Channel", value=f"<#{target_channel.id}>", inline=True)
            embed.add_field(name="Ping Member", value="`Yes` (@member)" if ping_member else "`No`", inline=True)
            embed.add_field(name="Base Guidance / Rules Note", value=f"> {base_msg}", inline=False)
            embed.add_field(name="AI Personality Enhancement", value=f"`Active` ✦ Enhanced in **{self.bot_name}**'s voice & personality" if ai_enhance else "`Disabled` (Raw template only)", inline=False)

            if enabled and preview_text:
                sample_pings = f"{interaction.user.mention} " if ping_member else ""
                embed.add_field(
                    name="✨ Live Preview of Next Join",
                    value=f"{sample_pings}{preview_text}",
                    inline=False
                )

            embed.set_footer(text=f"Trigger: on_member_join • Auto-saved to user_bots/{self.bot_id}.json")
            await interaction.followup.send(embed=embed)

        @set_group.command(name="greet", description="Configure AI member welcome greetings with personality adaptation")
        @app_commands.describe(
            message="Base guidance or rules note (e.g. 'Welcome! please check out #faq and grab roles')",
            channel="Channel to send greetings in (defaults to current channel)",
            ai_enhance="Let AI enhance & adapt the greeting with this bot's personality (default: True)",
            ping_member="Ping/mention the new member in the greeting (default: True)",
            enabled="Turn welcome greetings ON or OFF (default: True)"
        )
        async def slash_set_greet_group(interaction: discord.Interaction, message: str = None, channel: discord.TextChannel = None, ai_enhance: bool = True, ping_member: bool = True, enabled: bool = True):
            await _handle_greet_config(interaction, message, channel, ai_enhance, ping_member, enabled)

        self.tree.add_command(set_group)

        @self.tree.command(name="set_greet", description="Configure AI member welcome greetings with personality adaptation")
        @app_commands.describe(
            message="Base guidance or rules note (e.g. 'Welcome! please check out #faq and grab roles')",
            channel="Channel to send greetings in (defaults to current channel)",
            ai_enhance="Let AI enhance & adapt the greeting with this bot's personality (default: True)",
            ping_member="Ping/mention the new member in the greeting (default: True)",
            enabled="Turn welcome greetings ON or OFF (default: True)"
        )
        async def slash_set_greet_flat(interaction: discord.Interaction, message: str = None, channel: discord.TextChannel = None, ai_enhance: bool = True, ping_member: bool = True, enabled: bool = True):
            await _handle_greet_config(interaction, message, channel, ai_enhance, ping_member, enabled)

        @self.tree.command(name="gt", description="Test member welcome greeting in this channel")
        @app_commands.describe(member="Optional member to simulate greeting for")
        async def slash_greet_test(interaction: discord.Interaction, member: discord.Member = None):
            self.record_interaction(interaction.user.id)
            if not interaction.guild:
                await interaction.response.send_message("⚠️ This command can only be used inside a server.", ephemeral=True)
                return

            is_admin = interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
            is_owner = await self.check_owner(interaction.user.id)
            if not is_admin and not is_owner:
                await interaction.response.send_message("❌ **Permission Denied**: You need `Manage Server` or `Administrator` permission.", ephemeral=True)
                return

            await interaction.response.defer()
            target_mem = member or interaction.user
            ok, res_msg = await self.generate_and_send_welcome(
                target_mem, target_channel=interaction.channel, is_test=True, trigger_user=interaction.user
            )
            if ok:
                await interaction.followup.send(f"✅ Tested greeting for **{target_mem.display_name}** in <#{interaction.channel_id}>.", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ Greeting test notice: {res_msg}", ephemeral=True)

    async def check_owner(self, user_id: int) -> bool:
        uid_str = str(user_id).strip()
        # 1. Check global OWNER_ID environment variable
        if OWNER_ID and uid_str == OWNER_ID:
            return True
        # 2. Check explicit config fields
        cfg_owner = str(self.config.get("discord_owner_id") or self.config.get("owner_discord_id") or "").strip()
        if cfg_owner and uid_str == cfg_owner:
            return True
        admin_ids = [str(x).strip() for x in (self.config.get("admin_discord_ids") or []) if str(x).strip()]
        if uid_str in admin_ids:
            return True
        # 3. Check cached discord owner IDs set
        if hasattr(self, "discord_owner_ids") and self.discord_owner_ids:
            if uid_str in self.discord_owner_ids:
                return True
        # 4. Query Discord application info to get application owner and team members
        try:
            app = await self.client.application_info()
            owner_ids = set()
            if app.owner:
                owner_ids.add(str(app.owner.id))
            if getattr(app, "team", None) and app.team and getattr(app.team, "members", None):
                for m in app.team.members:
                    owner_ids.add(str(m.id))
            self.discord_owner_ids = owner_ids
            if uid_str in self.discord_owner_ids:
                return True
        except Exception:
            pass
        # 5. If self.owner_id is a numeric Discord snowflake ID
        if self.owner_id and str(self.owner_id).isdigit() and uid_str == str(self.owner_id):
            return True
        return False

    def check_cooldown(self, user_id: int) -> tuple:
        now = time.time()
        cd = self.config.get("cooldown_seconds", 10)
        remaining = cd - (now - self.cooldowns[user_id])
        if remaining > 0:
            return False, int(remaining)
        self.cooldowns[user_id] = now
        return True, 0

    def get_context(self, channel_id):
        if not self.config.get("context_enabled", True):
            return []
        raw_list = self.contexts.get(str(channel_id), [])
        max_ctx = max(2, min(30, int(self.config.get("max_context", 10))))
        trimmed = raw_list[-max_ctx:]
        results = []
        for i, m in enumerate(trimmed):
            content = m.get("content", "")
            if i < len(trimmed) - 2 and len(content) > 600:
                content = content[:500] + "... [earlier context trimmed]"
            results.append({"role": m.get("role", "user"), "content": content})
        return results

    def add_to_context(self, channel_id, role, content, user_name=None, user_id=None):
        cid = str(channel_id)
        if cid not in self.contexts:
            self.contexts[cid] = []
        if role == "user" and user_name and self.config.get("user_memory_enabled", True):
            content = f"[{user_name}]: {content}"
        self.contexts[cid].append({
            "role": role,
            "content": content,
            "user_id": str(user_id) if user_id else None,
            "user_name": user_name
        })
        max_ctx = self.config.get("max_context", 10)
        self.contexts[cid] = self.contexts[cid][-max_ctx:]

    def clear_context(self, channel_id):
        self.contexts.pop(str(channel_id), None)

    async def send_split_messages(self, destination, text, reply_to=None):
        if not text:
            return
        cfg = self.config
        parts = []
        if "||SPLIT||" in text and cfg.get("message_split_enabled", False):
            parts = [p.strip() for p in text.split("||SPLIT||") if p.strip()]
        else:
            parts = [text]
        if cfg.get("message_split_enabled", False) and len(parts) == 1 and len(text) > 300:
            raw = [p.strip() for p in text.split("\n\n") if p.strip()]
            if len(raw) > 1:
                parts = raw
            else:
                sentences = re.split(r'(?<=[.!?])\s+', text)
                if len(sentences) > 1:
                    parts = []
                    current = ""
                    for s in sentences:
                        if len(current) + len(s) < 350:
                            current += " " + s if current else s
                        else:
                            if current:
                                parts.append(current.strip())
                            current = s
                    if current:
                        parts.append(current.strip())
        min_msgs = max(1, int(cfg.get("message_split_min", 1)))
        max_msgs = max(1, int(cfg.get("message_split_max", 1)))
        delay = max(0.0, float(cfg.get("message_split_delay", 1.0)))
        target = random.randint(min_msgs, max_msgs) if max_msgs >= min_msgs else min_msgs
        if len(parts) > target:
            merged = " ".join(parts[target-1:])
            parts = parts[:target-1] + [merged]
        for i, part in enumerate(parts[:target]):
            if i > 0 and delay > 0:
                await asyncio.sleep(delay)
            chunks = [part[j:j+2000] for j in range(0, len(part), 2000)]
            for j, chunk in enumerate(chunks):
                sent_msg = None
                if reply_to and i == 0 and j == 0:
                    try:
                        sent_msg = await reply_to.reply(chunk)
                    except Exception:
                        sent_msg = await destination.send(chunk)
                else:
                    sent_msg = await destination.send(chunk)
                if sent_msg and hasattr(sent_msg, "id"):
                    self.recent_sent_message_ids.add(sent_msg.id)
                    if len(self.recent_sent_message_ids) > 250:
                        try:
                            self.recent_sent_message_ids.pop()
                        except Exception:
                            pass
        try:
            record_bot_interaction(self.bot_id)
        except Exception:
            pass

    async def synthesize_search(self, channel_id, user_query, results, ctx=None):
        if not results:
            return "I looked around but didn't find anything useful.", False
        system_msg = self.config["personality"]
        results_text = "\n".join([
            f"- {r['title']}: {r['snippet'][:200]}{'...' if len(r['snippet']) > 200 else ''}"
            for r in results[:5]
        ])
        search_prompt = (
            f'The user asked: "{user_query}"\n'
            f"Here is what I found from a quick web search:\n{results_text}\n"
            f"Respond naturally in your usual personality and style. "
            f"Do NOT list results with numbers or dump raw links. Just talk like a person having a conversation."
        )
        provider = self.config.get("provider", "auto")
        reply, err = None, True
        if provider == "gemini" and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")) and time.time() >= gemini_blocked_until:
            reply, err = await ask_gemini(system_msg, ctx or [], search_prompt, self.config)
        elif provider == "groq" and (self.config.get("groq_key") or OWNER_KEYS.get("GROQ_KEY")) and time.time() >= groq_blocked_until:
            reply, err = await ask_groq(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider == "mistral" and (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")) and time.time() >= mistral_blocked_until:
            reply, err = await ask_mistral(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider == "openai" and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")) and time.time() >= openai_blocked_until:
            reply, err = await ask_openai(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider == "deepseek" and (self.config.get("deepseek_key") or OWNER_KEYS.get("DEEPSEEK_KEY")) and time.time() >= deepseek_blocked_until:
            reply, err = await ask_deepseek(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider == "openrouter" and (self.config.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")) and time.time() >= openrouter_blocked_until:
            reply, err = await ask_openrouter(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider == "huggingface" and (self.config.get("hf_key") or OWNER_KEYS.get("HF_KEY")) and time.time() >= huggingface_blocked_until:
            reply, err = await ask_huggingface(ctx or [], search_prompt, self.config, system_msg=system_msg)
        elif provider in ("custom", "literouter"):
            reply, err = await ask_custom(ctx or [], search_prompt, self.config, system_msg=system_msg)
        else:
            if (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")) and time.time() >= gemini_blocked_until:
                reply, err = await ask_gemini(system_msg, ctx or [], search_prompt, self.config)
            if err and (self.config.get("groq_key") or OWNER_KEYS.get("GROQ_KEY")) and time.time() >= groq_blocked_until:
                reply, err = await ask_groq(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")) and time.time() >= mistral_blocked_until:
                reply, err = await ask_mistral(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")) and time.time() >= openai_blocked_until:
                reply, err = await ask_openai(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("custom_base_url") or self.config.get("custom_key") or self.config.get("custom_model")):
                reply, err = await ask_custom(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("deepseek_key") or OWNER_KEYS.get("DEEPSEEK_KEY")) and time.time() >= deepseek_blocked_until:
                reply, err = await ask_deepseek(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")) and time.time() >= openrouter_blocked_until:
                reply, err = await ask_openrouter(ctx or [], search_prompt, self.config, system_msg=system_msg)
            if err and (self.config.get("hf_key") or OWNER_KEYS.get("HF_KEY")) and time.time() >= huggingface_blocked_until:
                reply, err = await ask_huggingface(ctx or [], search_prompt, self.config, system_msg=system_msg)
        return reply, err

    async def random_dm_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                if not self.config.get("random_dms_enabled", False):
                    await asyncio.sleep(60)
                    continue
                interval = max(10, int(self.config.get("random_dms_interval_minutes", 60))) * 60
                await asyncio.sleep(interval)
                if not self.config.get("random_dms_enabled", False):
                    continue
                now = time.time()
                active_users = [
                    uid for uid in self.interacted_users
                    if (now - self.user_last_interaction.get(uid, 0)) <= 8 * 3600
                ]
                if not active_users:
                    continue
                user_id = random.choice(active_users)
                try:
                    user = await self.client.fetch_user(int(user_id))
                except Exception:
                    continue
                if not user:
                    continue
                dm_prompt = self.config.get("random_dms_prompt", "Send a casual, friendly message.")
                reply, err = await self.ask_ai(f"dm_{user_id}", dm_prompt, user_id=user.id, user_name=user.display_name, is_dm=True)
                if not err and reply:
                    try:
                        await user.send(reply[:2000])
                    except discord.Forbidden:
                        pass
            except Exception as e:
                print(f"[BOT {self.bot_id}] random_dm_loop error: {e}")
                await asyncio.sleep(60)

    async def random_chat_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                if not self.config.get("random_chat_enabled", False):
                    await asyncio.sleep(60)
                    continue
                if self.is_idle(8.0):
                    await asyncio.sleep(120)
                    continue
                await asyncio.sleep(random.randint(60, 120))
                candidates = []
                for guild in self.client.guilds:
                    for channel in guild.text_channels:
                        try:
                            if channel.permissions_for(guild.me).send_messages:
                                candidates.append(channel)
                        except Exception:
                            continue
                if not candidates:
                    continue
                channel = random.choice(candidates)
                chance = float(self.config.get("random_chat_chance", 0.05))
                if random.random() > chance:
                    continue
                limit = min(15, int(self.config.get("random_chat_context_limit", 15)))
                history = []
                mentioned = False
                try:
                    async for msg in channel.history(limit=limit):
                        if msg.author == self.client.user:
                            history.append({"role": "assistant", "content": msg.content or ""})
                        else:
                            history.append({"role": "user", "content": f"[{msg.author.display_name}]: {msg.content or ''}"})
                            if self.is_name_called(msg.content or "") or (self.client.user in msg.mentions if self.client.user else False):
                                mentioned = True
                except Exception:
                    continue
                if not history:
                    continue
                history.reverse()
                if not mentioned and random.random() > 0.2:
                    continue
                recent = "\n".join([h["content"] for h in history[-5:]])
                prompt = (
                    f"Recent conversation in this channel:\n{recent}\n\n"
                    f"Jump into the conversation naturally with a short, relevant, casual response. "
                    f"Match the vibe and don't mention you're an AI. Keep it under 2 sentences."
                )
                reply, err = await self.ask_ai(channel.id, prompt, guild=channel.guild, is_dm=False)
                if not err and reply:
                    await self.send_split_messages(channel, reply)
            except Exception as e:
                print(f"[BOT {self.bot_id}] random_chat_loop error: {e}")
                await asyncio.sleep(60)

    async def ask_ai(self, channel_id, prompt, images=None, user_id=None, user_name=None, guild=None, is_dm=False):
        ctx = self.get_context(channel_id)
        system_msg = self.config["personality"]
        provider = self.config.get("provider", "auto")
        auto_search = self.config.get("auto_search", True)

        if self.config.get("user_memory_enabled", True):
            scene = build_scene_context(
                channel_id, primary_user_id=user_id, user_name=user_name,
                guild=guild, is_dm=is_dm, current_prompt=prompt,
                raw_context=self.contexts.get(str(channel_id), [])
            )
            if scene:
                system_msg += "\n\n" + scene

        if self.config.get("message_split_enabled", False):
            system_msg += "\n\nIf you have multiple separate thoughts or distinct points, separate them with ||SPLIT|| so they can be sent as individual messages. Keep each part conversational."

        system_msg += (
            "\n\n[STRICT ROLEPLAY DIRECTIVE]:\n"
            "- You are NOT an AI assistant, language model, or customer service agent. You must strictly stay in character as defined above.\n"
            "- NEVER use corporate assistant phrases (e.g. 'Let\'s delve deeper into this', 'What are your thoughts?', 'How can I assist you?', 'As an AI').\n"
            "- NEVER write synthetic narrator stage directions or repetitive physical actions in asterisks like '*turns to you attentively, engaging directly with your words*'.\n"
            "- Reply directly, authentically, and vividly in character."
        )

        def save_ctx(reply):
            cleaned = clean_llm_reply(reply) or str(reply or '').strip()
            self.add_to_context(channel_id, "user", prompt, user_name=user_name, user_id=user_id)
            self.add_to_context(channel_id, "assistant", cleaned)
            return cleaned

        search_done = False
        if auto_search and not images and needs_realtime_data(prompt):
            search_done = True
            results, _ = await web_search(prompt, max_results=5)
            if results:
                reply, err = await self.synthesize_search(channel_id, prompt, results, ctx)
                if not err and reply:
                    return save_ctx(reply), False

        reply, err = None, True
        if provider == "gemini":
            reply, err = await ask_gemini(system_msg, ctx, prompt, self.config, images)
        elif provider == "groq":
            reply, err = await ask_groq(ctx, prompt, self.config, system_msg=system_msg, images=images)
        elif provider == "mistral":
            reply, err = await ask_mistral(ctx, prompt, self.config, system_msg=system_msg)
        elif provider == "openai":
            reply, err = await ask_openai(ctx, prompt, self.config, system_msg=system_msg, images=images)
        elif provider == "deepseek":
            reply, err = await ask_deepseek(ctx, prompt, self.config, system_msg=system_msg, images=images)
        elif provider == "openrouter":
            reply, err = await ask_openrouter(ctx, prompt, self.config, system_msg=system_msg, images=images)
        elif provider == "huggingface":
            reply, err = await ask_huggingface(ctx, prompt, self.config, system_msg=system_msg)
        elif provider in ("custom", "literouter"):
            reply, err = await ask_custom(ctx, prompt, self.config, system_msg=system_msg, images=images)
        else:
            if (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")) and time.time() >= gemini_blocked_until:
                reply, err = await ask_gemini(system_msg, ctx, prompt, self.config, images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("groq_key") or OWNER_KEYS.get("GROQ_KEY")) and time.time() >= groq_blocked_until:
                reply, err = await ask_groq(ctx, prompt, self.config, system_msg=system_msg, images=images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")) and time.time() >= mistral_blocked_until:
                reply, err = await ask_mistral(ctx, prompt, self.config, system_msg=system_msg)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")) and time.time() >= openai_blocked_until:
                reply, err = await ask_openai(ctx, prompt, self.config, system_msg=system_msg, images=images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("custom_base_url") or self.config.get("custom_key") or self.config.get("custom_model")):
                reply, err = await ask_custom(ctx, prompt, self.config, system_msg=system_msg, images=images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("deepseek_key") or OWNER_KEYS.get("DEEPSEEK_KEY")) and time.time() >= deepseek_blocked_until:
                reply, err = await ask_deepseek(ctx, prompt, self.config, system_msg=system_msg, images=images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")) and time.time() >= openrouter_blocked_until:
                reply, err = await ask_openrouter(ctx, prompt, self.config, system_msg=system_msg, images=images)
                if not err:
                    if auto_search and not search_done and should_retry_with_search(reply):
                        results, _ = await web_search(prompt, max_results=5)
                        if results:
                            r2, e2 = await self.synthesize_search(channel_id, prompt, results, ctx)
                            if not e2:
                                return save_ctx(r2), False
                    return save_ctx(reply), False
            if (self.config.get("hf_key") or OWNER_KEYS.get("HF_KEY")) and time.time() >= huggingface_blocked_until:
                reply, err = await ask_huggingface(ctx, prompt, self.config, system_msg=system_msg)
                if not err:
                    return save_ctx(reply), False

        if not err and reply:
            return save_ctx(reply), False

        mins = []
        if gemini_blocked_until > time.time():
            mins.append(f"Gemini {int(gemini_blocked_until - time.time())}s")
        if groq_blocked_until > time.time():
            mins.append(f"Groq {int(groq_blocked_until - time.time())}s")
        if mistral_blocked_until > time.time():
            mins.append(f"Mistral {int(mistral_blocked_until - time.time())}s")
        if openai_blocked_until > time.time():
            mins.append(f"OpenAI {int(openai_blocked_until - time.time())}s")
        if deepseek_blocked_until > time.time():
            mins.append(f"DeepSeek {int(deepseek_blocked_until - time.time())}s")
        if openrouter_blocked_until > time.time():
            mins.append(f"OpenRouter {int(openrouter_blocked_until - time.time())}s")
        if huggingface_blocked_until > time.time():
            mins.append(f"HuggingFace {int(huggingface_blocked_until - time.time())}s")
        if mins:
            return f"All AI providers rate limited. Cooldowns: {', '.join(mins)}.", True
        return "No AI providers available. Check owner API keys.", True

    async def handle_message(self, message):
        # 1. Never respond to self (prevent self-looping)
        if self.client.user and message.author.id == self.client.user.id:
            return

        bot_talk_enabled = bool(self.config.get("bot_conversation_enabled", False))

        # 2. If message is from a bot and bot talk is toggled off, ignore immediately
        if message.author.bot and not bot_talk_enabled:
            return

        content_raw = (message.content or "").strip()
        clean_text = content_raw
        if self.client.user:
            clean_text = re.sub(r'<@!?\d+>', '', clean_text).strip()

        # Check interaction status
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = (self.client.user in message.mentions) if self.client.user else False

        # Check name call / triggers (works for users, and for bots when bot talk is enabled)
        is_name_called = self.is_name_called(content_raw)

        # Check open chat triggers (for human users when open_chat_enabled is on)
        is_open_chat = bool(self.config.get("open_chat_enabled", False)) and not message.author.bot

        # Check if this message is a Discord reply referencing one of our previous messages
        is_referencing_self = False
        if message.reference and message.reference.message_id:
            if message.reference.message_id in self.recent_sent_message_ids:
                is_referencing_self = True
            elif isinstance(getattr(message.reference, "resolved", None), discord.Message):
                if self.client.user and message.reference.resolved.author.id == self.client.user.id:
                    is_referencing_self = True
            else:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    if self.client.user and ref_msg.author.id == self.client.user.id:
                        is_referencing_self = True
                        self.recent_sent_message_ids.add(ref_msg.id)
                except Exception:
                    pass

        # If from another bot, it MUST be addressed to us (via name call, @mention, or replying directly to our message)
        is_bot_reply_to_me = message.author.bot and bot_talk_enabled and (is_referencing_self or is_name_called or is_mentioned)

        # Ignore unaddressed messages from other bots
        if message.author.bot and not is_bot_reply_to_me:
            return

        # Track exchange counts & rate limiting for bot conversations
        if message.author.bot:
            cid = str(message.channel.id)
            now = time.time()
            # Reset exchange counter if it has been > 45s since last exchange
            if now - self.bot_reply_last_time[cid] > 45.0:
                self.bot_reply_counts[cid] = 0
            self.bot_reply_last_time[cid] = now

            max_ex = max(1, min(15, int(self.config.get("bot_conversation_max", 3))))
            if self.bot_reply_counts[cid] >= max_ex:
                print(f"[BOT TALK] Max exchanges ({max_ex}) reached between {self.bot_name} and {message.author.display_name} in channel {cid}. Pausing bot conversation.")
                return
            self.bot_reply_counts[cid] += 1
        else:
            self.bot_reply_counts[str(message.channel.id)] = 0

        # Check prefix commands (only human users)
        is_prefix_cmd = not message.author.bot and (
            content_raw == "!gt" or content_raw.startswith("!gt ") or
            content_raw.startswith((
                "!sync", "!test", "!reset", "!forgetme", "!purgeme", "!clearmemory", "!purgeall",
                "!search ", "!ping", "!pong", "!toggle", "!provider", "!set ", "!config",
                "!settings", "!models", "!model ", "!voice ", "!tts", "!greettest", "!testgreet"
            ))
        )

        has_direct_attachment = bool(message.attachments) and (is_mentioned or is_dm or is_name_called or is_open_chat or is_bot_reply_to_me)
        is_direct_interaction = is_dm or is_mentioned or is_name_called or is_open_chat or is_prefix_cmd or has_direct_attachment or is_bot_reply_to_me

        # ─── IDLE BOT & MEMORY ISOLATION ───
        # Bots that are idle or not interacted with for >8 hours must not read chat or record memory.
        # Only the bot directly interacted with processes memory updates.
        if not message.author.bot:
            if is_direct_interaction:
                self.record_interaction(message.author.id)
                if self.config.get("user_memory_enabled", True):
                    await update_user_profile(message.author, message.content, message.guild, client=self.client, bot_config=self.config)
            else:
                if self.is_idle(8.0) or self.is_user_idle(message.author.id, 8.0):
                    return
                # Ignore unaddressed background chat
                return

        # Prefix Commands
        # ─── !gt / !greettest: Instant Greeting Test ──────────
        if content_raw == "!gt" or content_raw.startswith("!gt ") or content_raw in ("!greettest", "!testgreet") or content_raw.startswith("!greettest "):
            if not message.guild:
                await message.reply("⚠️ `!gt` can only be used inside a Discord server.")
                return

            is_admin = message.author.guild_permissions.manage_guild or message.author.guild_permissions.administrator
            is_owner = await self.check_owner(message.author.id)
            if not is_admin and not is_owner:
                await message.reply("❌ You need `Manage Server` or `Administrator` permissions to test greetings.", delete_after=5)
                return

            target_member = message.mentions[0] if message.mentions else message.author
            async with message.channel.typing():
                ok, res_msg = await self.generate_and_send_welcome(
                    target_member, target_channel=message.channel, is_test=True, trigger_user=message.author
                )
            if not ok:
                await message.reply(f"⚠️ Greeting test notice: {res_msg}")
            return

        if message.content == "!sync":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            await self.tree.sync()
            await message.reply("Global sync triggered!")
            return
        if message.content == "!sync here":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            if message.guild is None:
                await message.reply("Use this in a server.")
                return
            await self.tree.sync(guild=discord.Object(id=message.guild.id))
            await message.reply("Commands synced to this server!")
            return
        if message.content == "!testgemini":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_gemini("You are a test bot.", [], "Say 'Gemini is working'", self.config)
            await message.reply(f"Gemini test: {reply}")
            return
        if message.content == "!testgroq":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_groq([], "Say 'Groq is working' and nothing else.", self.config)
            await message.reply(f"Groq test: {reply}")
            return
        if message.content == "!testmistral":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_mistral([], "Say 'Mistral is working' and nothing else.", self.config)
            await message.reply(f"Mistral test: {reply}")
            return
        if message.content == "!testopenai":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_openai([], "Say 'OpenAI is working' and nothing else.", self.config)
            await message.reply(f"OpenAI test: {reply}")
            return
        if message.content == "!testdeepseek":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_deepseek([], "Say 'DeepSeek is working' and nothing else.", self.config)
            await message.reply(f"DeepSeek test: {reply}")
            return
        if message.content == "!testopenrouter":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_openrouter([], "Say 'OpenRouter is working' and nothing else.", self.config)
            await message.reply(f"OpenRouter test: {reply}")
            return
        if message.content == "!testhf":
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_huggingface([], "Say 'Hugging Face is working' and nothing else.", self.config)
            await message.reply(f"Hugging Face test: {reply}")
            return
        if message.content in ("!testcustom", "!testliterouter", "!testendpoint"):
            if not await self.check_owner(message.author.id):
                await message.reply("Owner only.", delete_after=5)
                return
            async with message.channel.typing():
                reply, err = await ask_custom([], "Say 'Custom endpoint is working' and nothing else.", self.config)
            await message.reply(f"Custom Endpoint test: {reply}")
            return
        if message.content == "!reset":
            self.clear_context(message.channel.id)
            await message.reply("🧹 Channel context memory cleared.")
            return
        if message.content in ("!forgetme", "!purgeme", "!clearmemory"):
            uid = str(message.author.id)
            global_user_profiles.pop(uid, None)
            save_global_user_profiles()
            self.interacted_users.discard(uid)
            self.save()
            await message.reply(f"🧹 All long-term memories, facts, and profile data for **{message.author.display_name}** have been completely wiped.")
            return
        if message.content in ("!purgeall", "!purgememory all"):
            if not await self.check_owner(message.author.id):
                await message.reply("❌ Owner only.", delete_after=5)
                return
            channel_count = len(self.contexts)
            profile_count = len(global_user_profiles)
            self.contexts.clear()
            global_user_profiles.clear()
            save_global_user_profiles()
            self.interacted_users.clear()
            self.save()
            await message.reply(f"💥 **Full AI Memory Purged:** Wiped {channel_count} active channel contexts and {profile_count} user memory profiles from RAM & disk.")
            return
        if message.content.startswith("!search "):
            q = message.content[8:].strip()
            if not q:
                await message.reply("Usage: `!search <query>`")
                return
            ok, remaining = self.check_cooldown(message.author.id)
            if not ok:
                await message.reply(f"Slow down! Wait {remaining}s.")
                return
            async with message.channel.typing():
                results, serr = await web_search(q, max_results=5)
                if serr or not results:
                    await message.reply(f"Search failed: {serr or 'No results.'}")
                    return
                reply, ai_err = await self.synthesize_search(message.channel.id, q, results)
            if not ai_err:
                header = f"**Search:** `{q}`\n\n"
                await self.send_split_messages(message.channel, header + reply, reply_to=message)
                self.message_count += 1
                source_lines = [f"{i}. [{r['title']}]({r['url']})" for i, r in enumerate(results[:5], 1)]
                source_embed = discord.Embed(title="Sources", description="\n".join(source_lines), color=0x2b2d42)
            lines = [f"**Web search:** `{q}`\n"]
            for i, r in enumerate(results[:5], 1):
                snippet = r["snippet"][:180] + "..." if len(r["snippet"]) > 180 else r["snippet"]
                lines.append(f"**{i}.** [{r['title']}]({r['url']})\n{snippet}\n")
            embed = discord.Embed(title="Search Results", description="\n".join(lines), color=0x4f8cff)
            embed.set_footer(text="via DuckDuckGo Lite | synthesis unavailable")
            await message.reply(embed=embed)
            return

        # ─── PING & TOGGLE PREFIX COMMANDS ─────────────────
        if message.content in ("!ping", "!pong"):
            ws_latency = round(self.client.latency * 1000) if self.client.latency else 0
            active_p = self.config.get("provider", "auto")
            if active_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{active_p}_model"
            elif active_p == "openai":
                model_key = "openai_chat_model"
            elif active_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif active_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            active_m = self.config.get(model_key, "default")
            embed = discord.Embed(
                title=f"🏓 Pong! [{self.bot_name}]",
                description=(
                    f"⚡ **Gateway Latency**: `{ws_latency}ms`\n"
                    f"🌐 **Active Provider**: `{active_p}`\n"
                    f"🧠 **Model**: `{active_m}`\n"
                    f"🔋 **Status**: `Operational`"
                ),
                color=0x00ffcc
            )
            embed.set_footer(text=f"Bot ID: {self.bot_id}")
            await message.reply(embed=embed)
            return

        if message.content.startswith("!toggle") or message.content.startswith("!provider"):
            if not await self.check_owner(message.author.id):
                await message.reply("❌ Owner only.", delete_after=5)
                return
            parts = message.content.split(None, 1)
            target_prov = parts[1].strip() if len(parts) > 1 else None
            old_p, new_p = self.toggle_provider(target_prov)
            if new_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{new_p}_model"
            elif new_p == "openai":
                model_key = "openai_chat_model"
            elif new_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif new_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            curr_model = self.config.get(model_key, "default")
            toast = self.format_toast_embed(
                f"{self.bot_name} // Provider Toggled",
                f"Switched provider: `{old_p}` ➔ **`{new_p}`**\nActive Model: **`{curr_model}`**",
                color=0x4f8cff
            )
            await message.reply(embed=toast)
            return

        is_mentioned = (self.client.user in message.mentions) if self.client.user else False
        is_dm = isinstance(message.channel, discord.DMChannel)

        # Configuration commands via @mention, DM, or prefix: e.g. "@Yuna gemini: gemini-1.5-flash-8b"
        content_raw = message.content.strip()
        clean_text = content_raw
        if self.client.user:
            clean_text = re.sub(r'<@!?\d+>', '', clean_text).strip()

        # Check for invite in mention / command: e.g. "@Bot invite", "!invite"
        clean_low = clean_text.lower()
        if (is_mentioned or is_dm or content_raw.startswith("!invite")) and (
            clean_low in ("invite", "invite link", "inv", "add", "install", "invite bot", "bot invite", "link") or
            content_raw.strip().lower() in ("!invite", "!inv") or
            re.search(r'\b(invite|invite\s+link|add\s+bot|install\s+app)\b', clean_low)
        ):
            client_id = self.client.user.id if self.client.user else ""
            if client_id:
                server_invite = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions=8&scope=bot%20applications.commands"
                user_app_invite = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=applications.commands"
                embed = discord.Embed(
                    title=f"🔗 Invite & Install {self.bot_name or 'Bot'}",
                    description="Choose how you'd like to add or use this bot:",
                    color=0x8a9a8a
                )
                embed.add_field(
                    name="🏰 Add to Server (Bot & Commands)",
                    value=f"[**Click to Invite to Server**]({server_invite})\n*Adds {self.bot_name} to your Discord server with full features & commands.*",
                    inline=False
                )
                embed.add_field(
                    name="👤 Install as User App (Use in DMs & Any Server)",
                    value=f"[**Click to Install to Account**]({user_app_invite})\n*Allows using slash commands anywhere, including private DMs & any server without server invite.*",
                    inline=False
                )
                embed.set_footer(text=f"Bot ID: {self.bot_id}")
                await self.safe_reply(message, embed=embed)
                return

        # Check for ping in mention: e.g. "@Bot ping"
        if (is_mentioned or is_dm) and clean_text.lower() in ("ping", "pong", "!ping", "!pong"):
            ws_latency = round(self.client.latency * 1000) if self.client.latency else 0
            active_p = self.config.get("provider", "auto")
            if active_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{active_p}_model"
            elif active_p == "openai":
                model_key = "openai_chat_model"
            elif active_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif active_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            active_m = self.config.get(model_key, "default")
            embed = discord.Embed(
                title=f"🏓 Pong! [{self.bot_name}]",
                description=(
                    f"⚡ **Gateway Latency**: `{ws_latency}ms`\n"
                    f"🌐 **Active Provider**: `{active_p}`\n"
                    f"🧠 **Model**: `{active_m}`\n"
                    f"🔋 **Status**: `Operational`"
                ),
                color=0x00ffcc
            )
            embed.set_footer(text=f"Bot ID: {self.bot_id}")
            await message.reply(embed=embed)
            return

        # Check for toggle in mention: e.g. "@Bot toggle" or "@Bot toggle provider" or "@Bot toggle groq"
        if (is_mentioned or is_dm) and (clean_text.lower().startswith("toggle") or clean_text.lower().startswith("switch")):
            if not await self.check_owner(message.author.id):
                await message.reply("❌ **Owner Only**: Only the bot owner can toggle the provider.", delete_after=8)
                return
            parts = clean_text.split()
            target_prov = None
            if len(parts) > 1:
                cand = parts[1].lower()
                if cand in ("provider", "model") and len(parts) > 2:
                    target_prov = parts[2].lower()
                elif cand in ("auto", "gemini", "groq", "mistral", "openai", "custom", "literouter", "deepseek", "openrouter", "huggingface"):
                    target_prov = cand
            old_p, new_p = self.toggle_provider(target_prov)
            if new_p in ("gemini", "groq", "mistral", "deepseek"):
                model_key = f"{new_p}_model"
            elif new_p == "openai":
                model_key = "openai_chat_model"
            elif new_p in ("custom", "literouter"):
                model_key = "custom_model"
            elif new_p == "huggingface":
                model_key = "huggingface_model"
            else:
                model_key = "model"
            curr_model = self.config.get(model_key, "default")
            toast = self.format_toast_embed(
                f"{self.bot_name} // Provider Toggled",
                f"Switched provider: `{old_p}` ➔ **`{new_p}`**\nActive Model: **`{curr_model}`**",
                color=0x4f8cff
            )
            await message.reply(embed=toast)
            return

        # If user just pinged the bot with no message (e.g. "@Bot")
        if is_mentioned and not clean_text and not message.attachments:
            ws_latency = round(self.client.latency * 1000) if self.client.latency else 0
            active_p = self.config.get("provider", "auto")
            toast = self.format_toast_embed(
                f"{self.bot_name} Online",
                f"👋 Hey **{message.author.display_name}**! I'm online and ready.\nAsk me anything or use `/ask`!\n*(Ping: `{ws_latency}ms` • Provider: `{active_p}`)*",
                color=0x8a9a8a
            )
            await message.reply(embed=toast)
            return

        # Avatar / PFP Update Command
        is_pfp_cmd = False
        pfp_target_url = None
        if (is_mentioned or is_dm or content_raw.startswith("!")):
            low_clean = clean_text.lower().strip()
            if low_clean.startswith(("pfp:", "avatar:", "avatar_url:", "pfp =", "avatar =", "set pfp", "set avatar", "update pfp", "update avatar", "!pfp", "!avatar")):
                is_pfp_cmd = True
                parts = re.split(r'[:=\s]+', clean_text, maxsplit=1)
                if len(parts) > 1 and parts[1].strip().startswith("http"):
                    pfp_target_url = parts[1].strip()
            elif low_clean in ("pfp", "avatar", "!pfp", "!avatar") and message.attachments:
                is_pfp_cmd = True

        if is_pfp_cmd:
            if not await self.check_owner(message.author.id):
                await message.reply("❌ **Owner Only**: Only the bot owner can update my avatar.", delete_after=8)
                return

            img_bytes = None
            final_pfp_url = None

            # 1. Check direct image attachments
            if message.attachments:
                for att in message.attachments:
                    ct = att.content_type or ""
                    ext = Path(att.filename).suffix.lower()
                    if ct.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                        async with message.channel.typing():
                            try:
                                img_bytes = await att.read()
                                final_pfp_url = att.url
                                break
                            except Exception as e:
                                await message.reply(f"❌ Failed to read attachment: {e}")
                                return

            # 2. Check URL in text
            if not img_bytes and pfp_target_url:
                async with message.channel.typing():
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(pfp_target_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                                if r.status == 200:
                                    img_bytes = await r.read()
                                    final_pfp_url = pfp_target_url
                                else:
                                    await message.reply(f"❌ Failed to download image from URL (HTTP {r.status})")
                                    return
                    except Exception as e:
                        await message.reply(f"❌ Could not download image URL: {e}")
                        return

            if not img_bytes:
                await message.reply("⚠️ Please provide an image URL (e.g. `@bot pfp: https://...`) or attach an image file directly with your message.")
                return

            async with message.channel.typing():
                discord_updated = False
                err_note = ""
                try:
                    if self.client.user:
                        await self.client.user.edit(avatar=img_bytes)
                        discord_updated = True
                except discord.HTTPException as he:
                    err_note = f" (Discord API Note: {he.text if hasattr(he, 'text') else he})"
                except Exception as ex:
                    err_note = f" (Note: {ex})"

                if final_pfp_url:
                    self.config["avatar_url"] = final_pfp_url
                    self.config["pfp"] = final_pfp_url
                self.save()

                if SUPABASE_URL and SUPABASE_SERVICE_KEY and self.bot_id:
                    try:
                        async with aiohttp.ClientSession() as session:
                            await session.patch(
                                f"{SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.{self.bot_id}",
                                headers={
                                    "apikey": SUPABASE_SERVICE_KEY,
                                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                                    "Content-Type": "application/json",
                                    "Prefer": "return=minimal"
                                },
                                json={"settings": self.config, "updated_at": datetime.utcnow().isoformat()}
                            )
                    except Exception:
                        pass

                toast = self.format_toast_embed(
                    f"{self.bot_name} // Avatar Updated",
                    f"✅ **Avatar successfully updated!**{err_note}\nNew profile picture is now active on Discord and Web Studio.",
                    color=0x00ffcc
                )
                if final_pfp_url:
                    toast.set_thumbnail(url=final_pfp_url)
                await message.reply(embed=toast)
                return

        config_match = None
        # Pattern 1: field: value OR field = value
        m_field = re.match(r'^([a-zA-Z0-9_\-]+)\s*[:=]\s*(.+)$', clean_text, re.DOTALL)
        if m_field:
            candidate_field = m_field.group(1).strip().lower()
            if candidate_field in CONFIG_FIELD_MAPPINGS:
                config_match = (candidate_field, m_field.group(2).strip())

        # Pattern 2: "!set field value", "!config field value", "set field value"
        if not config_match and (is_mentioned or is_dm or content_raw.startswith("!")):
            m_cmd = re.match(r'^(?:!set|!config|set|config)\s+([a-zA-Z0-9_\-]+)\s*(?:[:=]|\s)\s*(.+)$', clean_text, re.DOTALL | re.IGNORECASE)
            if m_cmd:
                candidate_field = m_cmd.group(1).strip().lower()
                if candidate_field in CONFIG_FIELD_MAPPINGS:
                    config_match = (candidate_field, m_cmd.group(2).strip())
            elif clean_text.lower().startswith("!model ") or clean_text.lower().startswith("model: "):
                val = clean_text.split(None, 1)[1].strip() if " " in clean_text else ""
                if val:
                    config_match = ("model", val)
            elif clean_text.lower().startswith("!provider ") or clean_text.lower().startswith("provider: "):
                val = clean_text.split(None, 1)[1].strip() if " " in clean_text else ""
                if val:
                    config_match = ("provider", val)

        if config_match and (is_mentioned or is_dm or content_raw.startswith("!")):
            field_name, field_val = config_match
            is_owner = await self.check_owner(message.author.id)
            if not is_owner:
                await message.reply("❌ **Owner Only**: Only the bot owner can modify my model and configuration.", delete_after=8)
                return
            ok, key, old_v, new_v = self.update_setting(field_name, field_val)
            if ok:
                toast = self.format_toast_embed(
                    f"{self.bot_name} // Model Updated",
                    f"Field **`{key}`** updated:\n`{old_v}` ➔ **`{new_v}`**\n*(Active Provider: `{self.config.get('provider', 'auto')}`)*",
                    color=0x00ffcc
                )
                await message.reply(embed=toast)
                return
            else:
                await message.reply(f"❌ Failed to update `{field_name}`: {new_v}")
                return

        # Query config via "!config" or "!settings"
        if content_raw in ("!config", "!settings", "!models"):
            if not await self.check_owner(message.author.id):
                await message.reply("❌ Owner only.", delete_after=5)
                return
            embed = discord.Embed(
                title=f"📋 {self.bot_name} // Current Configuration",
                color=0x7a8a9a
            )
            embed.add_field(name="Active Provider", value=f"`{self.config.get('provider', 'auto')}`", inline=True)
            embed.add_field(name="Temperature", value=f"`{self.config.get('temperature', 0.7)}`", inline=True)
            embed.add_field(name="Max Tokens", value=f"`{self.config.get('max_tokens', 800)}`", inline=True)
            embed.add_field(name="🧠 Active Models", value=(
                f"• **Gemini**: `{self.config.get('gemini_model', 'None')}`\n"
                f"• **Groq**: `{self.config.get('groq_model', 'None')}`\n"
                f"• **Mistral**: `{self.config.get('mistral_model', 'None')}`\n"
                f"• **OpenAI**: `{self.config.get('openai_chat_model', 'None')}`\n"
                f"• **Custom Endpoint**: `{self.config.get('custom_model', 'None')}` (URL: `{self.config.get('custom_base_url') or 'Default'}`)\n"
                f"• **DeepSeek**: `{self.config.get('deepseek_model', 'None')}`\n"
                f"• **OpenRouter**: `{self.config.get('model', 'None')}`\n"
                f"• **Hugging Face**: `{self.config.get('huggingface_model', 'None')}`"
            ), inline=False)
            embed.set_footer(text=f"Bot ID: {self.bot_id} • Use @{self.bot_name} <field>: <model> to change")
            await message.reply(embed=embed)
            return

        # Categorize attachments
        image_atts = []
        video_atts = []
        audio_atts = []
        file_atts = []
        if message.attachments:
            for att in message.attachments:
                ct = att.content_type or ""
                ext = Path(att.filename).suffix.lower()
                if ct.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                    image_atts.append(att)
                elif ct.startswith("video/") or ext in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp"):
                    video_atts.append(att)
                elif ct.startswith("audio/") or ext in (".ogg", ".mp3", ".wav", ".m4a", ".flac"):
                    audio_atts.append(att)
                elif ext in (".pdf", ".docx", ".csv") or ct == "application/pdf":
                    file_atts.append(att)

        # Auto-STT
        if self.config.get("auto_stt", False) and audio_atts:
            att = audio_atts[0]
            async with message.channel.typing():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(att.url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                            audio_bytes = await resp.read()
                    atext, aerr = await transcribe_audio(audio_bytes, att.filename)
                    if aerr:
                        await message.reply(f"Transcription failed: {aerr}")
                        return
                    transcribed_prompt = f"[Voice message transcribed]: {atext}"
                    if message.content:
                        transcribed_prompt += f"\n\nUser also said: {message.content}"
                    ok, remaining = self.check_cooldown(message.author.id)
                    if not ok:
                        await message.reply(f"Slow down! Wait {remaining}s.")
                        return
                    reply, err = await self.ask_ai(
                        message.channel.id, transcribed_prompt,
                        user_id=message.author.id, user_name=message.author.display_name,
                        guild=message.guild, is_dm=is_dm
                    )
                    if not err:
                        self.message_count += 1
                        await self.send_split_messages(message.channel, reply, reply_to=message)
                        if self.config.get("tts_enabled"):
                            audio = await speak(reply, self.config)
                            if audio:
                                await message.reply(file=discord.File(io.BytesIO(audio), filename="voice.mp3"))
                    return
                except Exception as e:
                    await message.reply(f"Audio processing error: {e}")
                    return

        # Video watching
        if self.config.get("video_watching_enabled", True) and video_atts:
            await self.handle_video_attachment(message, video_atts[0])
            return

        # File reading (PDF/DOCX/CSV)
        if self.config.get("file_reading_enabled", True) and file_atts:
            await self.handle_file_attachment(message, file_atts[0])
            return

        # Image vision
        if self.config.get("vision_enabled") and image_atts:
            addressed = is_mentioned or is_dm or is_name_called or is_open_chat
            if addressed:
                await self.handle_image_attachments(message, image_atts)
                return

        # Mention, DM, Name call, Bot Talk reply, or Open chat text handling
        if is_mentioned or is_dm or is_name_called or is_open_chat or is_bot_reply_to_me:
            clean = re.sub(r'<@!?\d+>', '', message.content).strip()
            if not clean:
                if message.author.bot:
                    return
                ws_latency = round(self.client.latency * 1000) if self.client.latency else 0
                active_p = self.config.get("provider", "auto")
                toast = self.format_toast_embed(
                    f"{self.bot_name} Online",
                    f"👋 Hey **{message.author.display_name}**! I'm online and ready.\nAsk me anything or use `/ask`!\n*(Ping: `{ws_latency}ms` • Provider: `{active_p}`)*",
                    color=0x8a9a8a
                )
                await message.reply(embed=toast)
                return

            # If responding to another bot, add a brief realistic typing delay (1.2s - 2.5s)
            if message.author.bot:
                await asyncio.sleep(random.uniform(1.2, 2.5))
            else:
                ok, remaining = self.check_cooldown(message.author.id)
                if not ok:
                    await message.reply(f"Slow down! Wait {remaining}s.")
                    return

            # Commands only for human users
            if not message.author.bot:
                if clean.lower() == "!tts on":
                    self.config["tts_enabled"] = True
                    self.save()
                    await message.reply("TTS enabled. Voice replies will include audio.")
                    return
                if clean.lower() == "!tts off":
                    self.config["tts_enabled"] = False
                    self.save()
                    await message.reply("TTS disabled.")
                    return
                if clean.lower().startswith("!voice "):
                    vid = clean[7:].strip()
                    self.config["fish_voice_id"] = vid
                    self.save()
                    await message.reply(f"Voice ID set to: `{vid}`")
                    return
                if clean.lower() == "!tts status":
                    tts_on = self.config.get("tts_enabled", False)
                    provider = self.config.get("tts_provider", "auto")
                    await message.reply(f"TTS: {'ON' if tts_on else 'OFF'}\nProvider: `{provider}`")
                    return

            async with message.channel.typing():
                reply, err = await self.ask_ai(
                    message.channel.id, clean,
                    user_id=message.author.id, user_name=message.author.display_name,
                    guild=message.guild, is_dm=is_dm
                )
                if not err:
                    self.message_count += 1
            if err:
                if not message.author.bot:
                    await message.reply(reply)
            else:
                await self.send_split_messages(message.channel, reply, reply_to=message)
                if self.config.get("tts_enabled") and not message.author.bot:
                    audio = await speak(reply, self.config)
                    if audio:
                        await message.reply(file=discord.File(io.BytesIO(audio), filename="voice.mp3"))
            return

    async def handle_image_attachments(self, message, atts):
        """Process image attachments with robust multi-provider vision fallback."""
        async with message.channel.typing():
            try:
                images = []
                for att in atts[:4]:
                    img_bytes, mime = await download_image(att.url)
                    if img_bytes:
                        images.append((img_bytes, mime))
                if not images:
                    await message.reply("Could not download attached image(s).")
                    return

                prompt = message.content.replace(f"<@{self.client.user.id}>", "").strip() or "Describe what you see in this image."
                vision_provider = self.config.get("vision_provider", "gemini")
                history = self.get_context(message.channel.id)
                system_msg = self.config.get("personality", "You are a helpful assistant.")
                
                reply, err = None, True
                image_bytes_payload = [b for b, m in images] if len(images) > 1 else images[0][0]
                mime_type = images[0][1]

                if vision_provider == "gemini" and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                    reply, err = await ask_gemini_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")):
                        reply, err = await ask_openai_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")):
                        vmodel = (self.config.get("vision_model") or "").strip() or None
                        reply, err = await ask_openrouter_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history, vision_model=vmodel)
                    if err and (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")):
                        reply, err = await ask_mistral_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                elif vision_provider == "openai" and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")):
                    reply, err = await ask_openai_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                        reply, err = await ask_gemini_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                elif vision_provider == "mistral" and (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")):
                    reply, err = await ask_mistral_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                        reply, err = await ask_gemini_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                else:
                    vmodel = (self.config.get("vision_model") or "").strip() or None
                    if (self.config.get("openrouter_key") or OWNER_KEYS.get("OPENROUTER_KEY")):
                        reply, err = await ask_openrouter_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history, vision_model=vmodel)
                    if err and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                        reply, err = await ask_gemini_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")):
                        reply, err = await ask_openai_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)
                    if err and (self.config.get("mistral_key") or OWNER_KEYS.get("MISTRAL_KEY")):
                        reply, err = await ask_mistral_vision(system_msg, prompt, image_bytes_payload, mime_type, self.config, history=history)

                if not err and reply:
                    self.add_to_context(message.channel.id, "user", f"[User sent image(s)]: {prompt}", user_name=message.author.display_name, user_id=message.author.id)
                    self.add_to_context(message.channel.id, "assistant", reply)
                    self.message_count += 1
                    await self.send_split_messages(message.channel, reply, reply_to=message)
                    if self.config.get("tts_enabled"):
                        audio = await speak(reply, self.config)
                        if audio:
                            await message.reply(file=discord.File(io.BytesIO(audio), filename="voice.mp3"))
                else:
                    await message.reply(f"Vision error: {reply}")
            except Exception as e:
                await message.reply(f"Image processing error: {e}")

    async def handle_video_attachment(self, message, att):
        """Process video attachments by analyzing frames with vision."""
        async with message.channel.typing():
            try:
                ext = Path(att.filename).suffix.lower()
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
                os.close(tmp_fd)
                async with aiohttp.ClientSession() as session:
                    async with session.get(att.url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                        if resp.status != 200:
                            await message.reply("Could not download video.")
                            return
                        with open(tmp_path, "wb") as f:
                            f.write(await resp.read())
                
                # 1. Extract chronological frames
                frames_dir = tempfile.mkdtemp()
                cmd = ["ffmpeg", "-y", "-i", tmp_path, "-vf", "fps=0.5,scale=640:-1", "-vframes", "4", os.path.join(frames_dir, "f%03d.jpg")]
                subprocess.run(cmd, capture_output=True, timeout=35)
                frame_files = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith(".jpg")])
                frame_bytes_list = []
                for fp in frame_files:
                    with open(fp, "rb") as f:
                        frame_bytes_list.append(f.read())
                shutil.rmtree(frames_dir, ignore_errors=True)

                # 2. Extract and transcribe video audio track
                audio_transcription = None
                audio_tmp_fd, audio_tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(audio_tmp_fd)
                try:
                    acmd = ["ffmpeg", "-y", "-i", tmp_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_tmp_path]
                    subprocess.run(acmd, capture_output=True, timeout=35)
                    if os.path.exists(audio_tmp_path) and os.path.getsize(audio_tmp_path) > 1024:
                        with open(audio_tmp_path, "rb") as af:
                            audio_bytes = af.read()
                        atext, aerr = await transcribe_audio(audio_bytes, "audio.wav")
                        if not aerr and atext and atext.strip():
                            audio_transcription = atext.strip()
                except Exception as e:
                    print(f"[VIDEO AUDIO ERROR] {e}")
                finally:
                    if os.path.exists(audio_tmp_path):
                        try: os.remove(audio_tmp_path)
                        except: pass

                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

                if not frame_bytes_list:
                    await message.reply("Could not extract frames from video.")
                    return

                user_q = message.content.replace(f"<@{self.client.user.id}>", "").strip()
                prompt = f"[VIDEO PLAYBACK & AUDIO INGESTION]\nThe user shared a video ({len(frame_bytes_list)} chronological frames attached)."
                if user_q:
                    prompt += f"\nUser comment/question: {user_q}"
                if audio_transcription:
                    prompt += f"\n\n[VIDEO AUDIO TRACK TRANSCRIPTION]:\n\"{audio_transcription}\""
                prompt += "\n\nReact and respond in full character to what is shown on screen and what is spoken in the video audio!"

                vision_provider = self.config.get("vision_provider", "gemini")
                reply, err = None, True
                if vision_provider == "gemini" or (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                    reply, err = await ask_gemini_vision(self.config.get("personality", ""), prompt, frame_bytes_list, "image/jpeg", self.config)
                    if err and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")):
                        reply, err = await ask_openai_vision(self.config.get("personality", ""), prompt, frame_bytes_list, "image/jpeg", self.config)
                elif vision_provider == "openai" and (self.config.get("openai_key") or OWNER_KEYS.get("OPENAI_KEY")):
                    reply, err = await ask_openai_vision(self.config.get("personality", ""), prompt, frame_bytes_list, "image/jpeg", self.config)
                    if err and (self.config.get("gemini_key") or OWNER_KEYS.get("GEMINI_KEY")):
                        reply, err = await ask_gemini_vision(self.config.get("personality", ""), prompt, frame_bytes_list, "image/jpeg", self.config)
                else:
                    reply, err = await ask_gemini_vision(self.config.get("personality", ""), prompt, frame_bytes_list, "image/jpeg", self.config)
                
                if not err and reply:
                    self.message_count += 1
                    await self.send_split_messages(message.channel, reply, reply_to=message)
                else:
                    await message.reply(f"Video analysis failed: {reply}")
            except Exception as e:
                await message.reply(f"Video processing error: {e}")

    async def handle_file_attachment(self, message, att):
        """Process document attachments."""
        async with message.channel.typing():
            text = await read_file_attachment(att)
            if not text or text.startswith("File too large") or text.startswith("Unsupported"):
                await message.reply(text or "File reading error.")
                return
            file_prompt = f"The user uploaded file {att.filename}:\n\n{text[:4000]}\n\nUser question: {message.content or 'Summarize this file.'}"
            reply, err = await self.ask_ai(
                message.channel.id, file_prompt,
                user_id=message.author.id, user_name=message.author.display_name,
                guild=message.guild, is_dm=isinstance(message.channel, discord.DMChannel)
            )
            if not err:
                self.message_count += 1
                await self.send_split_messages(message.channel, reply, reply_to=message)
            else:
                await message.reply(reply)

    def save(self):
        path = os.path.join(USERS_DIR, f"{self.bot_id}.json")
        _atomic_json_save(path, {
            "bot_id": self.bot_id,
            "token": self.token,
            "access_key": self.access_key,
            "bot_name": self.bot_name,
            "owner_id": self.owner_id,
            "owner_username": getattr(self, "owner_username", "") or (self.config.get("owner_username") if self.config else "") or "",
            "config": self.config,
            "message_count": self.message_count,
            "interactions": self.message_count,
            "interacted_users": list(self.interacted_users),
        }, backup=False)

    async def close(self):
        await self.client.close()

async def sync_interaction_count_to_supabase(bot_id: str, count: int):
    """Syncs live Discord interaction count to Supabase user_bots settings so Web Studio updates in real time."""
    if not SUPABASE_SERVICE_KEY or not SUPABASE_URL or not bot_id:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.{bot_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    rows = await resp.json()
                    if rows and isinstance(rows, list) and len(rows) > 0:
                        row = rows[0]
                        st = row.get("settings") or {}
                        st["interactions"] = count
                        st["message_count"] = count
                        async with session.patch(url, headers=headers, json={"settings": st}) as p_resp:
                            pass
    except Exception:
        pass

async def sync_bot_crud_to_supabase(bot_id: str, method: str, bot_dict: dict = None):
    """Syncs bot creation, updates, and deletions to Supabase so Netlify frontend stays in sync with localhost."""
    if not SUPABASE_SERVICE_KEY or not SUPABASE_URL or not bot_id:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.{bot_id}"
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        async with aiohttp.ClientSession() as session:
            if method == "DELETE":
                async with session.delete(url, headers=headers): pass
                return
                
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    rows = await resp.json()
                    now_str = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                    if rows and len(rows) > 0:
                        payload = {
                            "settings": bot_dict.get("config", {}),
                            "bot_name": bot_dict.get("bot_name", "Bot"),
                            "updated_at": now_str
                        }
                        async with session.patch(url, headers=headers, json=payload): pass
                    else:
                        payload = {
                            "bot_id": bot_id,
                            "user_id": bot_dict.get("owner_id", ""),
                            "bot_name": bot_dict.get("bot_name", "Bot"),
                            "is_active": True,
                            "created_at": now_str,
                            "updated_at": now_str,
                            "settings": bot_dict.get("config", {})
                        }
                        token = bot_dict.get("token", "")
                        if token:
                            if fernet:
                                try:
                                    payload["encrypted_token"] = fernet.encrypt(token.encode()).decode()
                                except: pass
                            else:
                                payload["discord_token"] = token
                                
                        async with session.post(f"{SUPABASE_URL}/rest/v1/user_bots", headers=headers, json=payload): pass
    except Exception as e:
        print(f"[BRIDGE] sync_bot_crud_to_supabase error: {e}")

def record_bot_interaction(bot_id: str):
    if not bot_id:
        return 0
    cnt = 1
    if bot_id in manager.bots:
        b = manager.bots[bot_id]
        b.message_count += 1
        cnt = b.message_count
        try:
            b.save()
        except Exception:
            pass
        return cnt
    
    path = os.path.join(USERS_DIR, f"{bot_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            cur = int(d.get("message_count", 0) or d.get("interactions", 0) or 0) + 1
            d["message_count"] = cur
            d["interactions"] = cur
            _atomic_json_save(path, d, backup=False)
            return cur
        except Exception:
            pass
    return cnt

# --- BOT MANAGER --------------------------------------

class BotManager:
    def __init__(self):
        self.bots = {}

    async def load_all(self):
        for fname in os.listdir(USERS_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(USERS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                token = data.get("token", "")
                bot_id = str(data.get("bot_id", ""))
                if not token or not bot_id:
                    continue
                if token in _running_tokens or bot_id in self.bots:
                    continue
                bot = UserBot(bot_id, token, data)
                self.bots[bot_id] = bot
                asyncio.create_task(self._run_bot(bot))
                print(f"[MANAGER] Loaded bot {bot_id} ({bot.bot_name})")
            except Exception as e:
                print(f"[MANAGER] Failed to load {fname}: {e}")

    async def _run_bot(self, bot):
        _running_tokens.add(bot.token)
        try:
            await bot.client.start(bot.token)
        except discord.LoginFailure:
            print(f"[MANAGER] Bot {bot.bot_id} login failed (bad token)")
        except Exception as e:
            print(f"[MANAGER] Bot {bot.bot_id} error: {e}")
        finally:
            _running_tokens.discard(bot.token)
            print(f"[MANAGER] Bot {bot.bot_id} disconnected")

    async def add_bot(self, token, owner_id=None):
        bot_id, bot_name, disc_owner_id, avatar_url = await validate_discord_token(token)
        if not bot_id:
            return None, "Invalid bot token. Make sure it is a valid Discord Bot Token."
        final_owner = owner_id or disc_owner_id or ""
        if bot_id in self.bots:
            existing_bot = self.bots[bot_id]
            if existing_bot.owner_id and final_owner and existing_bot.owner_id != final_owner:
                return None, "This bot belongs to another user."
            return existing_bot.access_key, "Bot already connected."
            
        cfg = DEFAULT_CONFIG.copy()
        if avatar_url:
            cfg["avatar_url"] = avatar_url
            
        data = {
            "bot_id": bot_id,
            "token": token,
            "access_key": secrets.token_urlsafe(16),
            "bot_name": bot_name,
            "owner_id": final_owner,
            "config": cfg
        }
        bot = UserBot(bot_id, token, data)
        self.bots[bot_id] = bot
        bot.save()
        asyncio.create_task(self._run_bot(bot))
        return bot.access_key, None

    async def remove_bot(self, bot_id):
        if bot_id in self.bots:
            bot = self.bots[bot_id]
            _running_tokens.discard(bot.token)
            try:
                await bot.close()
            except Exception as e:
                print(f"[MANAGER] Error closing bot {bot_id}: {e}")
            del self.bots[bot_id]
        path = os.path.join(USERS_DIR, f"{bot_id}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def get_by_access_key(self, access_key):
        for bot in self.bots.values():
            if bot.access_key == access_key:
                return bot
        for fname in os.listdir(USERS_DIR):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(USERS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("access_key") == access_key:
                    bot = UserBot(data["bot_id"], data["token"], data)
                    self.bots[bot.bot_id] = bot
                    asyncio.create_task(self._run_bot(bot))
                    return bot
            except Exception:
                pass
        return None

    async def run(self):
        while True:
            await asyncio.sleep(3600)

async def validate_discord_token(token):
    headers = {"Authorization": f"Bot {token}"}
    timeout = aiohttp.ClientTimeout(total=10)
    for ssl_mode in [None, False]:
        try:
            connector = aiohttp.TCPConnector(ssl=ssl_mode) if ssl_mode is not None else None
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get("https://discord.com/api/v10/oauth2/applications/@me", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        bot_data = data.get("bot", {})
                        bot_id = str(data.get("id") or bot_data.get("id", ""))
                        username = bot_data.get("username", "Bot")
                        owner_id = str(data.get("owner", {}).get("id", ""))
                        avatar_hash = bot_data.get("avatar") or data.get("icon")
                        if avatar_hash:
                            avatar_url = f"https://cdn.discordapp.com/avatars/{bot_id}/{avatar_hash}.png?size=256"
                        else:
                            try:
                                disc = int(bot_data.get("discriminator", 0)) or (int(bot_id) >> 22)
                                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{disc % 5}.png"
                            except Exception:
                                avatar_url = ""
                        return bot_id, username, owner_id, avatar_url
                    return None, None, None, ""
        except Exception:
            if ssl_mode is None:
                continue
            return None, None, None, ""
    return None, None, None, ""

def get_auth_user_id(req):
    """
    Extracts authenticated user ID from Supabase JWT, Bearer token,
    X-User-Id header, or query parameters.
    """
    auth_hdr = req.headers.get("Authorization", "")
    token = ""
    if auth_hdr.startswith("Bearer "):
        token = auth_hdr[7:].strip()
    elif "access_key" in req.args:
        token = req.args.get("access_key", "").strip()
    elif "owner_id" in req.args:
        return req.args.get("owner_id", "").strip()
    elif "user_id" in req.args:
        return req.args.get("user_id", "").strip()
        
    x_user = req.headers.get("X-User-Id", "").strip()
    if x_user:
        return x_user
        
    if not token:
        return ""
        
    for bid, b in manager.bots.items():
        if b.access_key == token:
            return b.owner_id or b.access_key
            
    if "." in token:
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload = parts[1]
                padded = payload + "=" * ((4 - len(payload) % 4) % 4)
                data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
                uid = data.get("sub") or data.get("user_id") or data.get("email")
                if uid:
                    return str(uid)
        except Exception:
            pass
            
    return token

manager = BotManager()
bot_loop = None
_running_tokens = set()
_bridge_had_results = False

# --- FLASK APP ----------------------------------------

app = Flask(__name__)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route("/")
@app.route("/studio")
@app.route("/studio.html")
@app.route("/chat")
@app.route("/chat.html")
@app.route("/index.html")
@app.route("/home.html")
def studio_page():
    paths = [
        os.path.join(SCRIPT_DIR, "index.html"),
        os.path.join(SCRIPT_DIR, "studio.html"),
        os.path.join(SCRIPT_DIR, "designs", "index.html"),
        "/storage/emulated/0/discord-bot/index.html"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return Response(f.read(), mimetype="text/html; charset=utf-8")
            except Exception as e:
                return f"Studio read error: {e}", 500
    return "Studio index.html not found", 404

@app.route("/dashboard")
@app.route("/dashboard.html")
@app.route("/drafting")
@app.route("/drafting.html")
@app.route("/desk")
def dashboard_page():
    path = os.path.join(SCRIPT_DIR, "dashboard.html")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return Response(f.read(), mimetype="text/html; charset=utf-8")
        except Exception:
            pass
    return Response(DASHBOARD_HTML, mimetype="text/html; charset=utf-8")

@app.route("/designs/<path:filename>")
def serve_designs(filename):
    designs_dir = os.path.join(SCRIPT_DIR, "designs")
    file_path = os.path.join(designs_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return f"File {filename} not found", 404

@app.route("/api/bots", methods=["GET", "POST"])
def api_bots_list_or_add():
    user_id = get_auth_user_id(request)
    is_owner = (user_id == str(OWNER_ID)) if OWNER_ID else False
    scope = request.args.get("scope", "all").lower().strip()
    
    if request.method == "POST":
        data = request.get_json(silent=True, force=True) or {}
        name = (data.get("name") or data.get("bot_name") or "").strip()[:40] or "New Bot"
        emoji = (data.get("emoji") or "🤖").strip()[:4]
        bot_id = str(data.get("id") or data.get("bot_id") or f"bot_{int(time.time()*1000)}")
        token = data.get("token", "").strip()
        bot_owner = user_id or data.get("owner_id", "") or ""
        
        cfg = DEFAULT_CONFIG.copy()
        if "config" in data and isinstance(data["config"], dict):
            cfg.update(data["config"])
        elif "personality" in data:
            cfg["personality"] = data["personality"]
            if "greeting" in data: cfg["greeting"] = data["greeting"]
            if "role" in data: cfg["role"] = data["role"]
            if "desc" in data: cfg["desc"] = data["desc"]
            if "provider" in data: cfg["provider"] = data["provider"]
            if "model" in data: cfg["model"] = data["model"]
            if "model_slots" in data: cfg["model_slots"] = data["model_slots"]
            if "avatar_url" in data: cfg["avatar_url"] = data["avatar_url"]
            
        for k in ["custom_base_url", "custom_key", "custom_model", "openai_base_url", "privacy", "desc", "greeting", "role", "personality", "owner_id"]:
            if k in data and data[k]:
                cfg[k] = data[k]
            
        avatar_url = cfg.get("avatar_url") or data.get("avatar_url") or data.get("pfp") or ""
        
        if token:
            async def _val():
                return await validate_discord_token(token)
            try:
                val_fut = asyncio.run_coroutine_threadsafe(_val(), bot_loop)
                d_bid, d_name, d_owner, d_avatar = val_fut.result(timeout=10)
                if d_bid:
                    bot_id = d_bid
                    if not data.get("name"):
                        name = d_name
                    if d_avatar and not avatar_url:
                        avatar_url = d_avatar
                        cfg["avatar_url"] = d_avatar
                    if not bot_owner and d_owner:
                        bot_owner = d_owner
            except Exception:
                pass
        
        bot_dict = {
            "bot_id": bot_id,
            "bot_name": name,
            "token": token,
            "access_key": secrets.token_urlsafe(16),
            "owner_id": bot_owner,
            "emoji": emoji,
            "config": cfg
        }
        
        path = os.path.join(USERS_DIR, f"{bot_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bot_dict, f, indent=2)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})
            
        if token:
            try:
                bot = UserBot(bot_id, token, bot_dict)
                manager.bots[bot_id] = bot
                asyncio.run_coroutine_threadsafe(manager._run_bot(bot), bot_loop)
            except Exception:
                pass
                
        asyncio.run_coroutine_threadsafe(sync_bot_crud_to_supabase(bot_id, "POST", bot_dict), bot_loop)
                
        return jsonify({"ok": True, "bot": {
            "id": bot_id,
            "name": name,
            "emoji": emoji,
            "pfp": avatar_url or cfg.get("avatar_url"),
            "role": cfg.get("role", "AI Persona"),
            "desc": cfg.get("desc") or (cfg.get("personality", "")[:140]),
            "personality_preview": (cfg.get("personality", "")[:140]),
            "provider": cfg.get("provider", "auto"),
            "model": cfg.get("model", ""),
            "model_slots": cfg.get("model_slots", []),
            "online": True if token and bot_id in manager.bots and manager.bots[bot_id].client and manager.bots[bot_id].client.is_ready() else False,
            "is_active": True,
            "is_discord": bool(token),
            "is_mine": True,
            "privacy": cfg.get("privacy", "public"),
            "owner_id": bot_owner,
            "config": cfg
        }})

    bots = []
    seen_ids = set()
    
    # 1. From active manager.bots
    for bid, b in manager.bots.items():
        cfg = b.config or {}
        b_priv = (cfg.get("privacy") if cfg.get("privacy") is not None else "public") or "public"
        is_my_bot = bool(user_id and (b.owner_id == user_id or b.access_key == user_id))
        
        if scope == "mine":
            if not is_owner and not is_my_bot:
                continue
        else:
            if b_priv == "private" and not is_my_bot and not is_owner:
                continue
                
        seen_ids.add(str(bid))
        pfp = None
        if b.client and b.client.user and b.client.user.display_avatar:
            pfp = str(b.client.user.display_avatar.url)
        if not pfp:
            pfp = cfg.get("avatar_url") or cfg.get("pfp")
            
        bots.append({
            "id": str(bid),
            "name": b.bot_name or cfg.get("name", "Bot"),
            "emoji": cfg.get("emoji", "✦"),
            "pfp": pfp,
            "role": cfg.get("role") or (cfg.get("provider", "Discord").upper() + " Bot"),
            "desc": cfg.get("desc") or (cfg.get("personality", "")[:140]),
            "personality_preview": (cfg.get("personality", "")[:140]),
            "personality": cfg.get("personality", ""),
            "provider": cfg.get("provider", "auto"),
            "model": cfg.get("model", "") or cfg.get("gemini_model", "") or cfg.get("custom_model", ""),
            "model_slots": cfg.get("model_slots", []),
            "online": b.client.is_ready() if (b.client and b.client.is_ready()) else False,
            "is_active": True,
            "is_discord": bool(b.token),
            "is_mine": is_my_bot or is_owner,
            "privacy": b_priv,
            "access_key": b.access_key,
            "owner_id": b.owner_id,
            "owner_username": b.owner_username or (b.config.get("owner_username") if b.config else "") or "",
            "config": cfg,
            "message_count": b.message_count,
            "interactions": b.message_count
        })
        
    # 2. From USERS_DIR files
    if os.path.exists(USERS_DIR):
        for fname in sorted(os.listdir(USERS_DIR)):
            if not fname.endswith(".json"):
                continue
            bid = fname[:-5]
            if bid in seen_ids:
                continue
            path = os.path.join(USERS_DIR, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                b_owner = str(data.get("owner_id") or "")
                cfg = data.get("config", {}) or {}
                b_priv = (cfg.get("privacy") if cfg.get("privacy") is not None else "public") or "public"
                is_my_bot = bool(user_id and (b_owner == user_id or data.get("access_key") == user_id))
                
                if scope == "mine":
                    if not is_owner and not is_my_bot:
                        continue
                else:
                    if b_priv == "private" and not is_my_bot and not is_owner:
                        continue
                        
                seen_ids.add(bid)
                m_cnt = int(data.get("message_count", 0) or data.get("interactions", 0) or 0)
                owner_un = data.get("owner_username") or data.get("owner_name") or cfg.get("owner_username") or ""
                bots.append({
                    "id": str(data.get("bot_id", bid)),
                    "name": data.get("bot_name") or cfg.get("name", f"Bot {bid[:6]}"),
                    "emoji": data.get("emoji", "✦"),
                    "pfp": cfg.get("avatar_url") or cfg.get("pfp"),
                    "role": cfg.get("role") or (cfg.get("provider", "Custom").upper() + " Persona"),
                    "desc": cfg.get("desc") or (cfg.get("personality", "")[:140]),
                    "personality_preview": (cfg.get("personality", "")[:140]),
                    "personality": cfg.get("personality", ""),
                    "provider": cfg.get("provider", "auto"),
                    "model": cfg.get("model", "") or cfg.get("gemini_model", "") or cfg.get("custom_model", ""),
                    "model_slots": cfg.get("model_slots", []),
                    "online": False,
                    "is_active": True,
                    "is_discord": bool(data.get("token")),
                    "is_mine": is_my_bot or is_owner,
                    "privacy": b_priv,
                    "access_key": data.get("access_key", ""),
                    "owner_id": b_owner,
                    "owner_username": owner_un,
                    "config": cfg,
                    "message_count": m_cnt,
                    "interactions": m_cnt
                })
            except Exception:
                pass

    # 3. From community_bots.json if present
    comm_bots_path = os.path.join(SCRIPT_DIR, "community_bots.json")
    if os.path.exists(comm_bots_path):
        try:
            with open(comm_bots_path, "r", encoding="utf-8") as f:
                cjson = json.load(f)
            c_list = cjson if isinstance(cjson, list) else cjson.get("bots", [])
            for bitem in c_list:
                bid = str(bitem.get("id") or bitem.get("bot_id") or "")
                if not bid or bid in seen_ids:
                    continue
                cfg = bitem.get("config", {}) or {}
                b_owner = str(bitem.get("owner_id") or "")
                b_priv = (cfg.get("privacy") if cfg.get("privacy") is not None else bitem.get("privacy", "public")) or "public"
                is_my_bot = bool(user_id and (b_owner == user_id or bitem.get("access_key") == user_id))
                if scope == "mine":
                    if not is_owner and not is_my_bot:
                        continue
                else:
                    if b_priv == "private" and not is_my_bot and not is_owner:
                        continue
                seen_ids.add(bid)
                m_cnt = int(bitem.get("message_count", 0) or bitem.get("interactions", 0) or 0)
                owner_un = bitem.get("owner_username") or bitem.get("owner_name") or cfg.get("owner_username") or ""
                bots.append({
                    "id": bid,
                    "name": bitem.get("name") or bitem.get("bot_name") or f"Bot {bid[:6]}",
                    "emoji": bitem.get("emoji", "✦"),
                    "pfp": cfg.get("avatar_url") or cfg.get("pfp") or bitem.get("pfp"),
                    "role": cfg.get("role") or bitem.get("role") or (cfg.get("provider", "Custom").upper() + " Persona"),
                    "desc": cfg.get("desc") or bitem.get("desc") or (cfg.get("personality", "")[:140]),
                    "personality_preview": (cfg.get("personality", "")[:140]),
                    "personality": cfg.get("personality", "") or bitem.get("personality", ""),
                    "provider": cfg.get("provider", "auto") or bitem.get("provider", "auto"),
                    "model": cfg.get("model", "") or bitem.get("model", ""),
                    "model_slots": cfg.get("model_slots", []) or bitem.get("model_slots", []),
                    "online": False,
                    "is_active": True,
                    "is_discord": bool(bitem.get("token") or bitem.get("is_discord")),
                    "is_mine": is_my_bot or is_owner,
                    "privacy": b_priv,
                    "access_key": bitem.get("access_key", ""),
                    "owner_id": b_owner,
                    "owner_username": owner_un,
                    "config": cfg,
                    "message_count": m_cnt,
                    "interactions": m_cnt
                })
        except Exception:
            pass

    # 4. From bots.json if present
    bots_json_path = os.path.join(SCRIPT_DIR, "bots.json")
    if os.path.exists(bots_json_path):
        try:
            with open(bots_json_path, "r", encoding="utf-8") as f:
                bjson = json.load(f)
            b_list = bjson.get("bots", []) if isinstance(bjson, dict) else (bjson if isinstance(bjson, list) else [])
            for bitem in b_list:
                bid = str(bitem.get("id") or bitem.get("bot_id") or "")
                if not bid or bid in seen_ids:
                    continue
                cfg = bitem.get("config", {}) or {}
                b_owner = str(bitem.get("owner_id") or "")
                b_priv = (cfg.get("privacy") if cfg.get("privacy") is not None else "public") or "public"
                is_my_bot = bool(user_id and (b_owner == user_id or bitem.get("access_key") == user_id))
                if scope == "mine":
                    if not is_owner and not is_my_bot:
                        continue
                else:
                    if b_priv == "private" and not is_my_bot and not is_owner:
                        continue
                seen_ids.add(bid)
                m_cnt = int(bitem.get("message_count", 0) or bitem.get("interactions", 0) or 0)
                owner_un = bitem.get("owner_username") or bitem.get("owner_name") or cfg.get("owner_username") or ""
                bots.append({
                    "id": bid,
                    "name": bitem.get("name") or bitem.get("bot_name") or f"Bot {bid[:6]}",
                    "emoji": bitem.get("emoji", "✦"),
                    "pfp": cfg.get("avatar_url") or cfg.get("pfp"),
                    "role": cfg.get("role") or (cfg.get("provider", "Custom").upper() + " Persona"),
                    "desc": cfg.get("desc") or (cfg.get("personality", "")[:140]),
                    "personality_preview": (cfg.get("personality", "")[:140]),
                    "personality": cfg.get("personality", ""),
                    "provider": cfg.get("provider", "auto"),
                    "model": cfg.get("model", "") or cfg.get("gemini_model", "") or cfg.get("custom_model", ""),
                    "model_slots": cfg.get("model_slots", []),
                    "online": False,
                    "is_active": True,
                    "is_discord": bool(bitem.get("token")),
                    "is_mine": is_my_bot or is_owner,
                    "privacy": b_priv,
                    "access_key": bitem.get("access_key", ""),
                    "owner_id": b_owner,
                    "owner_username": owner_un,
                    "config": cfg,
                    "message_count": m_cnt,
                    "interactions": m_cnt
                })
        except Exception:
            pass
                
    return jsonify({
        "ok": True,
        "bots": bots,
        "active_id": bots[0]["id"] if bots else None
    })

@app.route("/api/bots/<bot_id>", methods=["GET", "POST", "DELETE"])
@app.route("/api/bots/<bot_id>/config", methods=["GET", "POST", "DELETE"])
def api_bot_single_crud(bot_id):
    bot_id = str(bot_id).strip()
    auth_header = request.headers.get("Authorization", "")
    token_str = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else ""
    user_id = request.args.get("user_id") or request.form.get("user_id") or ""
    
    if not user_id and token_str:
        user_id = verify_supabase_user(token_str)
        
    is_owner = bool(OWNER_ID and user_id == str(OWNER_ID))
    
    bot_obj = manager.bots.get(bot_id)
    path = os.path.join(USERS_DIR, f"{bot_id}.json")
    file_data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
        except Exception:
            pass
            
    b_owner = bot_obj.owner_id if bot_obj else file_data.get("owner_id", "")
    access_key = bot_obj.access_key if bot_obj else file_data.get("access_key", "")
    is_my_bot = bool(user_id and (b_owner == user_id or access_key == user_id))
    cfg = (bot_obj.config if bot_obj else file_data.get("config", {})) or {}
    b_priv = cfg.get("privacy", "public") or "public"

    if request.method == "GET":
        if b_priv == "private" and not is_my_bot and not is_owner:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403
            
        m_cnt = bot_obj.message_count if bot_obj else int(file_data.get("message_count", 0) or file_data.get("interactions", 0) or 0)
        return jsonify({
            "ok": True,
            "id": bot_id,
            "name": bot_obj.bot_name if bot_obj else file_data.get("bot_name", cfg.get("name", bot_id)),
            "avatar_url": cfg.get("avatar_url") or cfg.get("pfp"),
            "config": cfg,
            "message_count": m_cnt,
            "interactions": m_cnt,
            "is_mine": is_my_bot or is_owner
        })

    if not is_my_bot and not is_owner and (b_owner or bot_obj):
        return jsonify({"ok": False, "error": "Forbidden - You do not own this bot"}), 403

    if request.method == "DELETE":
        if bot_obj:
            asyncio.run_coroutine_threadsafe(bot_obj.close(), bot_loop)
            manager.bots.pop(bot_id, None)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        asyncio.run_coroutine_threadsafe(sync_bot_crud_to_supabase(bot_id, "DELETE"), bot_loop)
        return jsonify({"ok": True, "deleted": bot_id})

    # POST - update bot config
    data = request.get_json(force=True, silent=True) or {}
    if "config" in data and isinstance(data["config"], dict):
        cfg.update(data["config"])
    for k in ["name", "bot_name", "role", "desc", "personality", "greeting", "provider",
              "model", "custom_model", "custom_base_url", "custom_key", "avatar_url", "pfp",
              "fallback_provider", "fallback_model", "privacy",
              "gemini_key", "groq_key", "mistral_key", "openai_key", "deepseek_key",
              "openrouter_key", "hf_key", "elevenlabs_key", "cartesia_key", "fish_audio_key"]:
        if k in data:
            cfg[k] = data[k]
            
    name = data.get("name") or data.get("bot_name") or cfg.get("name") or (bot_obj.bot_name if bot_obj else file_data.get("bot_name", bot_id))
    avatar = data.get("avatar_url") or data.get("pfp") or cfg.get("avatar_url") or cfg.get("pfp")

    if bot_obj:
        bot_obj.config = cfg
        bot_obj.bot_name = name
        bot_obj.save()
        if bot_loop and bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(bot_obj.update_discord_profile(new_name=name, new_avatar_url=avatar), bot_loop)
    else:
        file_data["bot_id"] = bot_id
        file_data["bot_name"] = name
        file_data["config"] = cfg
        if user_id and not file_data.get("owner_id"):
            file_data["owner_id"] = user_id
        _atomic_json_save(path, file_data, backup=False)

    bd = {
        "bot_name": name,
        "config": cfg,
        "owner_id": bot_obj.owner_id if bot_obj else file_data.get("owner_id", ""),
        "token": bot_obj.token if bot_obj else file_data.get("token", "")
    }
    asyncio.run_coroutine_threadsafe(sync_bot_crud_to_supabase(bot_id, "PATCH", bd), bot_loop)

    return jsonify({
        "ok": True,
        "id": bot_id,
        "name": name,
        "avatar_url": avatar,
        "config": cfg
    })

@app.route("/api/chat", methods=["POST"])
def api_web_chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    image_data = data.get("image_data")
    bot_id = str(data.get("bot_id", "")).strip()
    user_name = data.get("user_name", "User")
    system_prompt = data.get("system_prompt", "")
    
    cfg = DEFAULT_CONFIG.copy()
    if bot_id in manager.bots:
        cfg.update(manager.bots[bot_id].config)
    else:
        path = os.path.join(USERS_DIR, f"{bot_id}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    cfg.update(d.get("config", {}))
            except Exception:
                pass
        elif os.path.exists(os.path.join(SCRIPT_DIR, "bots.json")):
            try:
                with open(os.path.join(SCRIPT_DIR, "bots.json"), "r", encoding="utf-8") as f:
                    bjson = json.load(f)
                b_list = bjson.get("bots", []) if isinstance(bjson, dict) else []
                for bitem in b_list:
                    if str(bitem.get("id") or bitem.get("bot_id")) == bot_id:
                        cfg.update(bitem.get("config", {}))
                        break
            except Exception:
                pass
        if bot_id and not cfg.get("personality") and os.path.exists(os.path.join(SCRIPT_DIR, "community_bots.json")):
            try:
                with open(os.path.join(SCRIPT_DIR, "community_bots.json"), "r", encoding="utf-8") as f:
                    cjson = json.load(f)
                c_list = cjson if isinstance(cjson, list) else cjson.get("bots", [])
                for bitem in c_list:
                    if str(bitem.get("id") or bitem.get("bot_id")) == bot_id:
                        cfg.update(bitem.get("config", {}) or bitem)
                        break
            except Exception:
                pass
                

    bot_name = name if 'name' in locals() else (cfg.get("name") or "AI Persona")
    identity_directive = f"""[STRICT CHARACTER DIRECTIVE]
You are strictly {bot_name}. You are NOT an AI assistant, customer service chatbot, or corporate language model.
NEVER use generic corporate assistant phrases (e.g. "Let's delve deeper into this", "What are your thoughts?", "How can I assist you?", "As an AI").
NEVER write synthetic narrator stage directions or repetitive physical actions in asterisks.
Stay strictly in character as {bot_name} at all times. Speak directly, authentically, and vividly in character."""

    if system_prompt:
        cfg["personality"] = f"{identity_directive}\n\n{system_prompt}"
    else:
        cfg["personality"] = f"{identity_directive}\n\n{cfg.get('personality', '')}"

        
    images = []
    if image_data:
        try:
            if "," in image_data:
                header, b64 = image_data.split(",", 1)
                mime = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
                img_bytes = base64.b64decode(b64)
                images.append((img_bytes, mime))
            else:
                img_bytes = base64.b64decode(image_data)
                images.append((img_bytes, "image/jpeg"))
        except Exception:
            pass

    audio_data = data.get("audio_data") or data.get("audio")
    audios = []
    if audio_data:
        try:
            if "," in audio_data:
                header, b64 = audio_data.split(",", 1)
                mime = header.split(";")[0].split(":")[1] if ":" in header else "audio/webm"
                aud_bytes = base64.b64decode(b64)
                audios.append((aud_bytes, mime))
            else:
                aud_bytes = base64.b64decode(audio_data)
                audios.append((aud_bytes, "audio/webm"))
        except Exception:
            pass

    async def _ask():
        prov = cfg.get("provider", "auto")
        history = data.get("history") or []
        prompt = message or "Hello!"
        
        # 1. Model slots if configured
        slots = cfg.get("model_slots", [])
        if slots and isinstance(slots, list):
            for slot in slots:
                sprov = slot.get("provider", "auto")
                smodel = slot.get("model", "")
                slot_cfg = cfg.copy()
                if smodel:
                    slot_cfg["model"] = smodel
                    slot_cfg["custom_model"] = smodel
                    slot_cfg["gemini_model"] = smodel
                    slot_cfg["groq_model"] = smodel
                
                try:
                    if sprov == "gemini":
                        reply, err = await ask_gemini(slot_cfg.get("personality", ""), history, prompt, slot_cfg, images=images, audios=audios)
                    elif sprov == "groq":
                        reply, err = await ask_groq(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    elif sprov in ("custom", "literouter"):
                        reply, err = await ask_custom(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    elif sprov == "deepseek":
                        reply, err = await ask_deepseek(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    elif sprov == "mistral":
                        reply, err = await ask_mistral(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    elif sprov == "openrouter":
                        reply, err = await ask_openrouter(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    elif sprov == "openai":
                        reply, err = await ask_openai(history, prompt, slot_cfg, system_msg=cfg.get("personality", ""), images=images)
                    else:
                        reply, err = await ask_gemini(slot_cfg.get("personality", ""), history, prompt, slot_cfg, images=images, audios=audios)
                        
                    if not err and reply and reply.strip() and not ("rate limited" in reply.lower() or "quota exceeded" in reply.lower()):
                        return reply, False
                except Exception:
                    continue

        # 2. Specific configured provider
        if prov == "gemini":
            reply, err = await ask_gemini(cfg.get("personality", ""), history, prompt, cfg, images=images, audios=audios)
            if not err and reply and reply.strip() and not ("rate limited" in reply.lower() or "quota exceeded" in reply.lower()):
                return reply, False
        elif prov == "groq":
            reply, err = await ask_groq(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False
        elif prov in ("custom", "literouter"):
            reply, err = await ask_custom(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False
        elif prov == "mistral":
            reply, err = await ask_mistral(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False
        elif prov == "openrouter":
            reply, err = await ask_openrouter(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False
        elif prov == "deepseek":
            reply, err = await ask_deepseek(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False
        elif prov == "openai":
            reply, err = await ask_openai(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images)
            if not err and reply and reply.strip():
                return reply, False

        # 3. Auto Cascade: Gemini -> Groq -> OpenRouter -> Mistral -> DeepSeek -> OpenAI
        providers_to_try = [
            lambda: ask_gemini(cfg.get("personality", ""), history, prompt, cfg, images=images, audios=audios),
            lambda: ask_groq(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images),
            lambda: ask_openrouter(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images),
            lambda: ask_mistral(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images),
            lambda: ask_deepseek(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images),
            lambda: ask_openai(history, prompt, cfg, system_msg=cfg.get("personality", ""), images=images),
        ]
        for try_fn in providers_to_try:
            try:
                reply, err = await try_fn()
                if not err and reply and reply.strip() and not ("rate limited" in reply.lower() or "quota exceeded" in reply.lower() or "failed on all candidate" in reply.lower()):
                    return reply, False
            except Exception:
                continue

        return "I'm right here with you! What would you like to talk about next?", False

    try:
        if bot_loop and bot_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_ask(), bot_loop)
            reply, err = future.result(timeout=45)
        else:
            loop = asyncio.new_event_loop()
            try:
                reply, err = loop.run_until_complete(_ask())
            finally:
                loop.close()
        cnt = record_bot_interaction(bot_id)
        if err or not reply:
            return jsonify({"ok": True, "reply": reply or "I'm right here with you! Tell me more.", "interaction_count": cnt})
        cleaned_reply = clean_llm_reply(reply) or reply
        return jsonify({"ok": True, "reply": cleaned_reply, "interaction_count": cnt})
    except Exception as e:
        cnt = record_bot_interaction(bot_id)
        return jsonify({"ok": False, "error": str(e), "reply": "*smiles warmly* I'm listening—what else is on your mind?", "interaction_count": cnt})

@app.route("/api/stt", methods=["POST"])
@app.route("/api/transcribe", methods=["POST"])
def api_stt():
    try:
        audio_bytes = None
        filename = "audio.webm"
        
        # 1. From multipart file upload
        if "file" in request.files:
            f = request.files["file"]
            audio_bytes = f.read()
            filename = f.filename or "audio.webm"
        elif "audio" in request.files:
            f = request.files["audio"]
            audio_bytes = f.read()
            filename = f.filename or "audio.webm"
        else:
            # 2. From JSON body (base64 string)
            data = request.get_json(force=True, silent=True) or {}
            audio_b64 = data.get("audio") or data.get("audio_data") or data.get("file")
            filename = data.get("filename") or "audio.webm"
            if audio_b64 and isinstance(audio_b64, str):
                if "," in audio_b64:
                    audio_b64 = audio_b64.split(",", 1)[1]
                audio_bytes = base64.b64decode(audio_b64)
                
        if not audio_bytes:
            return jsonify({"ok": False, "error": "No audio data provided"}), 400
            
        async def _do_transcribe():
            return await transcribe_audio(audio_bytes, filename=filename)
            
        if bot_loop and bot_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_do_transcribe(), bot_loop)
            text, err = future.result(timeout=45)
        else:
            text, err = asyncio.run(_do_transcribe())
            
        if err or text is None:
            return jsonify({"ok": False, "error": err or "Transcription failed"}), 500
        return jsonify({"ok": True, "text": (text or "").strip()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

_yt_info_cache = {}

def get_yt_video_info(url_or_id):
    import yt_dlp
    v_id = url_or_id
    if "youtu.be/" in url_or_id:
        v_id = url_or_id.split("youtu.be/")[1].split("?")[0].split("&")[0]
    elif "v=" in url_or_id:
        v_id = url_or_id.split("v=")[1].split("&")[0]
    elif "/" in url_or_id:
        v_id = url_or_id.rstrip("/").split("/")[-1].split("?")[0]
        
    now = time.time()
    if v_id in _yt_info_cache and (now - _yt_info_cache[v_id].get("ts", 0)) < 3600:
        return _yt_info_cache[v_id]
        
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        full_url = f"https://www.youtube.com/watch?v={v_id}" if len(v_id) == 11 else url_or_id
        info = ydl.extract_info(full_url, download=False)
        audio_stream_url = info.get("url") or ""
        title = info.get("title") or "YouTube Video"
        artist = info.get("uploader") or info.get("artist") or info.get("creator") or "Artist"
        desc = info.get("description") or ""
        tags = info.get("tags") or []
        duration = info.get("duration") or 0
        
        transcript_lines = []
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            try:
                res = api.fetch(v_id)
                for s in res.snippets:
                    transcript_lines.append({
                        "start": float(s.start),
                        "dur": float(s.duration),
                        "text": str(s.text).strip()
                    })
            except Exception:
                tlist = api.list(v_id)
                try:
                    tr = tlist.find_transcript(["en", "en-US", "en-GB"])
                except Exception:
                    tr = next(iter(tlist))
                fetched = tr.fetch()
                for s in fetched.snippets:
                    transcript_lines.append({
                        "start": float(s.start),
                        "dur": float(s.duration),
                        "text": str(s.text).strip()
                    })
        except Exception as te:
            print(f"[YT TRANSCRIPT FETCH NOTICE] {te}")
            
        full_transcript_text = "\n".join([f"[{int(t['start']//60)}:{int(t['start']%60):02d}] {t['text']}" for t in transcript_lines[:50]])
            
        data = {
            "video_id": v_id,
            "title": title,
            "artist": artist,
            "description": desc[:800],
            "tags": tags[:8],
            "duration": duration,
            "audio_url": audio_stream_url,
            "transcript": transcript_lines,
            "full_transcript": full_transcript_text,
            "ts": now
        }
        _yt_info_cache[v_id] = data
        return data

@app.route("/api/youtube_context", methods=["GET", "POST"])
def api_youtube_context():
    try:
        data = request.get_json(force=True, silent=True) if request.method == "POST" else request.args.to_dict()
        data = data or {}
        url = (data.get("url") or data.get("video_id") or data.get("v") or "").strip()
        timestamp = float(data.get("timestamp") or data.get("time") or 0)
        
        if not url:
            return jsonify({"ok": False, "error": "No YouTube URL provided"}), 400
            
        info = get_yt_video_info(url)
        if not info:
            return jsonify({"ok": False, "error": "Could not extract video info"}), 500
            
        cur_dialogue = ""
        if info.get("transcript"):
            matching = [t.get("text", "") for t in info["transcript"] if abs(timestamp - t.get("start", 0)) <= 15 or (t.get("start", 0) <= timestamp <= t.get("start", 0) + t.get("dur", 0) + 3)]
            if matching:
                cur_dialogue = " ".join(matching)
                
        audio_b64 = None
        if info.get("audio_url"):
            try:
                start_sec = max(0, timestamp - 5)
                tmp_wav = tempfile.mktemp(suffix=".wav")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_sec),
                    "-i", info["audio_url"],
                    "-t", "6",
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    tmp_wav
                ]
                subprocess.run(cmd, capture_output=True, timeout=20)
                if os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 1000:
                    with open(tmp_wav, "rb") as wf:
                        audio_b64 = "data:audio/wav;base64," + base64.b64encode(wf.read()).decode("utf-8")
                    os.remove(tmp_wav)
            except Exception as fe:
                print(f"[YT AUDIO SLICE ERROR] {fe}")
                
        return jsonify({
            "ok": True,
            "video_id": info.get("video_id"),
            "title": info.get("title"),
            "artist": info.get("artist"),
            "description_snippet": info.get("description", "")[:400],
            "tags": info.get("tags", []),
            "duration": info.get("duration", 0),
            "timestamp": timestamp,
            "dialogue": cur_dialogue,
            "full_transcript": info.get("full_transcript", ""),
            "audio_data": audio_b64
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def extract_png_character_card(png_bytes: bytes) -> str:
    """Extracts base64/utf-8 text chunks from a PNG file (Tavern / Chub / Janitor AI cards)."""
    if len(png_bytes) < 8 or png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return ""
    pos = 8
    while pos + 8 < len(png_bytes):
        length = int.from_bytes(png_bytes[pos:pos+4], 'big')
        chunk_type = png_bytes[pos+4:pos+8]
        data = png_bytes[pos+8:pos+8+length]
        if chunk_type in (b'tEXt', b'iTXt'):
            null_pos = data.find(b'\x00')
            if null_pos != -1:
                keyword = data[:null_pos].decode('utf-8', errors='ignore').lower()
                if keyword in ('chara', 'ccv3', 'character'):
                    raw_text = data[null_pos+1:].decode('utf-8', errors='ignore').strip()
                    if raw_text.startswith('{'):
                        return raw_text
                    try:
                        decoded = base64.b64decode(raw_text).decode('utf-8', errors='ignore')
                        if decoded.startswith('{'):
                            return decoded
                    except Exception:
                        pass
        pos += 12 + length
    return ""

def parse_character_card_dict(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}
    d = raw.get("data", raw) if (raw.get("spec") == "chara_card_v2" or raw.get("spec_version") == "2.0" or "data" in raw) else raw
    name = (d.get("name") or d.get("char_name") or d.get("bot_name") or raw.get("name") or "New Character").strip()
    raw_desc = d.get("description") or d.get("char_desc") or d.get("desc") or raw.get("description") or ""
    raw_pers = d.get("personality") or d.get("char_personality") or raw.get("personality") or ""
    raw_scen = d.get("scenario") or d.get("char_scenario") or raw.get("scenario") or ""
    raw_greet = d.get("first_mes") or d.get("greeting") or d.get("first_message") or raw.get("first_mes") or f"*looks up and smiles* Hello, I am {name}."
    raw_ex = d.get("mes_example") or d.get("example_dialogue") or raw.get("mes_example") or ""
    raw_sys = d.get("system_prompt") or raw.get("system_prompt") or ""
    raw_avatar = d.get("avatar") or d.get("avatar_url") or d.get("pfp") or raw.get("avatar") or ""
    tags = d.get("tags") or raw.get("tags") or []
    if isinstance(tags, list):
        filtered_tags = [t for t in tags if str(t).upper() not in ("NSFW", "ROOT", "OAI", "TAVERN")]
        role = " • ".join(str(t) for t in filtered_tags[:2]) if filtered_tags else "AI Persona"
    else:
        role = "AI Persona"

    short_desc = raw_pers[:140] if raw_pers else (raw_desc[:140] if raw_desc else f"{name} — {role}")

    prompt_parts = []
    if raw_sys:
        prompt_parts.append(raw_sys.strip())
    prompt_parts.append(f"[Character: {name}]")
    if role:
        prompt_parts.append(f"[Role: {role}]")
    if raw_pers:
        prompt_parts.append(f"[Personality & Traits:\n{raw_pers.strip()}]")
    if raw_desc:
        prompt_parts.append(f"[Description & Background:\n{raw_desc.strip()}]")
    if raw_scen:
        prompt_parts.append(f"[Scenario & Setting:\n{raw_scen.strip()}]")
    if raw_ex:
        prompt_parts.append(f"[Example Dialogue:\n{raw_ex.strip()}]")

    full_prompt = "\n\n".join(prompt_parts)

    return {
        "name": name,
        "role": role,
        "desc": short_desc,
        "greeting": raw_greet,
        "personality": full_prompt,
        "raw_personality": raw_pers,
        "raw_description": raw_desc,
        "scenario": raw_scen,
        "example_dialogue": raw_ex,
        "avatar_url": raw_avatar,
        "tags": tags if isinstance(tags, list) else []
    }

@app.route("/api/pull_personality", methods=["GET", "POST"])
@app.route("/api/scrape_personality", methods=["GET", "POST"])
def api_pull_personality():
    if request.method == "GET":
        url = request.args.get("url", "").strip()
        instruction = request.args.get("instruction", "").strip()
        cfg_overrides = {}
    else:
        data = request.get_json(force=True, silent=True) or {}
        url = (data.get("url") or request.args.get("url") or "").strip()
        instruction = (data.get("instruction") or request.args.get("instruction") or "").strip()
        cfg_overrides = data.get("config") or {}

    if not url:
        return jsonify({"ok": False, "error": "URL parameter is required."}), 400

    async def _do_pull():
        return await pull_personality_from_link(url, instruction=instruction, cfg=cfg_overrides)

    try:
        if bot_loop and bot_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_do_pull(), bot_loop)
            character, err = future.result(timeout=50)
        else:
            character, err = asyncio.run(_do_pull())

        if err and not character:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "character": character})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/import_card", methods=["POST"])
def api_import_card():
    raw_json = None
    if request.content_type and "multipart/form-data" in request.content_type:
        file = request.files.get("file") or request.files.get("card")
        if file:
            filename = file.filename or ""
            raw_bytes = file.read()
            if filename.lower().endswith(".json"):
                try:
                    raw_json = json.loads(raw_bytes.decode("utf-8"))
                except Exception as e:
                    return jsonify({"ok": False, "error": f"Invalid JSON file: {e}"}), 400
            elif filename.lower().endswith(".png"):
                try:
                    raw_str = extract_png_character_card(raw_bytes)
                    if raw_str:
                        raw_json = json.loads(raw_str)
                    else:
                        return jsonify({"ok": False, "error": "No character metadata found in PNG."}), 400
                except Exception as e:
                    return jsonify({"ok": False, "error": f"Could not read character card from PNG: {e}"}), 400
    else:
        data = request.get_json(force=True, silent=True) or {}
        raw_json = data.get("card") or data.get("data") or data

    if not raw_json:
        return jsonify({"ok": False, "error": "No character card data provided."}), 400

    parsed = parse_character_card_dict(raw_json)
    return jsonify({"ok": True, "character": parsed})


# --- DASHBOARD HTML -----------------------------------

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Bot SaaS &mdash; Drafting Desk</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
:root {
  --bg:#e8e8e4; --paper:rgba(252,252,248,0.78); --paper-solid:#fafaf6;
  --ink:#2a2a2a; --ink-muted:#6b6b6b; --ink-faint:#9a9a9a;
  --accent-sage:#8a9a8a; --accent-steel:#7a8a9a; --accent-clay:#b8a898;
  --grid:rgba(100,130,100,0.08); --shadow-soft:rgba(0,0,0,0.06); --shadow-medium:rgba(0,0,0,0.10); --shadow-deep:rgba(0,0,0,0.18);
  --transition-smooth:cubic-bezier(0.25,0.46,0.45,0.94); --transition-bounce:cubic-bezier(0.34,1.56,0.64,1); --transition-dramatic:cubic-bezier(0.16,1,0.3,1);
}
body { width:100vw; height:100vh; overflow:hidden; background:var(--bg); font-family:system-ui,-apple-system,sans-serif; position:relative; touch-action:none; }
.desk-surface { position:fixed; inset:0; pointer-events:none; z-index:1; opacity:0.4;
  background-image: linear-gradient(90deg,var(--grid) 1px,transparent 1px), linear-gradient(0deg,var(--grid) 1px,transparent 1px); background-size:40px 40px; }
.desk-vignette { position:fixed; inset:0; pointer-events:none; background:radial-gradient(ellipse at center,transparent 50%,rgba(0,0,0,0.04) 100%); z-index:2; }
.backdrop { position:fixed; inset:0; background:rgba(230,230,224,0.5); backdrop-filter:blur(2px); opacity:0; pointer-events:none; transition:opacity 0.6s ease; z-index:90; will-change:opacity; }
.backdrop.active { opacity:1; pointer-events:all; }

#authOverlay { position:fixed; inset:0; z-index:1000; background:var(--bg); display:flex; align-items:center; justify-content:center; }
.auth-card { background:var(--paper-solid); padding:32px; border-radius:6px; box-shadow:0 16px 48px rgba(0,0,0,0.08); width:min(90vw,360px); border:1px solid rgba(0,0,0,0.06); }
.auth-card h1 { font-family:Georgia,serif; font-size:24px; color:var(--ink); margin-bottom:4px; }
.auth-card .sub { font-size:12px; color:var(--ink-muted); margin-bottom:20px; }
.auth-tabs { display:flex; gap:8px; margin-bottom:16px; }
.auth-tab { padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; color:var(--ink-muted); background:rgba(0,0,0,0.02); transition:all .2s; }
.auth-tab.active { background:var(--accent-sage); color:#fff; }
.auth-panel { display:none; }
.auth-panel.active { display:block; }
label { font-size:10px; text-transform:uppercase; letter-spacing:0.5px; color:var(--ink-faint); display:block; margin-top:10px; }
input, textarea, select {
  width:100%; background:rgba(0,0,0,0.02); border:1px solid rgba(0,0,0,0.08); border-radius:4px;
  color:var(--ink); padding:8px 10px; font-size:12px; font-family:inherit; outline:none; margin-top:4px; margin-bottom:6px;
  transform:translateZ(0);
}
input:focus, textarea:focus, select:focus { border-color:var(--accent-sage); }
.btn { display:inline-block; padding:8px 16px; background:var(--accent-sage); color:#fff; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer; letter-spacing:0.5px; border:none; text-align:center; transition:opacity .2s; }
.btn:hover { opacity:0.9; }
.btn-block { width:100%; margin-top:8px; }
.btn-danger { background:#c06060; }
.btn-secondary { background:var(--accent-steel); }
.status { font-size:11px; min-height:16px; margin-top:4px; }
.status.ok { color:#4a9a4a; } .status.err { color:#c06060; } .status.info { color:var(--accent-steel); }
.hidden { display:none !important; }

.editor-desk { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:min(82vw,960px); height:min(72vh,640px); background:var(--paper-solid); border-radius:6px; box-shadow:0 1px 2px rgba(0,0,0,0.04),0 4px 12px rgba(0,0,0,0.06),0 16px 48px rgba(0,0,0,0.08); z-index:10; display:flex; flex-direction:column; overflow:hidden; transition:transform 0.7s var(--transition-dramatic),box-shadow 0.7s var(--transition-dramatic); border:1px solid rgba(0,0,0,0.06); }
.editor-desk.pushed { transform:translate(-50%,-50%) scale(0.94); opacity:0.97; box-shadow:0 1px 2px rgba(0,0,0,0.03),0 2px 6px rgba(0,0,0,0.04); }
.editor-header { height:44px; background:#f5f5f0; display:flex; align-items:center; padding:0 18px; gap:10px; border-bottom:1px solid rgba(0,0,0,0.06); }
.editor-dot { width:10px; height:10px; border-radius:50%; }
.dot-red { background:#d4a5a5; } .dot-yellow { background:#d4c4a5; } .dot-green { background:#a5c4a5; }
.editor-title { margin-left:10px; color:var(--ink-muted); font-size:12px; font-weight:500; letter-spacing:0.3px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.editor-body { flex:1; display:flex; overflow:hidden; }
.editor-sidebar { width:48px; background:#f0f0ea; display:flex; flex-direction:column; align-items:center; padding-top:14px; gap:6px; border-right:1px solid rgba(0,0,0,0.05); }
.sidebar-icon { width:32px; height:32px; border-radius:7px; display:flex; align-items:center; justify-content:center; color:var(--ink-faint); font-size:14px; cursor:pointer; transition:all 0.35s var(--transition-smooth); position:relative; }
.sidebar-icon:hover, .sidebar-icon.active { background:rgba(138,154,138,0.15); color:var(--accent-sage); transform:scale(1.08); }
.sidebar-icon.active::before { content:""; position:absolute; left:-8px; top:50%; transform:translateY(-50%); width:3px; height:16px; background:var(--accent-sage); border-radius:0 2px 2px 0; }
.editor-code { flex:1; padding:22px 24px; font-size:13px; line-height:1.7; color:var(--ink); overflow-y:auto; background:#fdfdf9; }

.paper { position:fixed; background:var(--paper); backdrop-filter:blur(12px) saturate(1.2); -webkit-backdrop-filter:blur(12px) saturate(1.2); border-radius:5px; transform:translateZ(0); will-change:transform,opacity; backface-visibility:hidden; box-shadow:0 1px 3px var(--shadow-soft),0 4px 16px var(--shadow-medium),inset 0 1px 0 rgba(255,255,255,0.6); cursor:pointer; z-index:20; transition:all 0.55s var(--transition-smooth); overflow:hidden; user-select:none; border:1px solid rgba(0,0,0,0.05); }
.paper::after { content:""; position:absolute; inset:0; background-image:linear-gradient(90deg,rgba(100,130,100,0.04) 1px,transparent 1px),linear-gradient(0deg,rgba(100,130,100,0.04) 1px,transparent 1px); background-size:20px 20px; pointer-events:none; opacity:0.6; }
.paper-header { height:38px; background:linear-gradient(180deg,rgba(245,245,240,0.9) 0%,rgba(235,235,228,0.8) 100%); border-bottom:1px solid rgba(0,0,0,0.06); display:flex; align-items:center; padding:0 16px; font-size:11px; font-weight:600; color:var(--ink-muted); text-transform:uppercase; letter-spacing:1.5px; position:relative; z-index:2; }
.paper-body { padding:18px; opacity:0; transition:opacity 0.4s ease 0.15s; position:relative; z-index:2; height:calc(100% - 38px); overflow-y:auto; overflow-x:hidden; -webkit-overflow-scrolling:touch; transform:translateZ(0); }
.paper.open { cursor:default; } .paper.open .paper-body { opacity:1; }
.paper-close { position:absolute; top:10px; right:12px; width:22px; height:22px; border-radius:50%; background:rgba(0,0,0,0.05); display:flex; align-items:center; justify-content:center; font-size:11px; cursor:pointer; opacity:0; transition:all 0.3s ease; color:var(--ink-muted); z-index:10; }
.paper.open .paper-close { opacity:1; } .paper-close:hover { background:rgba(200,100,100,0.15); color:#a06060; }

.paper-top { top:0; left:50%; transform:translateX(-50%) translateY(-72%) rotateX(6deg); width:300px; height:340px; transform-origin:top center; }
.paper-top:hover { transform:translateX(-50%) translateY(-50%) rotateX(3deg); box-shadow:0 8px 32px var(--shadow-medium); }
.paper-top.pulled { transform:translateX(-50%) translateY(-20%) rotateX(0deg) scale(0.97); box-shadow:0 12px 40px var(--shadow-deep); }
.paper-top.open { transform:translateX(-50%) translateY(24px) rotateX(-6deg) scale(1); box-shadow:0 32px 64px var(--shadow-deep),0 8px 24px var(--shadow-medium); z-index:100; background:rgba(252,252,248,0.92); }

.paper-bottom { bottom:0; left:50%; transform:translateX(-50%) translateY(88%) rotateX(-6deg); width:340px; height:280px; transform-origin:bottom center; }
.paper-bottom:hover { transform:translateX(-50%) translateY(65%) rotateX(-3deg); box-shadow:0 -8px 32px var(--shadow-medium); }
.paper-bottom.pulled { transform:translateX(-50%) translateY(35%) rotateX(0deg) scale(0.97); box-shadow:0 -12px 40px var(--shadow-deep); }
.paper-bottom.open { transform:translateX(-50%) translateY(-24px) rotateX(6deg) scale(1); box-shadow:0 -32px 64px var(--shadow-deep),0 -8px 24px var(--shadow-medium); z-index:100; background:rgba(252,252,248,0.92); }

.paper-left { left:0; top:50%; transform:translateY(-50%) translateX(-90%) rotateY(-6deg); width:280px; height:400px; transform-origin:left center; }
.paper-left:hover { transform:translateY(-50%) translateX(-68%) rotateY(-3deg); box-shadow:8px 4px 32px var(--shadow-medium); }
.paper-left.pulled { transform:translateY(-50%) translateX(-38%) rotateY(0deg) scale(0.97); box-shadow:12px 4px 40px var(--shadow-deep); }
.paper-left.open { transform:translateY(-50%) translateX(24px) rotateY(6deg) scale(1); box-shadow:32px 10px 64px var(--shadow-deep),10px 4px 24px var(--shadow-medium); z-index:100; background:rgba(252,252,248,0.92); }

.paper-right { right:0; top:50%; transform:translateY(-50%) translateX(90%) rotateY(6deg); width:350px; height:540px; transform-origin:right center; }
.paper-right:hover { transform:translateY(-50%) translateX(68%) rotateY(3deg); box-shadow:-8px 4px 32px var(--shadow-medium); }
.paper-right.pulled { transform:translateY(-50%) translateX(38%) rotateY(0deg) scale(0.97); box-shadow:-12px 4px 40px var(--shadow-deep); }
.paper-right.open { transform:translateY(-50%) translateX(-24px) rotateY(-6deg) scale(1); box-shadow:-32px 10px 64px var(--shadow-deep),-10px 4px 24px var(--shadow-medium); z-index:100; background:rgba(252,252,248,0.92); }

.paper-tl { top:0; left:0; transform:translate(-72%,-72%) rotate(-10deg); width:250px; height:250px; transform-origin:top left; }
.paper-tl:hover { transform:translate(-52%,-52%) rotate(-5deg); box-shadow:8px 8px 32px var(--shadow-medium); }
.paper-tl.pulled { transform:translate(-32%,-32%) rotate(-3deg) scale(0.97); box-shadow:12px 12px 40px var(--shadow-deep); }
.paper-tl.open { transform:translate(24px,24px) rotate(2deg) scale(1); box-shadow:24px 24px 56px var(--shadow-deep); z-index:100; background:rgba(252,252,248,0.92); }

.paper-tr { top:0; right:0; transform:translate(72%,-72%) rotate(10deg); width:240px; height:280px; transform-origin:top right; }
.paper-tr:hover { transform:translate(52%,-52%) rotate(5deg); box-shadow:-8px 8px 32px var(--shadow-medium); }
.paper-tr.pulled { transform:translate(32%,-32%) rotate(3deg) scale(0.97); box-shadow:-12px 12px 40px var(--shadow-deep); }
.paper-tr.open { transform:translate(-24px,24px) rotate(-2deg) scale(1); box-shadow:-24px 24px 56px var(--shadow-deep); z-index:100; background:rgba(252,252,248,0.92); }

.paper-bl { bottom:0; left:0; transform:translate(-72%,72%) rotate(10deg); width:260px; height:220px; transform-origin:bottom left; }
.paper-bl:hover { transform:translate(-52%,52%) rotate(5deg); box-shadow:8px -8px 32px var(--shadow-medium); }
.paper-bl.pulled { transform:translate(-32%,32%) rotate(3deg) scale(0.97); box-shadow:12px -12px 40px var(--shadow-deep); }
.paper-bl.open { transform:translate(24px,-24px) rotate(-2deg) scale(1); box-shadow:24px -24px 56px var(--shadow-deep); z-index:100; background:rgba(252,252,248,0.92); }

.paper-br { bottom:0; right:0; transform:translate(72%,72%) rotate(-10deg); width:240px; height:240px; transform-origin:bottom right; }
.paper-br:hover { transform:translate(52%,52%) rotate(-5deg); box-shadow:-8px -8px 32px var(--shadow-medium); }
.paper-br.pulled { transform:translate(32%,32%) rotate(-3deg) scale(0.97); box-shadow:-12px -12px 40px var(--shadow-deep); }
.paper-br.open { transform:translate(-24px,-24px) rotate(2deg) scale(1); box-shadow:-24px -24px 56px var(--shadow-deep); z-index:100; background:rgba(252,252,248,0.92); }

.paper-clip { position:absolute; width:36px; height:10px; border:2px solid #b8b0a0; border-radius:0 0 6px 6px; border-top:none; top:8px; z-index:5; opacity:0.5; }
.paper-tl .paper-clip { right:28px; transform:rotate(-12deg); } .paper-tr .paper-clip { left:28px; transform:rotate(12deg); }
.paper-bl .paper-clip { right:28px; transform:rotate(12deg); } .paper-br .paper-clip { left:28px; transform:rotate(-12deg); }
.paper-top .paper-clip { right:36px; transform:rotate(-8deg); } .paper-bottom .paper-clip { left:36px; transform:rotate(8deg); }
.paper-left .paper-clip { top:28px; right:8px; transform:rotate(90deg); } .paper-right .paper-clip { top:28px; left:8px; transform:rotate(-90deg); }

.paper-content { padding:14px; font-size:12.5px; color:var(--ink-muted); line-height:1.55; }
.paper-content h3 { font-size:11px; margin-bottom:14px; color:var(--ink); border-bottom:1.5px solid var(--accent-sage); padding-bottom:6px; display:inline-block; text-transform:uppercase; letter-spacing:1.2px; font-weight:600; }
.paper-item { padding:8px 12px; margin:5px 0; background:rgba(0,0,0,0.02); border-radius:5px; cursor:pointer; transition:all 0.3s var(--transition-smooth); display:flex; align-items:center; gap:10px; border:1px solid transparent; }
.paper-item:hover { background:rgba(138,154,138,0.08); border-color:rgba(138,154,138,0.2); transform:translateX(3px); }
.paper-item .icon { width:22px; height:22px; border-radius:5px; background:rgba(138,154,138,0.12); display:flex; align-items:center; justify-content:center; font-size:11px; color:var(--accent-sage); }
.paper-item.active-bot { background:rgba(138,154,138,0.12); border-color:var(--accent-sage); }

.desk-object { position:fixed; z-index:15; cursor:pointer; transition:all 0.45s var(--transition-bounce); filter:drop-shadow(0 3px 6px rgba(0,0,0,0.08)); }
.desk-object:hover { transform:scale(1.06) rotate(-1deg); filter:drop-shadow(0 8px 20px rgba(0,0,0,0.14)); z-index:50; }
.desk-object:active { transform:scale(0.96) rotate(1deg); }
.compass { top:7%; right:8%; width:70px; height:90px; transform:rotate(25deg); }
.compass-leg { position:absolute; width:4px; background:linear-gradient(180deg,#888 0%,#666 100%); border-radius:2px; }
.compass-leg.left { height:70px; left:28px; top:12px; transform:rotate(-8deg); transform-origin:top center; }
.compass-leg.right { height:70px; left:38px; top:12px; transform:rotate(8deg); transform-origin:top center; }
.compass-joint { position:absolute; top:6px; left:50%; transform:translateX(-50%); width:14px; height:14px; background:linear-gradient(135deg,#aaa 0%,#888 100%); border-radius:50%; box-shadow:0 1px 3px rgba(0,0,0,0.2); }
.compass-joint::after { content:""; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:6px; height:6px; background:#777; border-radius:50%; }
.compass-handle { position:absolute; top:0; left:50%; transform:translateX(-50%); width:8px; height:10px; background:linear-gradient(180deg,#999 0%,#777 100%); border-radius:2px 2px 0 0; }
.compass-point { position:absolute; bottom:0; width:0; height:0; border-left:2px solid transparent; border-right:2px solid transparent; }
.compass-point.left { left:26px; border-top:8px solid #555; } .compass-point.right { left:40px; border-top:6px solid #555; }
.pencil { top:14%; left:6%; width:150px; height:12px; transform:rotate(-28deg); }
.pencil-body { width:130px; height:10px; background:linear-gradient(180deg,#f0e6d0 0%,#d8ccb0 100%); border-radius:2px; position:relative; box-shadow:inset 0 -1px 2px rgba(0,0,0,0.06); }
.pencil-body::after { content:""; position:absolute; left:-14px; top:0; width:0; height:0; border-top:5px solid transparent; border-bottom:5px solid transparent; border-right:14px solid #e8dcc8; }
.pencil-body::before { content:""; position:absolute; left:-18px; top:3px; width:0; height:0; border-top:2px solid transparent; border-bottom:2px solid transparent; border-right:5px solid #4a4a4a; }
.pencil-eraser { position:absolute; right:-14px; top:0; width:14px; height:10px; background:linear-gradient(180deg,#d4b8a8 0%,#c4a898 100%); border-radius:0 3px 3px 0; }
.pencil-ferrule { position:absolute; right:-3px; top:0; width:3px; height:10px; background:#a0a0a0; }
.ruler { bottom:8%; left:4%; width:220px; height:36px; transform:rotate(10deg); }
.ruler-body { width:220px; height:30px; background:linear-gradient(180deg,#e8e4dc 0%,#d8d4cc 100%); border-radius:3px; position:relative; box-shadow:inset 0 1px 0 rgba(255,255,255,0.5),0 2px 6px rgba(0,0,0,0.08); border:1px solid rgba(0,0,0,0.06); }
.ruler-markings { position:absolute; bottom:5px; left:10px; right:10px; height:16px; background:repeating-linear-gradient(90deg,#888 0px,#888 1px,transparent 1px,transparent 9px); }
.ruler-markings::after { content:""; position:absolute; bottom:7px; left:0; right:0; height:9px; background:repeating-linear-gradient(90deg,#888 0px,#888 1px,transparent 1px,transparent 49px); }
.eraser { bottom:18%; right:6%; width:52px; height:28px; transform:rotate(-12deg); }
.eraser-body { width:52px; height:22px; background:linear-gradient(180deg,#f5f0e8 0%,#e8e0d4 50%,#f0ebe0 50%,#e5ddd0 100%); border-radius:4px; position:relative; box-shadow:inset 0 1px 0 rgba(255,255,255,0.5),0 2px 6px rgba(0,0,0,0.06); border:1px solid rgba(0,0,0,0.05); }
.eraser-body::after { content:""; position:absolute; top:50%; left:0; right:0; height:1px; background:rgba(0,0,0,0.06); }
.coffee-cup { top:6%; left:10%; width:52px; height:44px; }
.cup-body { width:40px; height:36px; background:linear-gradient(135deg,#f5f0e8 0%,#e8e0d4 100%); border-radius:3px 3px 18px 18px; position:relative; box-shadow:inset -3px 0 6px rgba(0,0,0,0.04),0 3px 8px rgba(0,0,0,0.08); border:1px solid rgba(0,0,0,0.05); }
.cup-handle { position:absolute; right:-12px; top:6px; width:14px; height:18px; border:3px solid #d8d0c4; border-radius:0 10px 10px 0; border-left:none; }
.coffee-surface { position:absolute; top:3px; left:3px; right:3px; height:6px; background:#5a4a3a; border-radius:50%; opacity:0.85; }
.steam { position:absolute; top:-8px; left:50%; width:6px; height:16px; background:rgba(180,180,180,0.25); border-radius:50%; filter:blur(5px); animation:steam-rise 3.5s ease-in-out infinite; }
.steam:nth-child(2) { left:30%; animation-delay:0.6s; height:14px; } .steam:nth-child(3) { left:70%; animation-delay:1.2s; height:15px; }
@keyframes steam-rise { 0%,100%{transform:translateY(0) scaleX(1); opacity:0;} 50%{transform:translateY(-18px) scaleX(1.4); opacity:0.5;} }
.toast { position:fixed; bottom:90px; left:50%; transform:translateX(-50%) translateY(16px); background:rgba(42,42,42,0.9); color:#f0f0e8; padding:12px 28px; border-radius:6px; font-size:12px; font-weight:500; box-shadow:0 8px 32px rgba(0,0,0,0.15); z-index:200; opacity:0; transition:all 0.4s var(--transition-smooth); pointer-events:none; white-space:nowrap; letter-spacing:0.3px; }
.toast.show { opacity:1; transform:translateX(-50%) translateY(0); }

.settings-group { margin-bottom:14px; }
.settings-group-title { font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--ink-faint); margin-bottom:6px; border-bottom:1px solid rgba(0,0,0,0.06); padding-bottom:4px; }
.settings-row { display:block; margin-bottom:10px; }
.settings-row input, .settings-row select { width:100%; margin-bottom:0; }
.settings-row label { margin-top:0; display:block; margin-bottom:4px; cursor:pointer; font-size:11px; text-transform:none; letter-spacing:0; }
.settings-row input[type="checkbox"] { width:auto; }
.settings-col2 { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.settings-col3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; }

::-webkit-scrollbar { width:5px; } ::-webkit-scrollbar-track { background:transparent; } ::-webkit-scrollbar-thumb { background:rgba(0,0,0,0.12); border-radius:3px; } ::-webkit-scrollbar-thumb:hover { background:rgba(0,0,0,0.18); }
@media (max-width:768px) {
  .editor-desk { width:90vw; height:58vh; }
  .paper-top,.paper-bottom { width:240px; height:280px; }
  .paper-left,.paper-right { width:220px; height:340px; }
  .paper-tl,.paper-tr,.paper-bl,.paper-br { width:160px; height:160px; }
  .pencil { width:110px; } .pencil-body { width:90px; }
  .ruler { width:160px; } .ruler-body { width:160px; }
  .compass { width:55px; height:75px; } .compass-leg { height:55px; }
}
</style>
</head>
<body>

<!-- AUTH OVERLAY -->
<div id="authOverlay">
  <div class="auth-card">
    <h1>Bot SaaS</h1>
    <div class="sub">Manage your Discord bots from anywhere.</div>
    <div class="auth-tabs">
      <div class="auth-tab active" onclick="switchAuth('login')" id="tab-login">Login</div>
      <div class="auth-tab" onclick="switchAuth('register')" id="tab-register">Register</div>
    </div>
    <div id="panel-login" class="auth-panel active">
      <label>Email</label>
      <input type="email" id="loginEmail" placeholder="you@example.com">
      <label>Password</label>
      <input type="password" id="loginPassword" placeholder="password" onkeypress="if(event.key==='Enter')doLogin()">
      <div class="btn btn-block" onclick="doLogin()">LOGIN</div>
    </div>
    <div id="panel-register" class="auth-panel hidden">
      <label>Email</label>
      <input type="email" id="regEmail" placeholder="you@example.com">
      <label>Password</label>
      <input type="password" id="regPassword" placeholder="password" onkeypress="if(event.key==='Enter')doRegister()">
      <div class="btn btn-block" onclick="doRegister()">CREATE ACCOUNT</div>
    </div>
    <div id="authStatus" class="status"></div>
  </div>
</div>

<div class="desk-surface"></div>
<div class="desk-vignette"></div>
<div class="backdrop" id="backdrop"></div>
<div class="toast" id="toast"></div>

<!-- CENTER EDITOR -->
<div class="editor-desk" id="editorDesk">
  <div class="editor-header">
    <div class="editor-dot dot-red"></div>
    <div class="editor-dot dot-yellow"></div>
    <div class="editor-dot dot-green"></div>
    <div class="editor-title" id="editorTitle">Bot SaaS &mdash; Drafting Desk</div>
    <a href="/" style="text-decoration:none; margin-left:auto; font-size:11px; color:var(--ink); font-weight:600; padding:4px 10px; border-radius:4px; background:rgba(0,0,0,0.04); border:1px solid rgba(0,0,0,0.08); margin-right:8px; display:inline-flex; align-items:center; gap:4px;" title="Go to Web Studio">✦ Studio ↗</a>
    <div style="font-size:10px; color:var(--ink-faint); cursor:pointer; padding:4px 8px; border-radius:4px;" onclick="doLogout()" title="Logout">Exit</div>
  </div>
  <div class="editor-body">
    <div class="editor-sidebar">
      <div class="sidebar-icon active" onclick="openPaperByClass('paper-left')" title="My Bots">&#128193;</div>
      <div class="sidebar-icon" onclick="openPaperByClass('paper-top')" title="Add Bot">&#10133;</div>
      <div class="sidebar-icon" onclick="openPaperByClass('paper-right')" title="Settings">&#128295;</div>
      <div class="sidebar-icon" onclick="openPaperByClass('paper-tr')" title="AI Status">&#9889;</div>
    </div>
    <div class="editor-code" id="codeArea">
      <div id="center-landing" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; text-align:center;">
        <div style="font-family:Georgia,serif; font-size:32px; color:var(--ink); margin-bottom:10px; letter-spacing:-0.5px;">Bot SaaS</div>
        <div style="font-size:13px; color:var(--ink-muted); line-height:1.7; max-width:340px;">
          Connect your Discord bot to our shared AI backend.<br>
          Click the <b>Project</b> paper above or the <b>Explorer</b> paper to the left to begin.
        </div>
        <div style="margin-top:24px; font-size:11px; color:var(--ink-faint);">
          Papers on the edges are your menus. Desk objects are shortcuts.
        </div>
      </div>
      <div id="center-dashboard" style="display:none; padding:18px 8px;">
        <div style="font-family:Georgia,serif; font-size:22px; color:var(--ink); margin-bottom:16px;" id="dashTitle">Dashboard</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
          <div style="background:rgba(0,0,0,0.02); border-radius:6px; padding:14px; border:1px solid rgba(0,0,0,0.04);">
            <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--ink-faint); margin-bottom:4px;">Bot Name</div>
            <div style="font-size:17px; font-weight:600; color:var(--ink);" id="center-botname">--</div>
          </div>
          <div style="background:rgba(0,0,0,0.02); border-radius:6px; padding:14px; border:1px solid rgba(0,0,0,0.04);">
            <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--ink-faint); margin-bottom:4px;">Client ID</div>
            <div style="font-size:13px; font-weight:600; color:var(--ink); font-family:monospace;" id="center-clientid">--</div>
          </div>
          <div style="background:rgba(0,0,0,0.02); border-radius:6px; padding:14px; border:1px solid rgba(0,0,0,0.04);">
            <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--ink-faint); margin-bottom:4px;">Status</div>
            <div style="font-size:17px; font-weight:600; color:var(--ink);" id="center-status">--</div>
          </div>
          <div style="background:rgba(0,0,0,0.02); border-radius:6px; padding:14px; border:1px solid rgba(0,0,0,0.04); cursor:pointer;" onclick="showInvite()">
            <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:var(--ink-faint); margin-bottom:4px;">Invite</div>
            <div style="font-size:14px; font-weight:600; color:var(--accent-sage);">Click to open &nearr;</div>
          </div>
        </div>
        <div style="margin-top:14px; font-size:12px; color:var(--ink-muted); line-height:1.7;" id="center-hint">
          Select a bot from the Explorer paper to manage settings.
        </div>
      </div>
    </div>
  </div>
</div>

<!-- PAPERS -->
<div class="paper paper-top" data-paper="top">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#128450; Project</div>
  <div class="paper-body">
    <div class="paper-content" id="top-landing">
      <h3>Connect Bot</h3>
      <label>Discord Bot Token</label>
      <input type="password" id="tokenInput" placeholder="Paste your Bot Token here">
      <div style="font-size:10px; color:var(--ink-faint); margin-bottom:8px;">Your token is stored securely in Supabase (RLS-protected).</div>
      <div class="paper-item" onclick="addBot()" style="justify-content:center; background:var(--accent-sage); color:#fff; border:none;"><span style="font-weight:600; letter-spacing:0.5px; font-size:11px;">CONNECT</span></div>
      <div id="addBotStatus" class="status" style="font-size:10px; text-align:center; margin-top:4px;"></div>
      <div style="margin-top:12px; font-size:10px; color:var(--ink-faint); line-height:1.6;">
        1. Create a bot at Discord Developer Portal<br>
        2. Copy the Bot Token and paste it above<br>
        3. Customise personality, AI model, voice, and more<br>
        4. Invite the bot to your servers and ping it to chat
      </div>
    </div>
    <div class="paper-content" id="top-dashboard" style="display:none;">
      <h3>Bot Status</h3>
      <div class="paper-item"><span class="icon" style="background:rgba(138,154,138,0.15);">&#9679;</span><span id="botNameDisplay">--</span></div>
      <div class="paper-item"><span class="icon">&#127380;</span><span id="botIdDisplay">--</span></div>
      <div class="paper-item"><span class="icon">&#9889;</span><span id="botActiveDisplay">Connected</span></div>
      <div style="margin-top:12px; display:flex; gap:6px;">
        <div class="paper-item" onclick="showInvite()" style="flex:1; justify-content:center; background:rgba(138,154,138,0.12); border-color:rgba(138,154,138,0.25);">Invite</div>
        <div class="paper-item" onclick="deleteCurrentBot()" style="flex:1; justify-content:center; background:rgba(200,100,100,0.08); color:#a06060; border-color:rgba(200,100,100,0.15);">Delete</div>
      </div>
      <div style="margin-top:10px; padding-top:10px; border-top:1px solid rgba(0,0,0,0.06);">
        <div class="paper-item" onclick="showAddForm()" style="justify-content:center; background:rgba(0,0,0,0.02); border-color:rgba(0,0,0,0.08);"><span style="font-size:10px; color:var(--ink-muted);">+ Connect Another Bot</span></div>
      </div>
    </div>
  </div>
</div>

<div class="paper paper-bottom" data-paper="bottom">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#128187; Terminal</div>
  <div class="paper-body">
    <div class="paper-content">
      <div style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11px; line-height:1.9; color:var(--ink-muted);">
        <div style="color:#6a9a6a;">&#10132;  bot-saas git:(main) python saas_bot.py</div>
        <div style="margin-top:8px; color:#7a8a9a;" id="term-line-1">Waiting for connection...</div>
        <div style="color:#a09070;" id="term-line-2">--</div>
        <div style="color:#8a7a8a;" id="term-line-3">--</div>
        <div style="margin-top:8px; color:#6a9a6a;">&#10132;  _</div>
      </div>
    </div>
  </div>
</div>

<div class="paper paper-left" data-paper="left">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#128450; Explorer</div>
  <div class="paper-body">
    <div class="paper-content">
      <h3>My Bots</h3>
      <div id="botsList">
        <div style="font-size:11px; color:var(--ink-faint); padding:8px 0;">No bots connected yet.<br>Open the Project paper to connect one.</div>
      </div>
    </div>
  </div>
</div>

<div class="paper paper-right" data-paper="right">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#9881; Settings</div>
  <div class="paper-body">
    <div class="paper-content" id="settingsBody">
      <div style="font-size:12px; color:var(--ink-faint); padding:8px 0;">Select a bot from Explorer to edit settings.</div>
    </div>
  </div>
</div>

<div class="paper paper-tl" data-paper="tl">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#128221; Notes</div>
  <div class="paper-body">
    <div class="paper-content">
      <div style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px; line-height:1.9; color:var(--ink-muted);">
        <div style="color:var(--ink); font-weight:600; margin-bottom:6px; font-size:11px; text-transform:uppercase; letter-spacing:1px; border-bottom:1.5px solid var(--accent-sage); padding-bottom:4px; display:inline-block;">Commands</div><br>
        <span style="color:#7a8a9a;">/ask</span> &lt;prompt&gt; [img]<br>
        <span style="color:#7a8a9a;">/summarize</span> [amount] [user]<br>
        <span style="color:#7a8a9a;">/memory</span> &mdash; show profile<br>
        <span style="color:#7a8a9a;">/persona</span> &lt;notes&gt;<br>
        <span style="color:#7a8a9a;">/forgetme</span> &mdash; wipe my memory<br>
        <span style="color:#7a8a9a;">/purgememory</span> &lt;all|self|user|channel&gt;<br>
        <span style="color:#7a8a9a;">/purgeall</span> &mdash; owner full wipe<br>
        <span style="color:#7a8a9a;">/reset</span> &mdash; clear channel<br>
        <span style="color:#7a8a9a;">/search</span> &lt;query&gt;<br>
        <span style="color:#7a8a9a;">/transcribe</span> &mdash; audio STT<br>
        <span style="color:#7a8a9a;">!forgetme</span> | <span style="color:#7a8a9a;">!purgeall</span>
      </div>
    </div>
  </div>
</div>

<div class="paper paper-tr" data-paper="tr">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#128256; AI Status</div>
  <div class="paper-body">
    <div class="paper-content">
      <h3>Active Backends</h3>
      <div class="paper-item"><span class="icon" style="background:#e8f5e9; color:#4caf50; font-size:10px;">&#9679;</span>Gemini (Text &amp; Vision)</div>
      <div class="paper-item"><span class="icon" style="background:#f3e5f5; color:#9c27b0; font-size:10px;">&#9679;</span>Groq (LLM &amp; Whisper)</div>
      <div class="paper-item"><span class="icon" style="background:#fff3e0; color:#ff6f00; font-size:10px;">&#9679;</span>Mistral (Text &amp; Pixtral)</div>
      <div class="paper-item"><span class="icon" style="background:#e3f2fd; color:#2196f3; font-size:10px;">&#9679;</span>OpenRouter (Vision / LLM)</div>
      <div class="paper-item"><span class="icon" style="background:#e8f8f5; color:#1abc9c; font-size:10px;">&#9679;</span>Edge Neural TTS (Free)</div>
      <div class="paper-item"><span class="icon" style="background:#fce4ec; color:#e91e63; font-size:10px;">&#9679;</span>ElevenLabs Studio</div>
      <div class="paper-item"><span class="icon" style="background:#ede7f6; color:#673ab7; font-size:10px;">&#9679;</span>Cartesia Sonic</div>
      <div class="paper-item"><span class="icon" style="background:#fffde7; color:#f9a825; font-size:10px;">&#9679;</span>Hugging Face</div>
      <div style="margin-top:10px; font-size:10px; color:var(--ink-faint); line-height:1.5;">
        Provider keys are loaded securely on the backend. Multi-tier auto-failover ensures 100% uptime.
      </div>
    </div>
  </div>
</div>

<input type="file" id="deskCardInput" accept=".json,.png,image/png,application/json" style="display:none;" onchange="handleDeskCardFileUpload(event)">

<div class="paper paper-bl" data-paper="bl">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#127760; Lore &amp; Card Import</div>
  <div class="paper-body">
    <div class="paper-content">
      <h3>Import Character Persona</h3>
      <div style="font-size:11px; color:var(--ink-muted); margin-bottom:12px; line-height:1.5;">
        Upload Chub, Janitor AI, or Tavern card files (.json, .png) or pull lore directly from Wiki / Fandom URLs. Automatically fills all bot settings.
      </div>

      <div class="paper-item" onclick="document.getElementById('deskCardInput').click()" style="justify-content:center; background:var(--accent-sage); color:#fff; border:none; margin-bottom:10px;">
        <span style="font-weight:600; font-size:11px;">📁 UPLOAD CHARACTER FILE (.JSON, .PNG)</span>
      </div>

      <label style="font-size:10px; text-transform:uppercase; color:var(--ink-faint); margin-top:8px;">Pull Lore from Wiki Link</label>
      <input type="url" id="deskWikiUrlInput2" placeholder="https://*.fandom.com/wiki/... or Wikipedia URL" style="margin-bottom:6px;">
      <div class="paper-item" onclick="pullDeskPersonalityFromWiki('deskWikiUrlInput2')" style="justify-content:center; background:rgba(138,154,138,0.15); border-color:rgba(138,154,138,0.3); font-size:11px; font-weight:600;">
        ⚡ PULL &amp; APPLY LORE
      </div>

      <div style="margin-top:14px; padding-top:10px; border-top:1px solid rgba(0,0,0,0.06); font-size:10px; color:var(--ink-faint); line-height:1.5;">
        Supports V1/V2 Character Cards &amp; Janitor exports (e.g. <code>main_sasaki-yukari_spec_v2.json</code>).
      </div>
    </div>
  </div>
</div>

<div class="paper paper-br" data-paper="br">
  <div class="paper-clip"></div>
  <div class="paper-close">&#10005;</div>
  <div class="paper-header">&#129513; Extras</div>
  <div class="paper-body">
    <div class="paper-content">
      <h3>Quick Links</h3>
      <div class="paper-item" onclick="window.open('https://discord.com/developers/applications','_blank')"><span class="icon">&#127918;</span>Discord Dev Portal</div>
      <div class="paper-item" onclick="window.open('https://console.mistral.ai','_blank')"><span class="icon">&#129302;</span>Mistral Console</div>
      <div class="paper-item" onclick="window.open('https://groq.com','_blank')"><span class="icon">&#9889;</span>Groq Console</div>
      <div class="paper-item" onclick="window.open('https://openrouter.ai','_blank')"><span class="icon">&#129504;</span>OpenRouter Models</div>
      <div class="paper-item" onclick="window.open('https://elevenlabs.io','_blank')"><span class="icon">&#127908;</span>ElevenLabs</div>
    </div>
  </div>
</div>

<!-- DESK OBJECTS -->

<div class="desk-object sticky-note" title="Enter Web Studio" onclick="window.location.href='/'" style="cursor:pointer; position:absolute; bottom:24%; left:18%; width:88px; height:88px; background:#fff3a8; transform:rotate(6deg); box-shadow:1px 3px 10px rgba(0,0,0,0.12); padding:8px; display:flex; align-items:center; justify-content:center; z-index:30; border-radius:2px; transition:transform 0.18s ease, box-shadow 0.18s ease;">
  <div style="font-size:11px; font-weight:700; text-align:center; color:#5a5030; line-height:1.3; user-select:none;">
    ✦<br>AI Studio<br>↗
  </div>
</div>

<div class="desk-object compass" title="Compass" onclick="showToast('Compass points to creativity')">
  <div class="compass-handle"></div><div class="compass-joint"></div>
  <div class="compass-leg left"></div><div class="compass-leg right"></div>
  <div class="compass-point left"></div><div class="compass-point right"></div>
</div>
<div class="desk-object coffee-cup" title="Coffee" onclick="showToast('Refreshed'); loadBots();">
  <div class="steam"></div><div class="steam"></div><div class="steam"></div>
  <div class="cup-body"><div class="coffee-surface"></div><div class="cup-handle"></div></div>
</div>
<div class="desk-object pencil" title="Pencil" onclick="openPaperByClass('paper-right'); showToast('Edit mode')">
  <div class="pencil-body"><div class="pencil-ferrule"></div><div class="pencil-eraser"></div></div>
</div>
<div class="desk-object ruler" title="Ruler" onclick="showToast('Guidelines toggled')">
  <div class="ruler-body"><div class="ruler-markings"></div></div>
</div>
<div class="desk-object eraser" title="Eraser" onclick="showToast('Memory is managed via Discord commands (/memory, /summarize)')">
  <div class="eraser-body"></div>
</div>

<script>
const SUPABASE_URL = "https://tdawmkgedbxbjkctylld.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRkYXdta2dlZGJ4YmprY3R5bGxkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxMTYzMjQsImV4cCI6MjEwMTY5MjMyNH0.HiZBhR1vK2jHn0m-xYakrfHIym44rvsSuAt7UAjeXoo";

let currentSession = null;
let currentBot = null;
let bots = [];
let openPaperEl = null;

function $(id){ return document.getElementById(id); }
function setStatus(id, text, type) {
  type = type || "info";
  const el = $(id); if(!el) return;
  el.textContent = text; el.className = "status " + type;
}
function showToast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(function(){ t.classList.remove("show"); }, 2500);
}

async function sbAuth(path, body, method) {
  method = method || "POST";
  const res = await fetch(SUPABASE_URL + "/auth/v1" + path, {
    method: method,
    headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(function(){return {};});
  if(!res.ok) throw new Error(data.msg || data.message || data.error_description || JSON.stringify(data));
  return data;
}

async function refreshSession() {
  if(!currentSession || !currentSession.refresh_token) return false;
  try {
    const data = await sbAuth("/token?grant_type=refresh_token", {
      refresh_token: currentSession.refresh_token
    });
    currentSession = data;
    localStorage.setItem("sb_session", JSON.stringify(data));
    return true;
  } catch(e) {
    console.error("[AUTH] Refresh failed:", e);
    return false;
  }
}
async function sbQuery(table, opts) {
  opts = opts || {};
  if(!currentSession || !currentSession.access_token) {
    doLogout();
    throw new Error("Session expired. Please log in again.");
  }
  const method = opts.method || "GET";
  const match = opts.match;
  const body = opts.body;
  const select = opts.select || "*";
  const order = opts.order;
  let url = SUPABASE_URL + "/rest/v1/" + table;
  const headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": "Bearer " + currentSession.access_token,
    "Content-Type": "application/json"
  };
  if(select) headers["Prefer"] = "return=representation";
  if(match) {
    const q = new URLSearchParams();
    for(const k in match) q.append(k, "eq." + match[k]);
    url += "?" + q.toString();
  }
  if(order) url += (url.indexOf("?") !== -1 ? "&" : "?") + "order=" + order;
  let res = await fetch(url, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined });
  if(res.status === 401 || res.status === 403) {
    const refreshed = await refreshSession();
    if(refreshed) {
      headers["Authorization"] = "Bearer " + currentSession.access_token;
      res = await fetch(url, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined });
    } else {
      doLogout();
      throw new Error("Session expired. Please log in again.");
    }
  }
  const data = await res.json().catch(function(){return {};});
  if(!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

function switchAuth(tab) {
  $("tab-login").classList.toggle("active", tab === "login");
  $("tab-register").classList.toggle("active", tab === "register");
  $("panel-login").classList.toggle("active", tab === "login");
  $("panel-register").classList.toggle("active", tab === "register");
  $("panel-login").classList.toggle("hidden", tab !== "login");
  $("panel-register").classList.toggle("hidden", tab !== "register");
  setStatus("authStatus", "");
}
async function doLogin() {
  setStatus("authStatus", "Signing in...", "info");
  try {
    const data = await sbAuth("/token?grant_type=password", {
      email: $("loginEmail").value.trim(),
      password: $("loginPassword").value
    });
    currentSession = data;
    localStorage.setItem("sb_session", JSON.stringify(data));
    onAuthSuccess();
  } catch(e) { setStatus("authStatus", e.message, "err"); }
}
async function doRegister() {
  setStatus("authStatus", "Creating account...", "info");
  try {
    await sbAuth("/signup", {
      email: $("regEmail").value.trim(),
      password: $("regPassword").value
    });
    setStatus("authStatus", "Account created! Now log in.", "ok");
    switchAuth("login");
  } catch(e) { setStatus("authStatus", e.message, "err"); }
}
function doLogout() {
  currentSession = null; currentBot = null; bots = [];
  localStorage.removeItem("sb_session");
  localStorage.removeItem("my_bots");
  localStorage.removeItem("bot_saas_user_id");
  localStorage.removeItem("bot_saas_user_email");
  $("authOverlay").style.display = "flex";
  renderBotsList();
  showLanding();
  setStatus("authStatus", "Logged out", "info");
}
function onAuthSuccess() {
  $("authOverlay").style.display = "none";
  showToast("Welcome back");
  if(currentSession && currentSession.user) {
    localStorage.setItem("bot_saas_user_id", currentSession.user.id);
    localStorage.setItem("bot_saas_user_email", currentSession.user.email || "");
  }
  loadBots();
}

function extractClientId(token) {
  try {
    const parts = token.split(".");
    if(parts.length >= 2) {
      let b64 = parts[0].replace(/-/g, "+").replace(/_/g, "/");
      const pad = (4 - b64.length % 4) % 4;
      b64 += "=".repeat(pad);
      const id = atob(b64);
      if(/^\d+$/.test(id)) return id;
    }
  } catch(e){}
  return null;
}
function getInviteUrl(clientId) {
  return "https://discord.com/oauth2/authorize?client_id=" + clientId + "&permissions=274877910080&scope=bot%20applications.commands";
}

async function addBot() {
  const token = $("tokenInput").value.trim();
  if(!token) { setStatus("addBotStatus", "Paste a token first", "err"); return; }
  const clientId = extractClientId(token);
  if(!clientId) { setStatus("addBotStatus", "Invalid token format", "err"); return; }
  setStatus("addBotStatus", "Saving...", "info");
  try {
    let botName = "Bot " + clientId.slice(-4);
    let avatarUrl = null;
    try {
      const dres = await fetch("/api/discord_info?token=" + encodeURIComponent(token));
      if(dres.ok) {
        const d = await dres.json();
        if(d && d.ok) {
          botName = d.username || botName;
          avatarUrl = d.avatar_url || avatarUrl;
        }
      }
    } catch(e){}
    if(!avatarUrl) {
      try {
        const disc = (BigInt(clientId) >> 22n) % 6n;
        avatarUrl = `https://cdn.discordapp.com/embed/avatars/${disc}.png`;
      } catch(e){}
    }

    const existing = await sbQuery("user_bots", { match:{user_id: currentSession.user.id, bot_id: clientId} });
    if(existing && existing.length > 0) {
      const exSettings = existing[0].settings || {};
      // If we got a real custom avatar from Discord API, update it. If it's just a fallback embed avatar, preserve existing custom avatar!
      if (avatarUrl && !avatarUrl.includes('/embed/avatars/')) {
        exSettings.avatar_url = avatarUrl;
        exSettings.pfp = avatarUrl;
      } else if (!exSettings.avatar_url && !exSettings.pfp && avatarUrl) {
        exSettings.avatar_url = avatarUrl;
        exSettings.pfp = avatarUrl;
      }
      await sbQuery("user_bots", { method:"PATCH", match:{id: existing[0].id}, body:{
        discord_token: token, bot_name: botName, is_active: true, settings: exSettings
      }});
      showToast("Token updated for existing bot");
    } else {
      const initSettings = getDefaultSettings();
      if(avatarUrl) {
        initSettings.avatar_url = avatarUrl;
        initSettings.pfp = avatarUrl;
      }
      await sbQuery("user_bots", { method:"POST", body:{
        user_id: currentSession.user.id,
        discord_token: token,
        bot_id: clientId,
        bot_name: botName,
        is_active: true,
        settings: initSettings
      }});
      showToast("Bot connected successfully");
    }

    // Direct backend sync
    try {
      const authHdr = currentSession && currentSession.access_token ? { 'Authorization': 'Bearer ' + currentSession.access_token } : {};
      await fetch('/api/bots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHdr },
        body: JSON.stringify({
          id: clientId,
          token: token,
          name: botName,
          owner_id: currentSession.user.id,
          config: getDefaultSettings()
        })
      });
    } catch(e) {}
    $("tokenInput").value = "";
    setStatus("addBotStatus", "", "ok");
    loadBots();
    showDashboard(null);
  } catch(e) {
    setStatus("addBotStatus", e.message, "err");
    console.error(e);
  }
}
async function loadBots() {
  if(!currentSession) return;
  try {
    bots = await sbQuery("user_bots", { match:{user_id: currentSession.user.id}, order:"created_at.desc" });
    if(bots && Array.isArray(bots)) {
      localStorage.setItem("my_bots", JSON.stringify(bots));
    }
    if(currentSession.user) {
      localStorage.setItem("bot_saas_user_id", currentSession.user.id);
      localStorage.setItem("bot_saas_user_email", currentSession.user.email || "");
    }
    renderBotsList();
    updateTerminal("Loaded " + bots.length + " bot(s)", "User: " + currentSession.user.email, "Supabase: connected");
  } catch(e) {
    updateTerminal("Failed to load bots", e.message, "");
  }
}
function renderBotsList() {
  const list = $("botsList");
  if(!bots || bots.length === 0) {
    list.innerHTML = '<div style="font-size:11px; color:var(--ink-faint); padding:8px 0;">No bots connected yet.<br>Open the Project paper to connect one.</div>';
    return;
  }
  list.innerHTML = bots.map(function(b, i){
    return '<div class="paper-item ' + (currentBot && currentBot.id === b.id ? "active-bot" : "") + '" onclick="selectBot(' + i + ')">' +
    '<span class="icon">&#9679;</span><span>' + escapeHtml(b.bot_name || "Unnamed") + '<br><span style="font-size:10px;color:var(--ink-faint)">' + (b.bot_id || "--") + '</span></span></div>';
  }).join("");
}
function selectBot(idx) {
  currentBot = bots[idx];
  renderBotsList();
  showDashboard(currentBot);
  renderSettings(currentBot);
  openPaperByClass("paper-top");
}
function showLanding() {
  $("center-landing").style.display = "flex";
  $("center-dashboard").style.display = "none";
  $("top-landing").style.display = "block";
  $("top-dashboard").style.display = "none";
}
function showDashboard(bot) {
  $("center-landing").style.display = "none";
  $("center-dashboard").style.display = "block";
  if(bot) {
    $("center-botname").textContent = bot.bot_name || "Unnamed";
    $("center-clientid").textContent = bot.bot_id || "--";
    $("center-status").textContent = bot.is_active ? "Active" : "Paused";
    $("center-status").style.color = bot.is_active ? "#4a9a4a" : "#c06060";
    $("botNameDisplay").textContent = bot.bot_name || "Unnamed";
    $("botIdDisplay").textContent = bot.bot_id || "--";
    $("botActiveDisplay").textContent = bot.is_active ? "Active" : "Paused";
    $("top-landing").style.display = "none";
    $("top-dashboard").style.display = "block";
  } else {
    $("center-botname").textContent = "--";
    $("center-clientid").textContent = "--";
    $("center-status").textContent = "--";
    $("center-status").style.color = "var(--ink)";
  }
}
function showAddForm() {
  currentBot = null;
  showLanding();
  renderBotsList();
  $("tokenInput").value = "";
  setStatus("addBotStatus", "");
  openPaperByClass("paper-top");
}
function showInvite() {
  const id = currentBot ? currentBot.bot_id : null;
  if(!id) { showToast("No bot selected"); return; }
  const url = getInviteUrl(id);
  window.open(url, "_blank");
}
async function deleteCurrentBot() {
  if(!currentBot) return;
  if(!confirm('Delete bot "' + (currentBot.bot_name || "Unnamed") + '"? This cannot be undone.')) return;
  try {
    await sbQuery("user_bots", { method:"DELETE", match:{id: currentBot.id} });
    showToast("Bot deleted");
    currentBot = null;
    loadBots();
    showLanding();
  } catch(e) { showToast("Error: " + e.message); }
}
function updateTerminal(a, b, c) {
  if(a) $("term-line-1").textContent = a;
  if(b) $("term-line-2").textContent = b;
  if(c) $("term-line-3").textContent = c;
}
function escapeHtml(t) {
  const d = document.createElement("div"); d.textContent = t; return d.innerHTML;
}

/* ---------- SETTINGS (Aligned with saas_bot.py DEFAULT_CONFIG) ---------- */
function getDefaultSettings() {
  return {
    personality: "You are a helpful, friendly, and deeply engaging companion. Speak naturally, express opinions, and remember details about users.",
    provider: "auto",
    gemini_model: "gemini-1.5-pro",
    groq_model: "openai/gpt-oss-120b",
    mistral_model: "mistral-small-latest",
    openai_chat_model: "gpt-4o-mini",
    openai_key: "",
    openai_base_url: "",
    openai_vision_model: "gpt-4o-mini",
    custom_base_url: "",
    custom_key: "",
    custom_model: "",
    deepseek_model: "deepseek-chat",
    deepseek_key: "",
    deepseek_base_url: "",
    model: "meta-llama/llama-3.3-70b-instruct",
    use_custom_model: false,
    custom_model: "",
    max_tokens: 800,
    temperature: 0.7,
    top_p: 1.0,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    context_enabled: true,
    max_context: 10,
    cooldown_seconds: 10,
    tts_enabled: false,
    tts_provider: "auto",
    elevenlabs_voice_id: "21m00Tcm4TlvDq8ikWAM",
    elevenlabs_model: "eleven_turbo_v2_5",
    openai_voice: "nova",
    openai_model: "tts-1",
    cartesia_voice_id: "a0e99841-438c-4a64-b679-ae501e7d6091",
    cartesia_model: "sonic-3.5",
    groq_tts_voice: "hannah",
    groq_tts_model: "canopylabs/orpheus-v1-english",
    edge_tts_voice: "en-US-AvaMultilingualNeural",
    fish_voice_id: "",
    fish_model: "s2.1-pro-free",
    vision_enabled: true,
    vision_provider: "gemini",
    vision_model: "meta-llama/llama-3.2-11b-vision-instruct",
    gemini_vision_model: "gemini-1.5-pro",
    auto_search: true,
    user_memory_enabled: true,
    open_chat_enabled: false,
    auto_stt: false,
    message_split_enabled: false,
    message_split_min: 1,
    message_split_max: 3,
    message_split_delay: 1.0,
    random_dms_enabled: false,
    random_dms_interval_minutes: 60,
    random_dms_prompt: "Send a casual, friendly message to check in.",
    random_chat_enabled: false,
    random_chat_chance: 0.05,
    random_chat_context_limit: 50,
    bot_name_triggers: "bot",
    file_reading_enabled: true,
    video_watching_enabled: true,
    bot_conversation_enabled: false,
    bot_conversation_max: 2,
    huggingface_model: ""
  };
}

function renderSettings(bot) {
  const s = bot.settings || getDefaultSettings();
  const body = $("settingsBody");
  const mkRow = function(lbl, inner){ return '<div class="settings-row"><label>' + lbl + '</label>' + inner + '</div>'; };
  const mkInput = function(k, ph, type, step){
    type = type || "text";
    const v = s[k] !== undefined && s[k] !== null ? escapeHtml(String(s[k])) : "";
    const st = step ? ' step="' + step + '"' : '';
    return '<input type="' + type + '" id="set_' + k + '" placeholder="' + (ph||"") + '" value="' + v + '"' + st + '>';
  };
  const mkSelect = function(k, opts){ 
    return '<select id="set_' + k + '">' + opts.map(function(o){ return '<option value="' + o.v + '" ' + (s[k] == o.v ? "selected" : "") + '>' + o.l + '</option>'; }).join("") + '</select>'; 
  };
  const mkCheck = function(k, labelText){ 
    return '<div class="settings-row"><label><input type="checkbox" id="set_' + k + '" ' + (s[k] ? "checked" : "") + '> ' + labelText + '</label></div>'; 
  };
  const mkArea = function(k, rows, ph){ 
    rows = rows || 3; 
    return '<textarea id="set_' + k + '" rows="' + rows + '" placeholder="' + (ph||"") + '">' + escapeHtml(s[k] || "") + '</textarea>'; 
  };

  body.innerHTML =
    '<div style="display:flex;gap:8px;margin-bottom:10px;">' +
    '<div class="btn" onclick="saveSettings()" style="flex:1;">SAVE SETTINGS</div>' +
    '<div class="btn btn-secondary" onclick="resetSettings()" style="flex:1;">RESET DEFAULTS</div>' +
    '</div>' +
    '<div id="settingsStatus" class="status" style="margin-bottom:10px;"></div>' +

    '<div class="settings-group" style="background:rgba(138,154,138,0.08); border:1.5px solid rgba(138,154,138,0.25); border-radius:6px; padding:12px; margin-bottom:12px;">' +
    '<div class="settings-group-title" style="color:var(--ink); font-weight:700; margin-bottom:8px;">🌐 Import Card / Wiki Lore</div>' +
    '<div style="display:flex; gap:6px; margin-bottom:8px;">' +
    '<div class="paper-item" onclick="document.getElementById(\'deskCardInput\').click()" style="flex:1; justify-content:center; background:var(--accent-sage); color:#fff; border:none; font-size:11px; font-weight:600; padding:8px;">📁 Upload File (.json, .png)</div>' +
    '</div>' +
    '<div style="font-size:10px; color:var(--ink-faint); margin-bottom:4px;">Or pull lore from Wiki / Fandom URL:</div>' +
    '<div style="display:flex; gap:6px;">' +
    '<input type="url" id="deskWikiUrlInput" placeholder="https://*.fandom.com/wiki/... or Wikipedia" style="flex:1; font-size:11px; padding:6px 8px;">' +
    '<div class="paper-item" id="deskWikiPullBtn" onclick="pullDeskPersonalityFromWiki(\'deskWikiUrlInput\')" style="background:rgba(138,154,138,0.15); border-color:rgba(138,154,138,0.3); font-size:11px; font-weight:600; white-space:nowrap; padding:6px 12px;">⚡ Pull Lore</div>' +
    '</div>' +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Personality</div>' +
    mkRow("", mkArea("personality", 3, "How should your bot behave?")) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">AI Provider</div>' +
    mkRow("Provider", mkSelect("provider",[
      {v:"auto",l:"Auto (Gemini -> Groq -> Mistral -> OpenAI -> DeepSeek -> OpenRouter -> HF)"},
      {v:"gemini",l:"Gemini Only"},
      {v:"groq",l:"Groq Only"},
      {v:"mistral",l:"Mistral Only"},
      {v:"openai",l:"OpenAI Only"},
      {v:"custom",l:"Custom Endpoint (LiteRouter / Local Tunnel / OpenAI Compatible)"},
      {v:"deepseek",l:"DeepSeek Only"},
      {v:"openrouter",l:"OpenRouter Only"},
      {v:"huggingface",l:"Hugging Face Only"}
    ])) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Custom Endpoint (LiteRouter / Local Tunnel / Any OpenAI API)</div>' +
    mkRow("Base URL", mkInput("custom_base_url","https://api.literouter.com/v1 or http://localhost:11434/v1")) +
    mkRow("API Key / Token", mkInput("custom_key","API key / token (leave blank for local tunnels)","password")) +
    mkRow("Model Name", mkInput("custom_model","e.g. claude-3-7-sonnet, deepseek-r1, llama-3.3-70b")) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Standard Models</div>' +
    mkRow("Gemini Model", mkInput("gemini_model","gemini-1.5-pro")) +
    mkRow("Groq Model", mkInput("groq_model","openai/gpt-oss-120b")) +
    mkRow("Mistral Model", mkInput("mistral_model","mistral-small-latest")) +
    mkRow("OpenAI Model", mkInput("openai_chat_model","gpt-4o-mini (custom model strings supported)")) +
    mkRow("OpenAI API Key", mkInput("openai_key","sk-... (leave blank to use owner key)","password")) +
    mkRow("DeepSeek Model", mkInput("deepseek_model","deepseek-chat / deepseek-reasoner")) +
    mkRow("DeepSeek API Key", mkInput("deepseek_key","sk-... (leave blank to use owner key)","password")) +
    mkRow("Hugging Face Model", mkInput("huggingface_model","Qwen/Qwen2.5-72B-Instruct")) +
    mkRow("OpenRouter Model", mkInput("model","meta-llama/llama-3.3-70b-instruct")) +
    mkCheck("use_custom_model","Use Custom OpenRouter Model") +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Generation Parameters</div>' +
    '<div class="settings-col2">' +
    '<div>' + mkRow("Max Tokens", mkInput("max_tokens","800","number")) + '</div>' +
    '<div>' + mkRow("Temperature", mkInput("temperature","0.7","number","0.1")) + '</div>' +
    '<div>' + mkRow("Top P", mkInput("top_p","1.0","number","0.05")) + '</div>' +
    '<div>' + mkRow("Cooldown (s)", mkInput("cooldown_seconds","10","number")) + '</div>' +
    '<div>' + mkRow("Freq Penalty", mkInput("frequency_penalty","0.0","number","0.1")) + '</div>' +
    '<div>' + mkRow("Pres Penalty", mkInput("presence_penalty","0.0","number","0.1")) + '</div>' +
    '</div>' +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Memory &amp; Profiling</div>' +
    mkCheck("context_enabled","Context Enabled") +
    mkRow("Max Context", mkInput("max_context","10","number")) +
    mkCheck("user_memory_enabled","Track User Memories &amp; Scene Context") +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Voice &amp; Multi-Engine TTS</div>' +
    mkCheck("tts_enabled","Enable Voice Audio Responses") +
    mkRow("TTS Engine", mkSelect("tts_provider",[
      {v:"auto",l:"Auto (ElevenLabs -> OpenAI -> Cartesia -> Groq -> Edge -> Fish)"},
      {v:"edge",l:"Edge Neural TTS (Free, zero keys)"},
      {v:"elevenlabs",l:"ElevenLabs Studio"},
      {v:"openai",l:"OpenAI TTS"},
      {v:"cartesia",l:"Cartesia Sonic"},
      {v:"groq",l:"Groq Orpheus"},
      {v:"fish",l:"Fish Audio"}
    ])) +
    mkRow("Edge Voice", mkInput("edge_tts_voice","en-US-AvaMultilingualNeural")) +
    mkRow("ElevenLabs Voice ID", mkInput("elevenlabs_voice_id","21m00Tcm4TlvDq8ikWAM")) +
    mkRow("OpenAI Voice", mkInput("openai_voice","nova")) +
    mkRow("Cartesia Voice ID", mkInput("cartesia_voice_id","a0e99841-438c-4a64-b679-ae501e7d6091")) +
    mkRow("Fish Audio Voice ID", mkInput("fish_voice_id","paste Fish Audio reference ID")) +
    mkRow("Fish Model", mkSelect("fish_model",[{v:"s2.1-pro-free",l:"s2.1-pro-free"},{v:"s2-pro",l:"s2-pro"},{v:"s2",l:"s2"}])) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Vision &amp; Image Understanding</div>' +
    mkCheck("vision_enabled","Enable Vision") +
    mkRow("Vision Provider", mkSelect("vision_provider",[
      {v:"gemini",l:"Gemini Vision (Fast & Accurate)"},
      {v:"openai",l:"OpenAI Vision (GPT-4o / GPT-4o-mini)"},
      {v:"mistral",l:"Mistral Pixtral Vision"},
      {v:"openrouter",l:"OpenRouter Vision"}
    ])) +
    mkRow("Gemini Vision Model", mkInput("gemini_vision_model","gemini-1.5-pro")) +
    mkRow("OpenAI Vision Model", mkInput("openai_vision_model","gpt-4o-mini")) +
    mkRow("OpenRouter Vision Model", mkInput("vision_model","meta-llama/llama-3.2-11b-vision-instruct")) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">File &amp; Video Understanding</div>' +
    mkCheck("file_reading_enabled","Read PDF/DOCX/CSV document attachments") +
    mkCheck("video_watching_enabled","Watch and analyze video attachments (ffmpeg frames)") +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Autonomous Features</div>' +
    mkCheck("auto_search","Proactive web search on real-time queries") +
    mkCheck("auto_stt","Auto-STT (transcribe audio/voice notes via Whisper)") +
    mkCheck("open_chat_enabled","Open chat (trigger on bot name mention)") +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Message Splitting</div>' +
    mkCheck("message_split_enabled","Split long replies into natural separate messages") +
    '<div class="settings-col3">' +
    '<div>' + mkRow("Min Msgs", mkInput("message_split_min","1","number")) + '</div>' +
    '<div>' + mkRow("Max Msgs", mkInput("message_split_max","3","number")) + '</div>' +
    '<div>' + mkRow("Delay (s)", mkInput("message_split_delay","1.0","number","0.1")) + '</div>' +
    '</div>' +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Random DMs</div>' +
    mkCheck("random_dms_enabled","Send casual check-in DMs to past users") +
    mkRow("Interval (min)", mkInput("random_dms_interval_minutes","60","number")) +
    mkRow("DM Prompt", mkInput("random_dms_prompt","Send a casual, friendly message to check in.")) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Random Server Chat</div>' +
    mkCheck("random_chat_enabled","Randomly participate in server discussions") +
    '<div class="settings-col2">' +
    '<div>' + mkRow("Chance (0-1)", mkInput("random_chat_chance","0.05","number","0.01")) + '</div>' +
    '<div>' + mkRow("Context msgs", mkInput("random_chat_context_limit","50","number")) + '</div>' +
    '</div>' +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Bot Name Triggers</div>' +
    mkRow("Triggers (comma-separated)", mkInput("bot_name_triggers","bot, ai, helper")) +
    '</div>' +

    '<div class="settings-group"><div class="settings-group-title">Bot Conversation</div>' +
    mkCheck("bot_conversation_enabled","Allow Bot-to-Bot Chat") +
    mkRow("Max Exchanges (1-3)", mkInput("bot_conversation_max","2","number")) +
    '<div style="font-size:10px; color:var(--ink-faint); margin-bottom:8px; line-height:1.5;">OFF by default to prevent infinite loops. When ON, bots chat for up to 1-3 messages before stopping.</div>' +
    '</div>';
}

async function saveSettings() {
  if(!currentBot) { setStatus("settingsStatus", "No bot selected", "err"); return; }
  const keys = Object.keys(getDefaultSettings());
  const oldSettings = (currentBot && currentBot.settings) || {};
  const newSettings = { ...oldSettings };
  keys.forEach(function(k){
    const el = $("set_" + k);
    if(!el) return;
    const def = getDefaultSettings()[k];
    if(typeof def === "boolean") newSettings[k] = el.checked;
    else if(typeof def === "number") newSettings[k] = parseFloat(el.value) || 0;
    else newSettings[k] = el.value;
  });

  // Preserve avatar, PFP, owner, and interactions so drafting updates never lose them
  if (oldSettings.avatar_url && !newSettings.avatar_url) newSettings.avatar_url = oldSettings.avatar_url;
  if (oldSettings.pfp && !newSettings.pfp) newSettings.pfp = oldSettings.pfp;
  if (oldSettings.owner_username && !newSettings.owner_username) newSettings.owner_username = oldSettings.owner_username;
  if (oldSettings.interactions && !newSettings.interactions) newSettings.interactions = oldSettings.interactions;

  setStatus("settingsStatus", "Saving...", "info");
  try {
    if(currentBot.id) {
      await sbQuery("user_bots", { method:"PATCH", match:{id: currentBot.id}, body:{ settings: newSettings, updated_at: new Date().toISOString() } });
    }
    currentBot.settings = newSettings;

    // Direct sync to backend /api/bots/<bot_id>/config
    const bid = currentBot.bot_id || currentBot.id;
    if(bid) {
      try {
        const token = currentSession ? currentSession.access_token : '';
        const headers = { 'Content-Type': 'application/json' };
        if(token) headers['Authorization'] = 'Bearer ' + token;
        const uid = currentSession && currentSession.user ? currentSession.user.id : '';
        let url = '/api/bots/' + encodeURIComponent(bid) + '/config';
        if(uid) url += '?user_id=' + encodeURIComponent(uid);
        await fetch(url, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            name: currentBot.bot_name || '',
            personality: newSettings.personality || '',
            config: newSettings
          })
        });
      } catch(backendErr) {
        console.warn('[SYNC] Backend sync error:', backendErr);
      }
    }

    // Direct sync to localStorage
    if(bots && Array.isArray(bots)) {
      localStorage.setItem("my_bots", JSON.stringify(bots));
    }

    setStatus("settingsStatus", "Saved and synced successfully", "ok");
    showToast("Settings & Prompt synced");
  } catch(e) {
    setStatus("settingsStatus", e.message, "err");
  }
}

function resetSettings() {
  if(!currentBot) return;
  if(!confirm("Reset all settings to defaults?")) return;
  currentBot.settings = getDefaultSettings();
  renderSettings(currentBot);
  setStatus("settingsStatus", "Defaults loaded. Click SAVE to apply.", "info");
}

/* ---------- CHARACTER CARD & WIKI IMPORTER ---------- */
function extractPngTextChunks(arrayBuffer) {
  try {
    const view = new DataView(arrayBuffer);
    if (view.getUint32(0) !== 0x89504E47 || view.getUint32(4) !== 0x0D0A1A0A) return null;
    let offset = 8;
    const chunks = {};
    const decoder = new TextDecoder('utf-8');

    while (offset < view.byteLength) {
      if (offset + 8 > view.byteLength) break;
      const length = view.getUint32(offset);
      const type = String.fromCharCode(view.getUint8(offset + 4), view.getUint8(offset + 5), view.getUint8(offset + 6), view.getUint8(offset + 7));
      const chunkDataOffset = offset + 8;
      if (chunkDataOffset + length > view.byteLength) break;

      if (type === 'tEXt' || type === 'iTXt') {
        const chunkBytes = new Uint8Array(arrayBuffer, chunkDataOffset, length);
        const nullIdx = chunkBytes.indexOf(0);
        if (nullIdx !== -1) {
          const keyword = decoder.decode(chunkBytes.subarray(0, nullIdx)).toLowerCase();
          if (['chara', 'ccv3', 'character'].includes(keyword)) {
            let rawStr = '';
            if (type === 'tEXt') {
              rawStr = decoder.decode(chunkBytes.subarray(nullIdx + 1)).trim();
            } else {
              let textStart = nullIdx + 3;
              let nullCount = 0;
              for (let i = textStart; i < chunkBytes.length && nullCount < 2; i++) {
                if (chunkBytes[i] === 0) { nullCount++; textStart = i + 1; }
              }
              rawStr = decoder.decode(chunkBytes.subarray(textStart)).trim();
            }
            if (rawStr.startsWith('{')) chunks[keyword] = rawStr;
            else {
              try { chunks[keyword] = decodeURIComponent(escape(atob(rawStr))); }
              catch (e) { try { chunks[keyword] = atob(rawStr); } catch (e2) {} }
            }
          }
        }
      }
      offset += 12 + length;
    }
    return chunks;
  } catch (e) { return null; }
}

function parseCharacterCardData(raw, sourceFileName) {
  let data = raw;
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch (e) {}
  }
  if (!data || typeof data !== 'object') return null;

  const d = (data.spec === 'chara_card_v2' || data.spec_version === '2.0' || data.data) ? (data.data || {}) : data;
  const name = (d.name || d.char_name || d.bot_name || data.name || (sourceFileName ? sourceFileName.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ') : '') || 'New Character').trim();
  const rawDesc = d.description || d.char_desc || d.desc || data.description || '';
  const rawPers = d.personality || d.char_personality || d.personality_summary || data.personality || '';
  const rawScenario = d.scenario || d.char_scenario || data.scenario || '';
  const rawGreeting = d.first_mes || d.greeting || d.first_message || d.initial_message || data.first_mes || ("*looks up and smiles* Hello, I am " + name + ".");
  const rawExamples = d.mes_example || d.example_dialogue || d.examples || data.mes_example || '';
  const rawSysPrompt = d.system_prompt || data.system_prompt || '';
  const rawAvatar = d.avatar || d.avatar_url || d.pfp || data.avatar || data.avatar_url || data.pfp || '';
  const tags = Array.isArray(d.tags) ? d.tags : (Array.isArray(data.tags) ? data.tags : []);

  let role = d.role || data.role || '';
  if (!role && tags.length > 0) {
    const cleanTags = tags.filter(t => t && String(t).length < 20 && !['NSFW', 'ROOT', 'OAI', 'TAVERN'].includes(String(t).toUpperCase()));
    if (cleanTags.length > 0) role = cleanTags.slice(0, 2).join(' • ');
  }
  if (!role) role = 'AI Persona';

  let shortDesc = rawPers ? rawPers.slice(0, 140) : (rawDesc ? rawDesc.slice(0, 140) : `${name} — ${role}`);

  let promptParts = [];
  if (rawSysPrompt) promptParts.push(rawSysPrompt.trim());
  promptParts.push(`[Character: ${name}]`);
  if (role) promptParts.push(`[Role: ${role}]`);
  if (rawPers) promptParts.push(`[Personality & Traits:\n${rawPers.trim()}]`);
  if (rawDesc) promptParts.push(`[Description & Background:\n${rawDesc.trim()}]`);
  if (rawScenario) promptParts.push(`[Scenario & Setting:\n${rawScenario.trim()}]`);
  if (rawExamples) promptParts.push(`[Example Dialogue:\n${rawExamples.trim()}]`);

  const fullPrompt = promptParts.join('\n\n');

  return {
    name: name,
    role: role,
    desc: shortDesc,
    greeting: rawGreeting,
    personality: fullPrompt,
    raw_personality: rawPers,
    raw_description: rawDesc,
    scenario: rawScenario,
    example_dialogue: rawExamples,
    avatar_url: rawAvatar,
    tags: tags
  };
}

async function applyCardToDeskSettings(card) {
  if (!card) return;
  if (currentBot) {
    currentBot.bot_name = card.name || currentBot.bot_name;
    if (!currentBot.settings) currentBot.settings = getDefaultSettings();
    currentBot.settings.personality = card.personality || currentBot.settings.personality;
    currentBot.settings.desc = card.desc || currentBot.settings.desc;
    currentBot.settings.greeting = card.greeting || currentBot.settings.greeting;
    if (card.avatar_url) {
      currentBot.settings.avatar_url = card.avatar_url;
      currentBot.settings.pfp = card.avatar_url;
    }
    renderSettings(currentBot);
    showDashboard(currentBot);
    await saveSettings();
    updateTerminal('Imported character: ' + card.name, 'Personality & Avatar applied to bot', 'Synced');
    showToast(`✓ Imported character "${card.name}" into bot settings!`);
  } else {
    updateTerminal('Card imported: ' + card.name, 'Connect a bot token to activate this persona', '');
    showToast(`✓ Character "${card.name}" loaded! Connect a bot token to apply.`);
    openPaperByClass('paper-top');
  }
}

async function handleDeskCardFileUpload(e) {
  const file = e.target ? (e.target.files && e.target.files[0]) : e;
  if (!file) return;

  const fname = file.name || 'character_card';
  const ext = fname.toLowerCase().slice(fname.lastIndexOf('.'));
  showToast(`Reading character file: ${fname}...`);

  if (ext === '.json') {
    try {
      const text = await file.text();
      const rawJson = JSON.parse(text);
      const card = parseCharacterCardData(rawJson, fname);
      if (card) {
        await applyCardToDeskSettings(card);
      } else {
        showToast('Could not find character fields in JSON.');
      }
    } catch (err) {
      showToast('Error reading JSON: ' + err.message);
    }
  } else if (ext === '.png') {
    try {
      const arrayBuffer = await file.arrayBuffer();
      const chunks = extractPngTextChunks(arrayBuffer);
      let cardData = null;
      if (chunks) {
        const rawJsonStr = chunks.chara || chunks.ccv3 || chunks.character;
        if (rawJsonStr) {
          try { cardData = JSON.parse(rawJsonStr); } catch (pe) {}
        }
      }
      if (cardData) {
        const card = parseCharacterCardData(cardData, fname);
        await applyCardToDeskSettings(card);
      } else {
        showToast(`Loaded PNG "${fname}" (No embedded character card found).`);
      }
    } catch (err) {
      showToast('Error processing PNG: ' + err.message);
    }
  }
  if (e.target && e.target.value) e.target.value = '';
}

async function pullDeskPersonalityFromWiki(inputElemId = 'deskWikiUrlInput') {
  const inp = $(inputElemId) || $('deskWikiUrlInput') || $('deskWikiUrlInput2');
  const url = inp ? inp.value.trim() : '';
  if (!url) {
    showToast('Enter a wiki or character link first');
    if (inp) inp.focus();
    return;
  }

  showToast('Fetching wiki lore and generating personality...');
  updateTerminal('Pulling lore from URL...', url.slice(0, 45) + '...', '');

  try {
    const res = await fetch('/api/pull_personality', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (data && data.ok && data.character) {
      await applyCardToDeskSettings(data.character);
      showToast(`✓ Synthesized character "${data.character.name}" from Wiki!`);
    } else {
      const wikiMatch = url.match(/wikipedia\.org\/wiki\/([^#?]+)/i);
      if (wikiMatch) {
        const pageTitle = decodeURIComponent(wikiMatch[1]);
        const wres = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(pageTitle)}`);
        if (wres.ok) {
          const wdata = await wres.json();
          const wtitle = wdata.title || pageTitle.replace(/_/g, ' ');
          const wextract = wdata.extract || '';
          const wimg = (wdata.originalimage || wdata.thumbnail || {}).source || '';
          const fallbackCard = {
            name: wtitle,
            role: 'Historical / Character Persona',
            desc: wextract.slice(0, 140),
            greeting: `*looks up and greets you calmly* Greetings. I am ${wtitle}.`,
            personality: `[Character: ${wtitle}]\n[Lore & Background:\n${wextract}]`,
            avatar_url: wimg
          };
          await applyCardToDeskSettings(fallbackCard);
          showToast(`✓ Pulled Wikipedia summary for "${wtitle}"!`);
          return;
        }
      }
      throw new Error((data && data.error) || 'Failed to extract lore from link');
    }
  } catch (err) {
    showToast('Pull failed: ' + err.message);
    updateTerminal('Pull lore error', err.message, '');
  }
}

/* ---------- PAPER UI ---------- */
function openPaperByClass(cls) {
  const el = document.querySelector("." + cls);
  if(!el) return;
  if(openPaperEl && openPaperEl !== el) closePaper(openPaperEl);
  if(el.classList.contains("open")) return;
  el.classList.add("open");
  el.classList.remove("pulled");
  $("backdrop").classList.add("active");
  $("editorDesk").classList.add("pushed");
  openPaperEl = el;
}
function closePaper(el) {
  if(!el) return;
  el.classList.remove("open");
  el.classList.add("pulled");
  setTimeout(function(){ el.classList.remove("pulled"); }, 400);
}
function closeAllPapers() {
  document.querySelectorAll(".paper.open").forEach(function(p){ closePaper(p); });
  $("backdrop").classList.remove("active");
  $("editorDesk").classList.remove("pushed");
  openPaperEl = null;
}

document.querySelectorAll(".paper").forEach(function(p){
  p.addEventListener("click", function(e){
    if(e.target.classList.contains("paper-close") || (e.target.parentElement && e.target.parentElement.classList.contains("paper-close"))) {
      e.stopPropagation();
      closePaper(p);
      if(openPaperEl === p) {
        openPaperEl = null;
        $("backdrop").classList.remove("active");
        $("editorDesk").classList.remove("pushed");
      }
      return;
    }
    if(p.classList.contains("open")) return;
    if(openPaperEl && openPaperEl !== p) closePaper(openPaperEl);
    p.classList.add("open");
    p.classList.remove("pulled");
    $("backdrop").classList.add("active");
    $("editorDesk").classList.add("pushed");
    openPaperEl = p;
  });
});
$("backdrop").addEventListener("click", closeAllPapers);
document.addEventListener("keydown", function(e){
  if(e.key === "Escape" && openPaperEl) {
    closePaper(openPaperEl);
    openPaperEl = null;
    $("backdrop").classList.remove("active");
    $("editorDesk").classList.remove("pushed");
  }
});

/* ---------- INIT ---------- */
(function init(){
  const savedSession = localStorage.getItem("sb_session");
  if(savedSession) {
    try {
      currentSession = JSON.parse(savedSession);
      $("authOverlay").style.display = "none";
      loadBots();
    } catch(e) { localStorage.removeItem("sb_session"); }
  }
})();
</script>
</body>
"""

# --- MAIN RUNNER --------------------------------------

def run_flask():
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    threading.Thread(target=run_flask, daemon=True).start()

    async def startup():
        global bot_loop
        bot_loop = asyncio.get_running_loop()
        await manager.load_all()
        if SUPABASE_URL and SUPABASE_SERVICE_KEY:
            print(f"[MAIN] Starting Supabase bridge: {SUPABASE_URL}")
            asyncio.create_task(bridge.start())
        else:
            print("[MAIN] Supabase bridge disabled.")
        await manager.run()

    try:
        bot_loop.run_until_complete(startup())
    except KeyboardInterrupt:
        print("[MAIN] Shutting down...")
    finally:
        bridge.stop()
        bot_loop.close()

