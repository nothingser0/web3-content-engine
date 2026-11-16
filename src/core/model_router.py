#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model Router with 3-tier fallback per role.

Supports:
- strategist: Kategori A (Ideation & Strategi)
- writer: Kategori B (Eksekusi Kreatif)
- visual: Kategori C (Analisis → Structured Output)
- engagement: Kategori C (Analisis → Structured Output)
- qc: Kategori G (Review/QC) - uses Kategori B stack

Model configuration read from config.py environment variables.
"""
import json
import time
import logging
import requests
from typing import Dict, Any, Optional, Literal, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

Role = Literal["strategist", "writer", "visual", "engagement", "qc", "package"]
Tier = Literal["primary", "fb1", "fb2"]

@dataclass
class ModelConfig:
    """Model configuration for a specific tier."""
    model: str
    provider: str
    description: str = ""


def _required_model(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"Missing model config: {name}")
    return value

def _build_role_models() -> Dict[Role, Dict[Tier, ModelConfig]]:
    """Build ROLE_MODELS from config env vars at runtime."""
    from src.utils.config import (
        STRATEGIST_MODEL_PRIMARY, STRATEGIST_MODEL_FB1, STRATEGIST_MODEL_FB2,
        WRITER_MODEL_PRIMARY, WRITER_MODEL_FB1, WRITER_MODEL_FB2,
        VISUAL_MODEL_PRIMARY, VISUAL_MODEL_FB1, VISUAL_MODEL_FB2,
        ENGAGEMENT_MODEL_PRIMARY, ENGAGEMENT_MODEL_FB1, ENGAGEMENT_MODEL_FB2,
        QC_MODEL_PRIMARY, QC_MODEL_FB1, QC_MODEL_FB2,
        PACKAGE_MODEL_PRIMARY, PACKAGE_MODEL_FB1, PACKAGE_MODEL_FB2
    )
    
    return {
        "strategist": {
            "primary": ModelConfig(
                model=_required_model(STRATEGIST_MODEL_PRIMARY, "STRATEGIST_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori A - Ideation & Strategi"
            ),
            "fb1": ModelConfig(
                model=_required_model(STRATEGIST_MODEL_FB1, "STRATEGIST_MODEL_FB1"),
                provider="FB1",
                description="Kategori A fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(STRATEGIST_MODEL_FB2, "STRATEGIST_MODEL_FB2"),
                provider="FB2",
                description="Kategori A fallback 2"
            )
        },
        "writer": {
            "primary": ModelConfig(
                model=_required_model(WRITER_MODEL_PRIMARY, "WRITER_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori B - Eksekusi Kreatif"
            ),
            "fb1": ModelConfig(
                model=_required_model(WRITER_MODEL_FB1, "WRITER_MODEL_FB1"),
                provider="FB1",
                description="Kategori B fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(WRITER_MODEL_FB2, "WRITER_MODEL_FB2"),
                provider="FB2",
                description="Kategori B fallback 2"
            )
        },
        "visual": {
            "primary": ModelConfig(
                model=_required_model(VISUAL_MODEL_PRIMARY, "VISUAL_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori C - Analisis → Structured"
            ),
            "fb1": ModelConfig(
                model=_required_model(VISUAL_MODEL_FB1, "VISUAL_MODEL_FB1"),
                provider="FB1",
                description="Kategori C fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(VISUAL_MODEL_FB2, "VISUAL_MODEL_FB2"),
                provider="FB2",
                description="Kategori C fallback 2"
            )
        },
        "engagement": {
            "primary": ModelConfig(
                model=_required_model(ENGAGEMENT_MODEL_PRIMARY, "ENGAGEMENT_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori D - Engagement Planning"
            ),
            "fb1": ModelConfig(
                model=_required_model(ENGAGEMENT_MODEL_FB1, "ENGAGEMENT_MODEL_FB1"),
                provider="FB1",
                description="Kategori D fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(ENGAGEMENT_MODEL_FB2, "ENGAGEMENT_MODEL_FB2"),
                provider="FB2",
                description="Kategori D fallback 2"
            )
        },
        "qc": {
            "primary": ModelConfig(
                model=_required_model(QC_MODEL_PRIMARY, "QC_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori G - Review/QC"
            ),
            "fb1": ModelConfig(
                model=_required_model(QC_MODEL_FB1, "QC_MODEL_FB1"),
                provider="FB1",
                description="Kategori G fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(QC_MODEL_FB2, "QC_MODEL_FB2"),
                provider="FB2",
                description="Kategori G fallback 2"
            )
        },
        "package": {
            "primary": ModelConfig(
                model=_required_model(PACKAGE_MODEL_PRIMARY, "PACKAGE_MODEL_PRIMARY"),
                provider="Primary",
                description="Kategori F - Final Package"
            ),
            "fb1": ModelConfig(
                model=_required_model(PACKAGE_MODEL_FB1, "PACKAGE_MODEL_FB1"),
                provider="FB1",
                description="Kategori F fallback 1"
            ),
            "fb2": ModelConfig(
                model=_required_model(PACKAGE_MODEL_FB2, "PACKAGE_MODEL_FB2"),
                provider="FB2",
                description="Kategori F fallback 2"
            )
        }
    }

_role_models: Dict[Role, Dict[Tier, ModelConfig]] | None = None


def get_role_models() -> Dict[Role, Dict[Tier, ModelConfig]]:
    global _role_models
    if _role_models is None:
        _role_models = _build_role_models()
    return _role_models


ROLE_MODELS: Dict[Role, Dict[Tier, ModelConfig]] = {}


class ModelRouter:
    """
    3-tier fallback router with automatic provider switching.
    
    Usage:
        router = ModelRouter(api_url, api_key)
        result = router.call_with_fallback(
            role="writer",
            messages=[{"role": "user", "content": "Write content"}],
            max_tokens=2048
        )
    """
    
    def __init__(self, api_url: str, api_key: str, timeout: int = 600):
        """
        Initialize router with API credentials.
        
        Args:
            api_url: Base API URL (e.g., http://100.122.184.75:1430/v1)
            api_key: API authentication key
            timeout: Request timeout in seconds (default: 600)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _parse_sse_response(self, response_text: str) -> Optional[str]:
        """
        Parse Server-Sent Events (SSE) streaming response.
        Extracts content from 'data:' lines and concatenates deltas.
        
        Returns:
            Concatenated content or None if parsing fails
        """
        content_parts = []
        
        for line in response_text.split('\n'):
            line = line.strip()
            if not line.startswith('data: '):
                continue
            
            try:
                json_str = line[6:]  # Remove 'data: ' prefix
                if json_str == '[DONE]':
                    break
                
                chunk = json.loads(json_str)
                choices = chunk.get('choices', [])
                if not choices:
                    continue
                
                delta = choices[0].get('delta', {})
                if 'content' in delta:
                    content_parts.append(delta['content'])
            except Exception as e:
                logger.debug(f"[Router] SSE parse error for line: {e}")
                continue
        
        result = ''.join(content_parts) if content_parts else None
        if result:
            logger.debug(f"[Router] SSE parsed content length: {len(result)}")
        return result
    
    def _extract_content(self, data: Dict[str, Any], model: str) -> Optional[str]:
        """
        Extract content from API response with multiple field path fallbacks.
        Handles: standard OpenAI format, reasoning models, alternative structures.
        
        Returns:
            Extracted content or None if all paths fail
        """
        content = None
        field_path = None
        
        # Path 1: Standard OpenAI format - choices[0].message.content
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            # Try standard content field (must be non-empty)
            if message.get("content"):
                content = message["content"]
                field_path = "choices[0].message.content"
            # Try reasoning_content field (Kimi, GLM, DeepSeek models)
            elif message.get("reasoning_content"):
                content = message["reasoning_content"]
                field_path = "choices[0].message.reasoning_content"
            # Try reasoning field (Cerebras models)
            elif message.get("reasoning"):
                content = message["reasoning"]
                field_path = "choices[0].message.reasoning"
            # Try text field (alternative format)
            elif choice.get("text"):
                content = choice["text"]
                field_path = "choices[0].text"
        
        # Path 2: Reasoning models (thinking models) - check for reasoning_content + output
        if not content and "reasoning_content" in data:
            content = data.get("output") or data.get("content") or data.get("text")
            field_path = "reasoning_content + output/content"
        
        # Path 3: Google/Gemini format - candidates[0].content
        if not content and "candidates" in data:
            candidates = data["candidates"]
            if len(candidates) > 0:
                if "content" in candidates[0]:
                    cand_content = candidates[0]["content"]
                    if isinstance(cand_content, dict) and "parts" in cand_content:
                        parts = cand_content["parts"]
                        if len(parts) > 0 and "text" in parts[0]:
                            content = parts[0]["text"]
                            field_path = "candidates[0].content.parts[0].text"
                    elif isinstance(cand_content, str):
                        content = cand_content
                        field_path = "candidates[0].content"
        
        # Path 4: Direct output field
        if not content and "output" in data:
            content = data["output"]
            field_path = "output"
        
        # Path 5: Direct text field
        if not content and "text" in data:
            content = data["text"]
            field_path = "text"
        
        if content and content.strip():
            logger.debug(f"[Router] Extracted via {field_path}")
            return content.strip()
        
        logger.warning(f"[Router] Model {model} returned empty content (tried all field paths)")
        return None
    
    def _try_parse_strategies(self, raw_response_text: str) -> Optional[str]:
        """
        Try multiple parsing strategies on raw response text.
        Attempts different methods before giving up.
        
        Returns:
            Parsed content or None if all strategies fail
        """
        strategies = [
            ("SSE streaming format", self._parse_as_sse),
            ("Regular JSON response", self._parse_as_json_response),
            ("Plain text with code blocks", self._parse_as_plain_text),
            ("Direct JSON string", self._parse_as_direct_json),
        ]
        
        for strategy_name, parser_func in strategies:
            try:
                logger.debug(f"[Router] Trying strategy: {strategy_name}")
                content = parser_func(raw_response_text)
                if content and content.strip():
                    logger.info(f"[Router] ✓ Success with strategy: {strategy_name}")
                    return content.strip()
            except Exception as e:
                logger.debug(f"[Router] Strategy '{strategy_name}' failed: {e}")
                continue
        
        logger.warning(f"[Router] All parsing strategies failed")
        return None
    
    def _parse_as_sse(self, text: str) -> Optional[str]:
        """Parse as Server-Sent Events format"""
        return self._parse_sse_response(text)
    
    def _parse_as_json_response(self, text: str) -> Optional[str]:
        """Parse as standard JSON API response"""
        try:
            data = json.loads(text)
            return self._extract_content(data, "unknown")
        except:
            return None
    
    def _parse_as_plain_text(self, text: str) -> Optional[str]:
        """Parse as plain text, try to extract from code blocks"""
        content = text
        
        # Try markdown code blocks
        if "```json" in content:
            try:
                content = content.split("```json")[1].split("```")[0].strip()
            except:
                pass
        elif "```" in content:
            try:
                content = content.split("```")[1].split("```")[0].strip()
            except:
                pass
        
        # Validate if it's parseable JSON
        try:
            json.loads(content)
            return content
        except:
            return None
    
    def _parse_as_direct_json(self, text: str) -> Optional[str]:
        """Try to parse directly as JSON string"""
        try:
            # Check if it's valid JSON
            json.loads(text)
            return text
        except:
            return None
    
    def _try_model(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Try single model call with multi-strategy response parsing.
        Tries multiple parsing methods before giving up and triggering fallback.
        
        Args:
            response_format: Optional response format (e.g., {"type": "json_object"})
        
        Returns:
            Generated content or None on failure
        """
        try:
            logger.info(f"[Router] Calling model: {model}")
            
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            # Add response_format if provided (JSON mode)
            if response_format:
                payload["response_format"] = response_format
                logger.debug(f"[Router] Using response_format: {response_format}")
            
            # Request with transient retry for rate limits (429) and server overloads (502, 503)
            max_transient_retries = 2
            response = None
            for attempt in range(max_transient_retries + 1):
                try:
                    response = self.session.post(
                        f"{self.api_url}/chat/completions",
                        json=payload,
                        timeout=self.timeout
                    )
                    
                    # Rate limit or temporary gateway overload - quick retry before falling back
                    if response.status_code in (429, 502, 503):
                        if attempt < max_transient_retries:
                            delay = 2 * (attempt + 1)
                            logger.warning(
                                f"[Router] Model {model} hit HTTP {response.status_code}. "
                                f"Retrying in {delay}s (attempt {attempt + 1}/{max_transient_retries})..."
                            )
                            time.sleep(delay)
                            continue
                        else:
                            err_detail = response.text[:300].strip() if response.text else "No details"
                            logger.warning(f"[Router] Model {model} returned HTTP {response.status_code} after retries: {err_detail}")
                            return None
                    
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as conn_err:
                    if attempt < max_transient_retries:
                        delay = 2 * (attempt + 1)
                        logger.warning(f"[Router] Connection glitch: {conn_err}. Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    raise
            
            if response is None:
                return None

            if response.status_code != 200:
                err_detail = response.text[:300].strip() if response.text else "No details"
                logger.warning(f"[Router] Model {model} returned HTTP {response.status_code}: {err_detail}")
                return None
            
            # Get raw response text
            raw_text = response.text
            logger.debug(f"[Router] Received {len(raw_text)} bytes from {model}")
            
            # Try multiple parsing strategies
            content = self._try_parse_strategies(raw_text)
            
            if content:
                logger.info(f"[Router] ✓ Successfully parsed response from {model}")
                return content
            else:
                logger.warning(f"[Router] ✗ All parsing strategies failed for {model}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"[Router] Model {model} timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.warning(f"[Router] Model {model} failed: {e}")
            return None
    
    def call_with_fallback(
        self,
        role: Role,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.8,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Call model with 3-tier fallback (Utama → FB1 → FB2).
        
        Args:
            role: Task role (strategist, writer, visual, engagement, qc)
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            response_format: Optional response format (e.g., {"type": "json_object"} for JSON mode)
        
        Returns:
            Generated content or None if all tiers fail
        """
        role_models = get_role_models()
        if role not in role_models:
            logger.error(f"[Router] Unknown role: {role}")
            return None
        
        tiers = role_models[role]
        
        tier_order: List[Tier] = ["primary", "fb1", "fb2"]
        for tier_name in tier_order:
            config = tiers[tier_name]
            logger.info(f"[Router] {role} → {tier_name.upper()}: {config.model}")
            
            # Print to stderr for visibility during execution
            import sys
            tier_label = "PRIMARY" if tier_name == "primary" else "FB1" if tier_name == "fb1" else "FB2"
            print(f"    Model: {config.model} (Tier: {tier_label})", file=sys.stderr)
            if config.description:
                print(f"    Category: {config.description}", file=sys.stderr)
            
            result = self._try_model(config.model, messages, max_tokens, temperature, response_format)
            
            if result:
                logger.info(f"[Router] ✓ {role} → {tier_name.upper()} SUCCESS ({config.model})")
                return result
            else:
                logger.warning(f"[Router] ✗ {role} → {tier_name.upper()} FAILED ({config.model})")
                if tier_name != "fb2":
                    logger.info(f"[Router] → Trying {tier_name.upper()} fallback...")
        
        logger.error(f"[Router] All tiers failed for role: {role}")
        return None

    def close(self):
        """Close the persistent HTTP session."""
        if hasattr(self, 'session'):
            self.session.close()
