#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from pathlib import Path

def _load_env_files() -> None:
    env_candidates = [
        Path(__file__).parent.parent.parent / '.env',
        Path(__file__).parent.parent.parent / '.env.opencode',
    ]

    for env_file in env_candidates:
        if not env_file.exists():
            continue

        try:
            from dotenv import load_dotenv
            _ = load_dotenv(env_file, override=False)
        except Exception as e:
            print(f"[!] Warning: Could not load {env_file.name}: {e}")

_load_env_files()

DEFAULT_API_URL: str = "http://localhost:20128/v1"

EVERGREEN_CATEGORIES = [
    "Security & Scams",
    "Fundamental Skills",
    "Tool Reviews",
    "Case Studies",
    "Mindset & Strategy"
]

CONTENT_PILLARS = [
    "Onchain Identity & Reputation",
    "Campaign Evaluation & Risk Review",
    "Tools & Resources",
    "Honest Journey"
]

CONTENT_PILLAR_DISTRIBUTION = {
    "Onchain Identity & Reputation": 4,
    "Campaign Evaluation & Risk Review": 3,
    "Tools & Resources": 2,
    "Honest Journey": 1
}

PILLAR_ALIASES = {
    "airdrop_review": "Campaign Evaluation & Risk Review",
    "campaign_review": "Campaign Evaluation & Risk Review",
    "storytelling": "Honest Journey",
    "ai_tools": "Tools & Resources",
    "edukasi_web3": "Onchain Identity & Reputation",
    "market_takes": "Campaign Evaluation & Risk Review",
    "general": "Onchain Identity & Reputation",
}

PILLAR_DESCRIPTIONS = {
    "Onchain Identity & Reputation": "wallet behavior, security signals, reputation systems, and research habits",
    "Campaign Evaluation & Risk Review": "campaign evaluation, qualification logic, risk review, and effort-vs-value analysis without promotional framing",
    "Tools & Resources": "research tools, AI workflows, dashboards, and efficiency systems",
    "Honest Journey": "lessons learned, reflection, boundaries, and realistic expectations",
}

PILLAR_SLUGS = {
    "Onchain Identity & Reputation": "onchain_identity",
    "Campaign Evaluation & Risk Review": "campaign_evaluation_risk_review",
    "Tools & Resources": "tools_resources",
    "Honest Journey": "honest_journey",
}


def normalize_pillar(pillar: str) -> str:
    if not pillar:
        return "Onchain Identity & Reputation"

    pillar = pillar.strip()
    if pillar in CONTENT_PILLARS:
        return pillar

    return PILLAR_ALIASES.get(pillar, pillar)

def _env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


WEB3_CONTENT_MODEL_OVERRIDE = _env('WEB3_CONTENT_MODEL_OVERRIDE', 'WEB3_CONTENT_MODEL', 'MODEL_DEFAULT')

STRATEGIST_MODEL_PRIMARY = _env('STRATEGIST_MODEL_PRIMARY', 'MODEL_STRATEGIST_PRIMARY', 'MODEL_STRATEGIST', 'WEB3_CONTENT_IDEATION_PRIMARY', default='ag/gemini-3.5-flash-low')
STRATEGIST_MODEL_FB1 = _env('STRATEGIST_MODEL_FB1', 'MODEL_STRATEGIST_FB1', 'WEB3_CONTENT_IDEATION_FB1', default='kr/claude-haiku-4.5-thinking')
STRATEGIST_MODEL_FB2 = _env('STRATEGIST_MODEL_FB2', 'MODEL_STRATEGIST_FB2', 'WEB3_CONTENT_IDEATION_FB2', default='oc/deepseek-v4-flash-free')

WRITER_MODEL_PRIMARY = _env('WRITER_MODEL_PRIMARY', 'MODEL_WRITER_PRIMARY', 'MODEL_WRITER', 'WEB3_CONTENT_CREATIVE_PRIMARY', default='kr/claude-sonnet-4.5')
WRITER_MODEL_FB1 = _env('WRITER_MODEL_FB1', 'MODEL_WRITER_FB1', 'WEB3_CONTENT_CREATIVE_FB1', default='ag/claude-sonnet-4-6')
WRITER_MODEL_FB2 = _env('WRITER_MODEL_FB2', 'MODEL_WRITER_FB2', 'WEB3_CONTENT_CREATIVE_FB2', default='cx/gpt-5.5')

VISUAL_MODEL_PRIMARY = _env('VISUAL_MODEL_PRIMARY', 'MODEL_VISUAL_PRIMARY', 'MODEL_VISUAL', 'WEB3_CONTENT_CREATIVE_PRIMARY', default='groq/meta-llama/llama-4-scout-17b-16e-instruct')
VISUAL_MODEL_FB1 = _env('VISUAL_MODEL_FB1', 'MODEL_VISUAL_FB1', 'WEB3_CONTENT_CREATIVE_FB1', default='ag/gemini-3-flash')
VISUAL_MODEL_FB2 = _env('VISUAL_MODEL_FB2', 'MODEL_VISUAL_FB2', 'WEB3_CONTENT_CREATIVE_FB2', default='cerebras/gpt-oss-120b')

ENGAGEMENT_MODEL_PRIMARY = _env('ENGAGEMENT_MODEL_PRIMARY', 'MODEL_ENGAGEMENT_PRIMARY', 'MODEL_ENGAGEMENT', 'WEB3_CONTENT_CREATIVE_PRIMARY', default='groq/meta-llama/llama-4-scout-17b-16e-instruct')
ENGAGEMENT_MODEL_FB1 = _env('ENGAGEMENT_MODEL_FB1', 'MODEL_ENGAGEMENT_FB1', 'WEB3_CONTENT_CREATIVE_FB1', default='gemini/gemini-3.1-flash-lite')
ENGAGEMENT_MODEL_FB2 = _env('ENGAGEMENT_MODEL_FB2', 'MODEL_ENGAGEMENT_FB2', 'WEB3_CONTENT_CREATIVE_FB2', default='cerebras/gpt-oss-120b')

QC_MODEL_PRIMARY = _env('QC_MODEL_PRIMARY', 'MODEL_QC_PRIMARY', 'MODEL_QC', 'WEB3_CONTENT_REVIEW_PRIMARY', default='kr/claude-sonnet-4.5-thinking')
QC_MODEL_FB1 = _env('QC_MODEL_FB1', 'MODEL_QC_FB1', 'WEB3_CONTENT_REVIEW_FB1', default='cx/gpt-5.5-review')
QC_MODEL_FB2 = _env('QC_MODEL_FB2', 'MODEL_QC_FB2', 'WEB3_CONTENT_REVIEW_FB2', default='ag/gpt-oss-120b-medium')

PACKAGE_MODEL_PRIMARY = os.getenv('PACKAGE_MODEL_PRIMARY', 'groq/llama-3.3-70b-versatile')
PACKAGE_MODEL_FB1 = os.getenv('PACKAGE_MODEL_FB1', 'groq/meta-llama/llama-4-scout-17b-16e-instruct')
PACKAGE_MODEL_FB2 = os.getenv('PACKAGE_MODEL_FB2', 'oc/deepseek-v4-flash-free')

def load_api_config() -> tuple[str, str]:
    _load_env_files()
    api_url = os.getenv('API_BASE_URL') or os.getenv('OPENCODE_BASE_URL')
    api_key = os.getenv('API_KEY') or os.getenv('OPENCODE_API_KEY')
    if not api_key:
        raise RuntimeError("Missing API_KEY or OPENCODE_API_KEY environment variable")
    return api_url or DEFAULT_API_URL, api_key


API_URL, API_KEY = load_api_config()
