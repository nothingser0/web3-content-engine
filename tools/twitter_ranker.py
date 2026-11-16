#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter Data Parser & AI Ranker
Parse twitter-output/*.txt and rank by engagement + relevance
"""

import json
import sys
import io
import os
import re
import time
import requests
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    os.system('chcp 65001 > nul 2>&1')

def safe_print(text: str) -> str:
    """Sanitize unicode for Windows console - encode to ASCII with fallback"""
    try:
        # Try to encode as ASCII, replace problematic chars with '?'
        return text.encode('ascii', errors='replace').decode('ascii')
    except:
        # If even that fails, strip all non-ASCII
        return ''.join(c if ord(c) < 128 else '?' for c in text)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

NICHE_PRIORITY_KEYWORDS = {
    # Airdrop & Farming (high priority)
    "airdrop": 2,
    "retrodrop": 2,
    "retroactive": 2,
    "testnet": 2,
    "farming": 1,
    "snapshot": 1,
    "eligible": 2,
    "eligibility": 2,
    "allocation": 2,
    "claim": 1,
    "quest": 1,
    "whitelist": 1,
    "points": 2,
    "early adopter": 2,
    "og": 1,
    "contributor": 1,
    
    # Security & Due Diligence (high priority)
    "wallet": 2,
    "sybil": 2,
    "drain": 2,
    "phishing": 2,
    "scam": 2,
    "security": 2,
    "audit": 2,
    "rugcheck": 2,
    "rug pull": 2,
    "multi-sig": 2,
    "multisig": 2,
    "contract": 1,
    "smart contract": 1,
    "kyc": 1,
    "seed phrase": 2,
    "private key": 2,
    "2fa": 1,
    "authenticator": 1,
    "hardware wallet": 2,
    "cold wallet": 2,
    
    # Research & Analysis (high priority)
    "tokenomics": 2,
    "vesting": 2,
    "checklist": 2,
    "framework": 2,
    "dyor": 2,
    "research": 2,
    "risk": 2,
    "review": 2,
    "evaluate": 2,
    "evaluation": 2,
    "due diligence": 2,
    "analysis": 1,
    "red flag": 2,
    "warning sign": 2,
    
    # DeFi & Technical (medium priority)
    "tvl": 1,
    "defi": 1,
    "yield": 1,
    "apy": 1,
    "apr": 1,
    "liquidity": 1,
    "liquidity pool": 1,
    "staking": 1,
    "stake": 1,
    "validator": 1,
    "governance": 1,
    "proposal": 1,
    "dao": 1,
    "dex": 1,
    "cex": 1,
    "impermanent loss": 2,
    "slippage": 1,
    "arbitrage": 1,
    "mev": 1,
    "sandwich attack": 2,
    "front-run": 2,
    "swap": 1,
    "pool": 1,
    
    # Major Protocols & DEXs (low priority)
    "uniswap": 1,
    "pancakeswap": 1,
    "curve": 1,
    "aave": 1,
    "compound": 1,
    "sushiswap": 1,
    
    # Blockchain & Infrastructure (medium priority)
    "onchain": 1,
    "on-chain": 1,
    "bridge": 1,
    "mainnet": 1,
    "layer-2": 1,
    "layer 1": 1,
    "l1": 1,
    "l2": 1,
    "zk": 1,
    "rollup": 1,
    "optimistic": 1,
    "zk-rollup": 1,
    "evm": 1,
    "gas optimization": 2,
    "gas fee": 1,
    "gas war": 1,
    "priority fee": 1,
    "base fee": 1,
    "transaction": 1,
    "block": 1,
    "consensus": 1,
    "merkle tree": 1,
    "signature": 1,
    
    # Major Chains (low priority)
    "ethereum": 1,
    "solana": 1,
    "arbitrum": 1,
    "optimism": 1,
    "base": 1,
    "zksync": 1,
    "linea": 1,
    "scroll": 1,
    "polygon": 1,
    "cosmos": 1,
    "avalanche": 1,
    "sui": 1,
    "aptos": 1,
    "sei": 1,
    
    # Wallet Tools (low priority)
    "metamask": 1,
    "rabby": 1,
    "argent": 1,
    "safe": 1,
    "gnosis": 1,
    "ledger": 1,
    "trezor": 1,
    
    # Community & Participation (low priority)
    "discord": 1,
    "telegram": 1,
    "community": 1,
    "contributor": 1,
    "builder": 1,
    
    # Metrics & Analysis (low priority)
    "volume": 1,
    "market cap": 1,
    "mcap": 1,
    "fdv": 1,
    "fully diluted": 1,
    "circulating supply": 1,
    "total supply": 1,
    
    # NFT & Web3 Concepts (low priority)
    "nft": 1,
    "mint": 1,
    "metadata": 1,
    "opensea": 1,
    "collection": 1,
}

GENERIC_LOW_SIGNAL_KEYWORDS = {
    # Political & Macro Noise (high penalty)
    "trump": 4,
    "biden": 4,
    "democrat": 4,
    "republican": 4,
    "white house": 4,
    "election": 4,
    "fed": 3,
    "federal reserve": 3,
    "iran": 3,
    "russia": 3,
    "china": 3,
    "sec": 2,  # SEC bisa relevant, tapi sering noise
    
    # Traditional Finance Noise (medium penalty)
    "stock market": 3,
    "stocks": 2,
    "nasdaq": 2,
    "dow jones": 3,
    "s&p 500": 3,
    "oil": 3,
    "gold": 2,
    "commodities": 2,
    
    # Celebrity Noise (medium penalty)
    "tesla": 3,
    "elon musk": 3,
    "elon": 2,
    "mark cuban": 2,
    "peter thiel": 2,
    
    # Sports & Entertainment (medium penalty)
    "world cup": 2,
    "football": 2,
    "soccer": 2,
    "nba": 2,
    "super bowl": 2,
    
    # Gaming Noise (high penalty - NOT crypto related)
    "players online": 5,
    "gaming": 3,
    "video game": 4,
    "game server": 4,
    "esports": 3,
    "twitch": 2,
    "steam": 2,
    
    # Bot/AI Account Noise (high penalty - low quality content)
    "grok": 4,
    "@grok": 5,
    "ra-thor": 4,
    "agsi mode": 5,
    
    # Breaking News Noise (medium penalty)
    "breaking": 3,
    "just in": 2,
    "master accounts": 3,
    "exclusive": 2,
    
    # Low-Signal Price Talk (medium penalty)
    "bullish": 2,
    "bearish": 2,
    "pump": 2,
    "dump": 2,
    "price action": 2,
    "recovery": 2,
    "risk-on": 4,
    "risk-off": 3,
    "flows are flowing": 4,
    "binance": 2,
    "coinbase": 2,
    "kraken": 2,
    
    # Meme/Hype Noise (low penalty - might be cultural)
    "moon": 2,
    "to the moon": 3,
    "lambo": 2,
    "when lambo": 3,
    "hodl": 2,
    "diamond hands": 2,
    "paper hands": 2,
    "wagmi": 2,
    "ngmi": 2,
    "lfg": 2,
    "gm": 1,
    "gn": 1,
    "ser": 1,
    "anon": 1,
    
    # Motivational Fluff (low penalty)
    "follow your dreams": 2,
    "never give up": 2,
    "believe in yourself": 2,
    "stay positive": 1,
    "manifest": 2,
    
    # Generic Business Buzzwords (low penalty)
    "announcement": 1,
    "big news": 2,
    "huge announcement": 3,
    "major update": 2,
    
    # Vague Time Phrases (low penalty)
    "soon": 1,
    "coming soon": 2,
    "wait for it": 2,
    "stay tuned": 1,
    "any day now": 2,
    
    # Vague Phrases (low penalty)
    "all these happened": 2,
    "just saying": 1,
    "iykyk": 1,
    "ngl": 1,
}

PROMO_SPAM_KEYWORDS = {
    # Direct Call-to-Action Spam (highest penalty)
    "join tg": 5,
    "join telegram": 5,
    "dm for": 5,
    "dm me": 5,
    "dm for details": 6,
    "check dm": 5,
    "link in bio": 5,
    "link below": 4,
    "click link": 4,
    "guaranteed distribution": 6,
    "airdrop bot": 5,
    "post proof": 5,
    "register now": 5,
    "sign up now": 5,
    "join now": 5,
    "apply now": 4,
    "whitelist open": 5,
    "form open": 4,
    
    # Money/Investment Scams (highest penalty)
    "send eth": 6,
    "send sol": 6,
    "send usdt": 6,
    "send to wallet": 6,
    "double your": 6,
    "triple your": 6,
    "multiply your": 6,
    "guaranteed profit": 6,
    "guaranteed returns": 6,
    "fixed returns": 6,
    "daily profit": 5,
    "daily returns": 5,
    "passive income": 4,
    "easy money": 5,
    "make money fast": 5,
    "get rich": 5,
    "financial freedom": 4,
    
    # Unrealistic Hype (high penalty)
    "100x gem": 6,
    "1000x": 6,
    "10000x": 6,
    "100x potential": 5,
    "1000x potential": 6,
    "pump incoming": 5,
    "next bitcoin": 5,
    "next eth": 5,
    "next solana": 5,
    "next bnb": 5,
    "moonshot": 4,
    "rocket": 3,
    "parabolic": 4,
    
    # Pump & Dump Coordination (highest penalty)
    "pump group": 6,
    "pump and dump": 6,
    "coordinated buy": 6,
    "buy signal": 5,
    "sell signal": 5,
    "entry point": 4,
    "take profit": 3,
    "stop loss": 3,
    
    # Artificial Urgency/Scarcity (high penalty)
    "limited spots": 5,
    "only 100 spots": 6,
    "50 spots left": 5,
    "last chance": 5,
    "final call": 5,
    "don't miss": 4,
    "don't miss out": 5,
    "act fast": 4,
    "act now": 5,
    "ending soon": 4,
    "ends today": 5,
    "only today": 5,
    "24 hours left": 4,
    "hurry": 4,
    "rush": 4,
    "quick": 3,
    "early access": 4,
    "exclusive access": 4,
    "vip access": 5,
    
    # Reward/Prize Spam (high penalty)
    "free token": 5,
    "free tokens": 5,
    "free crypto": 5,
    "free money": 6,
    "reward pool": 4,
    "prize pool": 4,
    "winners": 4,
    "win prizes": 4,
    "giveaway": 5,
    "airdrop giveaway": 5,
    "nft giveaway": 4,
    
    # Investment/Trading Spam (medium-high penalty)
    "guaranteed": 4,
    "risk free": 5,
    "no risk": 5,
    "zero risk": 5,
    "safe investment": 4,
    "presale": 4,
    "private sale": 5,
    "seed round": 3,
    "public sale": 3,
    "ico": 3,
    "ido": 3,
    "ieo": 3,
    "fair launch": 3,
    
    # Signal Group Spam (high penalty)
    "vip group": 5,
    "premium group": 5,
    "premium channel": 5,
    "paid group": 4,
    "paid channel": 4,
    "signal group": 5,
    "signals group": 5,
    "trading signals": 4,
    "crypto signals": 4,
    "alpha group": 4,
    "insider info": 5,
    "insider tips": 5,
    
    # MLM/Pyramid Schemes (high penalty)
    "earn passive": 4,
    "passive earning": 4,
    "work from home": 4,
    "make money online": 5,
    "side hustle": 3,
    "referral bonus": 4,
    "invite friends": 4,
    "bring friends": 4,
    "recruit": 5,
    "downline": 6,
    "upline": 6,
    "mlm": 6,
    "network marketing": 5,
    
    # Social Engagement Spam (medium penalty)
    "follow": 3,
    "follow me": 4,
    "follow for": 4,
    "rt &": 4,
    "retweet and": 4,
    "retweet for": 4,
    "like and": 3,
    "like for": 4,
    "tag friends": 4,
    "tag 3 friends": 5,
    "mention friends": 4,
    "share and": 3,
    "referrers": 5,
    "referral code": 3,
    "use code": 3,
    "promo code": 4,
    
    # Disclaimer Spam (low penalty - might be legitimate)
    "nfa": 3,
    "dyor": 2,  # Lower penalty, DYOR is good practice
    "ad, nfa": 4,
    "not financial advice": 2,
    "financial advice": 3,
    "sponsored": 3,
    "paid promotion": 4,
    
    # Contract Address Spam (low penalty)
    "ca (": 3,
    "ca:": 3,
    "contract:": 2,
    "contract address": 2,
    "token address": 2,
    
    # Website/External Links (low penalty)
    "visit website": 3,
    "check website": 3,
    "website link": 3,
    "official website": 2,
}

def load_config():
    """Load project API config."""
    from src.utils.config import load_api_config

    return load_api_config()


def get_ranker_model():
    from src.utils.config import STRATEGIST_MODEL_PRIMARY

    return os.getenv("TWITTER_RANKER_MODEL") or STRATEGIST_MODEL_PRIMARY

def call_llm_with_retry(api_url, api_key, payload, max_retries=3, timeout=600):
    """
    Call LLM API with retry logic and exponential backoff
    
    Args:
        api_url: API base URL
        api_key: API key
        payload: Request payload dict
        max_retries: Maximum retry attempts (default: 3)
        timeout: Request timeout in seconds (default: 600)
    
    Returns:
        Response content string or None on failure
    """
    def calculate_backoff(attempt):
        """Calculate exponential backoff delay"""
        return min(2 ** attempt, 60)  # Max 60 seconds
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            print(f"[*] API call attempt {attempt + 1}/{max_retries}", file=sys.stderr)
            
            response = requests.post(
                f"{api_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                json=payload,
                timeout=timeout
            )
            
            # Success
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    print(f"[!] Empty response from API", file=sys.stderr)
                    return None
                print(f"[*] API call successful", file=sys.stderr)
                return content
            
            # Rate limit - always retry
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', calculate_backoff(attempt)))
                print(f"[!] Rate limited. Retrying after {retry_after}s", file=sys.stderr)
                time.sleep(retry_after)
                continue
            
            # Server errors - retry
            elif 500 <= response.status_code < 600:
                backoff = calculate_backoff(attempt)
                print(f"[!] Server error {response.status_code}. Retrying after {backoff}s", file=sys.stderr)
                time.sleep(backoff)
                continue
            
            # Client errors - don't retry (except 429 above)
            else:
                print(f"[!] API error {response.status_code}: {response.text}", file=sys.stderr)
                return None
        
        except requests.exceptions.Timeout:
            backoff = calculate_backoff(attempt)
            print(f"[!] Request timeout. Retrying after {backoff}s", file=sys.stderr)
            time.sleep(backoff)
            last_error = "Request timeout"
            continue
        
        except requests.exceptions.ConnectionError as e:
            backoff = calculate_backoff(attempt)
            print(f"[!] Connection error: {e}. Retrying after {backoff}s", file=sys.stderr)
            time.sleep(backoff)
            last_error = str(e)
            continue
        
        except Exception as e:
            print(f"[!] Unexpected error: {e}", file=sys.stderr)
            last_error = str(e)
            break
    
    # All retries exhausted
    print(f"[!] API call failed after {max_retries} attempts. Last error: {last_error}", file=sys.stderr)
    return None

def parse_number(text):
    """Parse number with 'rb', 'jt' suffix"""
    text = text.replace('\xa0', ' ').strip().lower()
    text = re.sub(r'\s+', ' ', text)
    
    if 'jt' in text:
        # Million
        num = float(re.sub(r'[^0-9.]', '', text))
        return int(num * 1_000_000)
    elif 'rb' in text:
        # Thousand
        num = float(re.sub(r'[^0-9.]', '', text))
        return int(num * 1_000)
    else:
        # Regular number
        return int(re.sub(r'[^0-9]', '', text)) if re.search(r'\d', text) else 0

def parse_twitter_file(filepath):
    """Parse twitter output file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by separator
    posts = re.split(r'─{50,}', content)
    
    parsed_posts = []
    
    for post in posts:
        if not post.strip() or 'DATA TWITTER:' in post:
            continue
        
        # Extract fields
        username_match = re.search(r'(?m)^Username\s*:\s*(.+?)\s*$', post)
        metrics_match = re.search(
            r'(?m)^Retweets\s*:\s*([^|\r\n]+?)\s*\|\s*Likes:\s*([^|\r\n]+?)\s*\|\s*Views:\s*([^\r\n]+?)\s*$',
            post,
        )
        kategori_match = re.search(r'(?m)^Kategori\s*:\s*(.+?)\s*$', post)
        link_match = re.search(r'(?m)^Link\s*:\s*(.+?)\s*$', post)
        
        # Extract text (after "Teks Post:")
        text_match = re.search(r'(?s)Teks Post\s*:\s*\n?(.*)$', post)
        
        if not text_match:
            continue
        
        text = text_match.group(1).strip()
        
        # Skip if text too short
        if len(text) < 20:
            continue
        
        # Parse engagement metrics
        retweets = parse_number(metrics_match.group(1)) if metrics_match else 0
        likes = parse_number(metrics_match.group(2)) if metrics_match else 0
        views = parse_number(metrics_match.group(3)) if metrics_match else 0
        
        parsed_posts.append({
            'username': username_match.group(1).strip() if username_match else 'Unknown',
            'text': text,
            'retweets': retweets,
            'likes': likes,
            'views': views,
            'kategori': kategori_match.group(1).strip() if kategori_match else 'Unknown',
            'link': link_match.group(1).strip() if link_match else ''
        })
    
    return parsed_posts

def calculate_engagement_score(post):
    """Calculate engagement score (0-10)"""
    # Weighted scoring
    retweet_score = min(post['retweets'] / 100, 3)  # Max 3 points
    like_score = min(post['likes'] / 500, 4)        # Max 4 points
    view_score = min(post['views'] / 10000, 3)      # Max 3 points
    
    total = retweet_score + like_score + view_score
    return round(min(total, 10), 2)


def calculate_niche_relevance_score(post):
    """Score how useful post is for Web3/airdrop content sourcing."""
    text = post['text'].lower()
    category = str(post.get('kategori', '')).lower()

    score = 0

    for keyword, weight in NICHE_PRIORITY_KEYWORDS.items():
        if keyword in text:
            score += weight

    for keyword, weight in GENERIC_LOW_SIGNAL_KEYWORDS.items():
        if keyword in text:
            score -= weight

    for keyword, weight in PROMO_SPAM_KEYWORDS.items():
        if keyword in text:
            score -= weight

    if category in {"testnet", "holder"}:
        score += 0
    elif category == "giveaway":
        score -= 6

    if any(keyword in text for keyword in ("reward pool", "winners", "register now", "join now", "free token", "claim now")):
        score -= 5

    if any(keyword in text for keyword in ("tokenomics", "checklist", "framework", "dyor", "red flag", "risk", "evaluate", "evaluation")):
        score += 3

    if any(keyword in text for keyword in ("price", "bullish", "risk-on", "binance", "pump", "recovery")) and not any(keyword in text for keyword in ("checklist", "framework", "red flag", "tokenomics", "risk review")):
        score -= 4

    if "http://" in text or "https://" in text:
        score -= 1

    if text.count("@")==0 and text.count("$") == 0 and len(text) < 120:
        score -= 1

    if any(keyword in text for keyword in ("how to", "guide", "checklist", "template", "red flag")):
        score += 2

    return score


def calculate_final_rank_score(post):
    """Blend niche relevance first, engagement second."""
    niche_score = post.get('niche_score', 0)
    engagement_score = post.get('engagement_score', 0)
    return round((niche_score * 1.8) + engagement_score, 2)

def classify_pillar_fast(text):
    """Fast keyword-based pillar classification with priority ordering"""
    text_lower = text.lower()
    
    # PRIORITY 1: Campaign Review (most specific - airdrop farming)
    airdrop_keywords = ["airdrop", "snapshot", "claim", "farming", "testnet", "whitelist", "allocation", "eligible", "retrodrop"]
    if any(kw in text_lower for kw in airdrop_keywords):
        # Determine sub-angle
        if any(kw in text_lower for kw in ["before", "eligibility", "criteria", "qualify", "prepare"]):
            return "campaign_review", "before"
        elif any(kw in text_lower for kw in ["farming", "strategy", "optimize", "gas", "progress"]):
            return "campaign_review", "during"
        elif any(kw in text_lower for kw in ["review", "worth", "roi", "result", "got $"]):
            return "campaign_review", "after"
        elif any(kw in text_lower for kw in ["skip", "avoid", "not worth", "waste"]):
            return "campaign_review", "skip"
        elif any(kw in text_lower for kw in ["zonk", "failed", "nothing", "$0", "rugi"]):
            return "campaign_review", "zonk"
        else:
            return "campaign_review", "general"
    
    # PRIORITY 2: Edukasi Web3 - Security & Warnings (before Storytelling to catch scam warnings)
    security_keywords = ["wallet", "ledger", "trezor", "metamask", "seed phrase", "private key", "phishing", "drain", "security", "custody", "hardware wallet", "cold wallet"]
    warning_keywords = ["red flag", "warning", "scam wave", "scam alert", "avoid", "danger", "risk", "be careful"]
    
    if any(kw in text_lower for kw in security_keywords + warning_keywords):
        # This is security/warning content - ALWAYS edukasi_web3
        if any(kw in text_lower for kw in ["red flag", "warning", "scam", "phishing", "avoid", "danger"]):
            return "edukasi_web3", "warning"
        elif any(kw in text_lower for kw in ["how to", "tutorial", "guide", "step"]):
            return "edukasi_web3", "how_to"
        elif any(kw in text_lower for kw in ["beginner", "basics", "what is", "introduction"]):
            return "edukasi_web3", "basics"
        else:
            return "edukasi_web3", "general"
    
    # PRIORITY 3: Storytelling (personal experience)
    story_keywords = ["lost", "made $", "profit", "rug pull", "rugpull", "hacked", "exploit", "journey", "mistake", "lesson learned"]
    if any(kw in text_lower for kw in story_keywords):
        if any(kw in text_lower for kw in ["made $", "profit", "success", "won", "gained"]):
            return "storytelling", "win"
        elif any(kw in text_lower for kw in ["lost", "hacked", "exploit"]):
            return "storytelling", "loss"
        elif any(kw in text_lower for kw in ["journey", "year", "started", "evolution"]):
            return "storytelling", "journey"
        elif any(kw in text_lower for kw in ["mistake", "error", "wrong", "regret"]):
            return "storytelling", "mistake"
        elif any(kw in text_lower for kw in ["lesson", "learned", "advice", "wisdom"]):
            return "storytelling", "lesson"
        else:
            return "storytelling", "general"
    
    # PRIORITY 4: AI Tools (now more restrictive - require AI + crypto context)
    ai_core_keywords = ["chatgpt", "claude", "gpt-4", "gpt-5", "gemini", "perplexity"]
    ai_generic_keywords = ["ai", "artificial intelligence", "machine learning"]
    crypto_context = ["crypto", "blockchain", "web3", "defi", "trading", "research", "airdrop", "analysis"]
    
    # Strong match: specific AI tool mentioned
    if any(kw in text_lower for kw in ai_core_keywords):
        if any(kw in text_lower for kw in ["review", "tested", "comparison", "best", "vs"]):
            return "ai_tools", "review"
        elif any(kw in text_lower for kw in ["tutorial", "how to", "guide", "step", "use"]):
            return "ai_tools", "tutorial"
        elif any(kw in text_lower for kw in crypto_context):
            return "ai_tools", "ai_crypto"
        elif any(kw in text_lower for kw in ["won't replace", "can't", "limitation", "risk"]):
            return "ai_tools", "hot_take"
        else:
            return "ai_tools", "general"
    
    # Weak match: generic "ai" but only if crypto context present
    if any(kw in text_lower for kw in ai_generic_keywords) and any(kw in text_lower for kw in crypto_context):
        if any(kw in text_lower for kw in crypto_context):
            return "ai_tools", "ai_crypto"
        else:
            return "ai_tools", "general"
    
    # PRIORITY 5: Edukasi Web3 - General educational content
    edu_keywords = ["tutorial", "guide", "how to", "beginner", "explain", "what is", "term", "glossary"]
    if any(kw in text_lower for kw in edu_keywords):
        if any(kw in text_lower for kw in ["beginner", "basics", "what is", "introduction"]):
            return "edukasi_web3", "basics"
        elif any(kw in text_lower for kw in ["term", "glossary", "definition", "meaning"]):
            return "edukasi_web3", "glossary"
        elif any(kw in text_lower for kw in ["how to", "tutorial", "guide", "step"]):
            return "edukasi_web3", "how_to"
        else:
            return "edukasi_web3", "general"
    
    # PRIORITY 6: Market Takes
    market_keywords = ["bitcoin", "btc", "eth", "price", "market", "bull", "bear", "altseason", "prediction"]
    if any(kw in text_lower for kw in market_keywords):
        if any(kw in text_lower for kw in ["this week", "recap", "summary", "update"]):
            return "market_takes", "weekly_recap"
        elif any(kw in text_lower for kw in ["watching", "list", "projects"]):
            return "market_takes", "watchlist"
        elif any(kw in text_lower for kw in ["analysis", "indicator", "signal", "sentiment"]):
            return "market_takes", "opini"
        elif any(kw in text_lower for kw in ["prediction", "forecast", "target", "will"]):
            return "market_takes", "prediksi"
        else:
            return "market_takes", "general"
    
    # Default
    return "general", "general"

def rank_posts_with_ai(posts):
    """Rank posts using AI (relevance + engagement)"""
    api_url, api_key = load_config()
    
    # For large volumes (200-400), do pre-filtering by engagement first
    if len(posts) > 50:
        print(f"[*] Large volume detected ({len(posts)} posts), pre-filtering by engagement...", file=sys.stderr)
        # Sort by engagement and take top 50
        posts_sorted = sorted(posts, key=lambda x: x.get('engagement_score', 0), reverse=True)
        posts_to_score = posts_sorted[:50]
        print(f"[*] Pre-filtered to top 50 by engagement", file=sys.stderr)
    else:
        posts_to_score = posts
    
    posts_text = ""
    for i, post in enumerate(posts_to_score, 1):
        eng_score = post.get('engagement_score', calculate_engagement_score(post))
        posts_text += f"\n[{i}] @{post['username']}\n"
        posts_text += f"    Engagement: {post['retweets']} RT | {post['likes']} Likes | {post['views']} Views (Score: {eng_score}/10)\n"
        posts_text += f"    Text: {post['text'][:150]}...\n"
    
    prompt = (Path(__file__).resolve().parent.parent / "prompts" / "twitter" / "twitter_ranker.txt").read_text(
        encoding="utf-8"
    ).format(post_count=len(posts_to_score), posts_text=posts_text)

    try:
        payload = {
            "model": get_ranker_model(),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 3000,
            "temperature": 0.3
        }
        
        content = call_llm_with_retry(api_url, api_key, payload, max_retries=3, timeout=600)
        
        if not content:
            return None
        
        # Parse scores
        scores = []
        for line in content.split('\n'):
            if re.match(r'\[\d+\]', line):
                try:
                    score_match = re.search(r'SCORE:\s*(\d+)', line)
                    pillar_match = re.search(r'PILLAR:\s*(\w+)', line)
                    sub_match = re.search(r'SUB:\s*(\w+)', line)
                    reason_match = re.search(r'REASON:\s*(.+)', line)
                    
                    if score_match and pillar_match and reason_match:
                        scores.append({
                            'score': int(score_match.group(1)),
                            'pillar': pillar_match.group(1),
                            'sub_angle': sub_match.group(1) if sub_match else 'general',
                            'reason': reason_match.group(1).strip()
                        })
                except (ValueError, AttributeError) as e:
                    print(f"[!] Failed to parse AI score line: {e}", file=sys.stderr)
                    continue
        
        # If we pre-filtered, map scores back to original posts
        if len(posts) > 50:
            # Create score map for top 50
            score_map = {i: scores[i] if i < len(scores) else None for i in range(len(posts_to_score))}
            # Return scores for all posts (None for non-scored)
            all_scores = []
            for post in posts:
                if post in posts_to_score:
                    idx = posts_to_score.index(post)
                    all_scores.append(score_map.get(idx))
                else:
                    all_scores.append(None)
            return all_scores
        
        return scores
        
    except Exception as e:
        print(f"[!] AI Ranking Error: {e}", file=sys.stderr)
        return None

def main():
    """Main function"""
    print("=" * 60, file=sys.stderr)
    print("TWITTER DATA PARSER & AI RANKER", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    # Get input file
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        print("[!] Usage: python twitter_ranker.py <twitter_output.txt>", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(input_file):
        print(f"[!] File not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[*] Parsing: {input_file}", file=sys.stderr)
    
    # Parse file
    posts = parse_twitter_file(input_file)
    
    print(f"[*] Found {len(posts)} posts", file=sys.stderr)
    
    if not posts:
        print("[!] No valid posts found", file=sys.stderr)
        sys.exit(1)
    
    # Calculate engagement scores and classify pillars (keyword-based, fast!)
    print(f"[*] Classifying pillars and calculating engagement...", file=sys.stderr)
    for post in posts:
        post['engagement_score'] = calculate_engagement_score(post)
        pillar, sub_angle = classify_pillar_fast(post['text'])
        post['pillar'] = pillar
        post['sub_angle'] = sub_angle
        post['niche_score'] = calculate_niche_relevance_score(post)
        post['final_rank_score'] = calculate_final_rank_score(post)
    
    # Sort by niche relevance first, engagement second.
    # Priority: non-general pillars first, higher niche score, then stronger engagement.
    posts.sort(
        key=lambda x: (
            0 if x['pillar'] != 'general' else 1,
            -x['niche_score'],
            -x['engagement_score'],
            -x['final_rank_score'],
        )
    )
    
    # FILTER 1: Only keep crypto-relevant posts (niche_score > 0)
    # This prevents high-engagement but off-topic content from being selected
    crypto_posts = [p for p in posts if p['niche_score'] > 0]
    
    if not crypto_posts:
        print(f"[!] No crypto-relevant posts found after filtering!", file=sys.stderr)
        print(f"[!] All {len(posts)} posts had niche_score <= 0", file=sys.stderr)
        sys.exit(1)
    
    print(f"[*] Filtered to {len(crypto_posts)} crypto-relevant posts (from {len(posts)} total)", file=sys.stderr)
    
    # FILTER 2: Minimum engagement threshold (prevents bot/spam noise)
    # Require: At least 5 RT OR 25 Likes OR 5000 Views
    MIN_RT = 5
    MIN_LIKES = 25
    MIN_VIEWS = 5000
    
    quality_posts = [
        p for p in crypto_posts 
        if p['retweets'] >= MIN_RT or p['likes'] >= MIN_LIKES or p['views'] >= MIN_VIEWS
    ]
    
    if not quality_posts:
        print(f"[!] No posts met minimum engagement threshold after filtering!", file=sys.stderr)
        print(f"[!] Minimum: {MIN_RT} RT OR {MIN_LIKES} Likes OR {MIN_VIEWS} Views", file=sys.stderr)
        print(f"[!] Falling back to crypto_posts without engagement filter", file=sys.stderr)
        quality_posts = crypto_posts  # Fallback to avoid empty results
    else:
        print(f"[*] Engagement filter: {len(quality_posts)} posts passed (from {len(crypto_posts)} crypto-relevant)", file=sys.stderr)
    
    # Use quality_posts for ranking
    crypto_posts = quality_posts
    
    # HYBRID AI RANKING: Keyword pre-filter + AI re-rank
    # Take top 50 by keyword score for AI evaluation (cost optimization)
    if len(crypto_posts) > 50:
        posts_for_ai = crypto_posts[:50]
        print(f"[*] Pre-selected top 50 by keyword score for AI re-ranking", file=sys.stderr)
    else:
        posts_for_ai = crypto_posts
    
    # AI re-ranking (context-aware, understands nuance)
    print(f"[*] Running AI re-ranking on {len(posts_for_ai)} posts...", file=sys.stderr)
    ai_scores = rank_posts_with_ai(posts_for_ai)
    
    if ai_scores:
        # Apply AI scores and blend with keyword scores
        for i, post in enumerate(posts_for_ai):
            if i < len(ai_scores) and ai_scores[i]:
                post['ai_score'] = ai_scores[i]['score']
                post['ai_pillar'] = ai_scores[i].get('pillar', post['pillar'])
                post['ai_sub_angle'] = ai_scores[i].get('sub_angle', post['sub_angle'])
                post['ai_reason'] = ai_scores[i]['reason']
                # Blended score: 40% keyword + 60% AI (prioritize AI for final ranking)
                post['total_score'] = round((post['final_rank_score'] * 0.4) + (ai_scores[i]['score'] * 0.6), 2)
                post['reason'] = post['ai_reason']
            else:
                # Fallback for posts without AI score
                post['ai_score'] = 5
                post['total_score'] = post['final_rank_score']
                post['reason'] = (
                    f"Keyword-only: Pillar={post['pillar']}; niche_score={post['niche_score']}; "
                    f"engagement_score={post['engagement_score']}"
                )
        
        # Re-sort by blended score (AI-weighted)
        posts_for_ai.sort(key=lambda x: -x.get('total_score', 0))
        top_10 = posts_for_ai[:10]
        print(f"[*] AI re-ranking completed successfully", file=sys.stderr)
    else:
        # Fallback to keyword-only if AI fails
        print(f"[!] AI re-ranking failed, falling back to keyword-only scores", file=sys.stderr)
        top_10 = crypto_posts[:10]
        for post in top_10:
            post['ai_score'] = 5  # Neutral (no AI scoring)
            post['reason'] = (
                f"Keyword-only: Pillar={post['pillar']}; niche_score={post['niche_score']}; "
                f"engagement_score={post['engagement_score']}"
            )
            post['total_score'] = post['final_rank_score']
    
    print(f"[*] Selected top {len(top_10)} posts for output", file=sys.stderr)
    
    for i, post in enumerate(top_10, 1):
        print(f"\n[{i}] {safe_print(post['text'][:80])}... - {post['total_score']}/10", file=sys.stderr)
        print(f"    @{safe_print(post['username'])}", file=sys.stderr)
        print(f"    Engagement: {post['retweets']} RT | {post['likes']} Likes | {post['views']} Views", file=sys.stderr)
        print(f"    Pillar: {safe_print(post['pillar'])} | Sub-angle: {safe_print(post.get('sub_angle', 'general'))}", file=sys.stderr)
        print(f"    Scores: AI={post['ai_score']}/10 | Keyword={post['final_rank_score']:.2f} | Niche={post['niche_score']} | Engagement={post['engagement_score']}", file=sys.stderr)
        print(f"    Reason: {safe_print(post['reason'])}", file=sys.stderr)
    
    print("\n" + "=" * 60, file=sys.stderr)
    
    # Output JSON for strategist
    output = []
    for i, post in enumerate(top_10, 1):
        output.append({
            'number': i,
            'text': post['text'],
            'context': f"Engagement: {post['retweets']} RT, {post['likes']} Likes, {post['views']} Views",
            'pillar': post['pillar'],
            'username': post['username'],
            'link': post['link'],
            'engagement': {
                'retweets': post['retweets'],
                'likes': post['likes'],
                'views': post['views']
            },
            'scores': {
                'ai_score': post['ai_score'],
                'niche_score': post['niche_score'],
                'engagement_score': post['engagement_score'],
                'total_score': post['total_score']
            }
        })
    
    print(json.dumps(output, indent=2, ensure_ascii=True))

if __name__ == "__main__":
    main()
