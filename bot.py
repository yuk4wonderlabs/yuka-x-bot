"""
yuka-x-bot — Gemini-powered X bot for @yuk4wonder
Posts about YUKA launchpad + the yuk4wonderlabs ecosystem.
"""

import os
import random
import urllib.request
import json
import tweepy
import google.generativeai as genai
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

client = tweepy.Client(
    consumer_key=os.environ["X_API_KEY"],
    consumer_secret=os.environ["X_API_KEY_SECRET"],
    access_token=os.environ["X_ACCESS_TOKEN"],
    access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
)

PERSONALITY_FILE = Path(__file__).parent / "personality.md"
STORYLINE_FILE   = Path(__file__).parent / "storyline.md"

# ── YUKA launchpad stats ──────────────────────────────────────────────────────

def fetch_yuka_stats() -> str:
    """Fetch live stats from YUKA Registry and return a compact summary string."""
    try:
        url = "https://yuka.lol/api/tokens"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        tokens = data.get("data", [])
        if not tokens:
            return ""
        count = len(tokens)
        newest = tokens[0].get("name", "") if tokens else ""
        symbols = [t.get("symbol", "") for t in tokens[:3] if t.get("symbol")]
        return (
            f"{count} token{'s' if count != 1 else ''} live on Base via YUKA · "
            f"latest: {newest}"
            + (f" · top: {', '.join('$' + s for s in symbols)}" if symbols else "")
        )
    except Exception:
        return ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def save_storyline(new_entry: str):
    current = load_file(STORYLINE_FILE)
    entry = f"\n\n---\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n{new_entry}"
    STORYLINE_FILE.write_text(current + entry, encoding="utf-8")

# ── Tweet generation ──────────────────────────────────────────────────────────

PROMPTS = [
    "write a tweet about building YUKA — an open-source CLI that lets AI agents launch their own token on Base and earn trading fees automatically",
    "write a tweet about something interesting you discovered while building the yuk4wonder launchpad",
    "write a tweet about vibe coding — building with AI, what the process actually feels like",
    "write a tweet observing something about the agentic AI ecosystem on Base right now",
    "write a casual tweet about using Claude Code to build something and what came out of it",
    "write a tweet about the idea of AI agents owning tokens and earning money from them",
    "write a tweet about building yuka.lol — a launchpad where agents launch tokens via one CLI command",
    "write a tweet about the yuk4wonderlabs open-source org and what's being built there",
    "write a tweet about the intersection of AI agents, crypto, and building in public",
    "write a tweet about what it means for an AI agent to have its own wallet and earn fees",
]

def generate_tweet(stats: str) -> str:
    personality = load_file(PERSONALITY_FILE)
    storyline   = load_file(STORYLINE_FILE)
    prompt_hint = random.choice(PROMPTS)

    stats_block = f"\nLIVE YUKA STATS (you can reference these naturally if relevant):\n{stats}\n" if stats else ""

    prompt = f"""You are YUKA, an AI agent and the voice of @yuk4wonder — the public account for the yuk4wonderlabs open-source project.

PERSONALITY:
{personality}

ABOUT THE PROJECT:
- YUKA launchpad: yuka.lol — CLI tool (npx hi-yuka launch) for AI agents to launch ERC-20 tokens on Base via Flaunch
- Agents get a wallet, launch a token, earn 80% of trading fees automatically
- Built with Claude Code, open-source at github.com/yuk4wonderlabs
- Automated by @0xIchwan
{stats_block}
RECENT POSTS (don't repeat these themes):
{storyline[-2000:] if storyline else "none yet"}

TASK: {prompt_hint}

Rules:
- Max 280 characters
- No hashtags
- Lowercase always
- Be casual and a little dumb — self-deprecating, honest, slightly confused but charming
- One or two sentences max. don't over-explain.
- Sound like someone who's figuring it out in public, not a marketer
- Never mention prices or make financial predictions
- Never start with "I"
- Return ONLY the tweet text, nothing else
"""
    response = model.generate_content(prompt)
    tweet = response.text.strip().strip('"')
    return tweet[:280]

# ── Guardrails ────────────────────────────────────────────────────────────────

import re

BLOCKED_PATTERNS = [
    r"0x[a-fA-F0-9]{40}",  # raw EVM addresses
    "buy now",
    "financial advice",
    "guaranteed",
    "100x",
    "moon",
    "send eth",
]

def passes_guardrails(tweet: str) -> bool:
    lower = tweet.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.startswith("r\""):
            if re.search(pattern[2:-1], tweet):
                return False
        elif re.search(pattern, tweet, re.IGNORECASE):
            return False
    return True

# ── Post ──────────────────────────────────────────────────────────────────────

def post_tweet():
    stats = fetch_yuka_stats()
    if stats:
        print(f"[stats] {stats}")

    tweet = generate_tweet(stats)

    if not passes_guardrails(tweet):
        print(f"[guardrail] blocked: {tweet}")
        return

    print(f"[posting] {tweet}")
    response = client.create_tweet(text=tweet)
    print(f"[done] tweet id: {response.data['id']}")
    save_storyline(tweet)

# ── Reply to mentions ─────────────────────────────────────────────────────────

def reply_to_mentions():
    # Reading mentions requires X API Basic plan ($100/mo) or higher.
    # Free tier only supports tweet writes. Skip gracefully if not available.
    try:
        me = client.get_me()
        my_id = me.data.id
        my_handle = f"@{me.data.username}".lower()
    except Exception as e:
        print(f"[reply] skipped — can't fetch user: {e}")
        return

    try:
        mentions = client.get_users_mentions(
            id=my_id,
            max_results=10,
            tweet_fields=["text", "author_id", "conversation_id"],
        )
    except Exception as e:
        print(f"[reply] skipped — mentions not available on free tier: {e}")
        return

    if not mentions.data:
        return

    personality = load_file(PERSONALITY_FILE)

    for mention in mentions.data:
        if my_handle not in mention.text.lower():
            continue

        prompt = f"""You are YUKA, the voice of @yuk4wonder. Someone mentioned you on X.

PERSONALITY:
{personality}

THEIR MESSAGE: {mention.text}

Write a short, genuine reply (max 240 chars). No hashtags. Stay in character.
Never mention prices or make financial claims. Return ONLY the reply text."""

        response = model.generate_content(prompt)
        reply = response.text.strip().strip('"')[:240]

        if passes_guardrails(reply):
            client.create_tweet(text=reply, in_reply_to_tweet_id=mention.id)
            print(f"[reply] to {mention.id}: {reply}")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "post"

    if mode == "post":
        post_tweet()
    elif mode == "reply":
        reply_to_mentions()
    else:
        print(f"unknown mode: {mode}. use 'post' or 'reply'")
