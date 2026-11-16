#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Utilities - API Client with Retry Logic
Centralized API calls with exponential backoff
"""

import time
import sys
import re
import json
import requests
from pathlib import Path
from typing import Any, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.logger import setup_logger
else:
    from ..utils.logger import setup_logger

logger = setup_logger(__name__)


def extract_json_from_response(response_text: str) -> dict[str, Any]:
    """
    Extract JSON from potentially messy API responses.
    Handles SSE (Server-Sent Events), markdown code blocks, extra text, and malformed responses.
    
    Args:
        response_text: Raw response text from API
        
    Returns:
        Parsed JSON dict
        
    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try 1: Parse as-is (clean JSON)
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try 2: Extract from SSE (Server-Sent Events) format
    # Pattern: data: {...}\n\n or data: {...}\n
    if 'data:' in response_text:
        # Extract all data: lines
        sse_lines = []
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('data:'):
                data_content = line[5:].strip()  # Remove 'data:' prefix
                if data_content and data_content != '[DONE]':
                    sse_lines.append(data_content)
        
        # Try to parse the first valid JSON from SSE data
        for sse_data in sse_lines:
            try:
                return json.loads(sse_data)
            except json.JSONDecodeError:
                continue
    
    # Try 3: Extract from markdown code block
    # Pattern: ```json\n{...}\n``` or ```\n{...}\n```
    code_block_pattern = r'```(?:json)?\s*\n(.*?)\n```'
    matches = re.findall(code_block_pattern, response_text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass
    
    # Try 4: Extract first complete JSON object by finding matching braces
    brace_count = 0
    start_idx = response_text.find('{')
    
    if start_idx != -1:
        for i in range(start_idx, len(response_text)):
            if response_text[i] == '{':
                brace_count += 1
            elif response_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found complete JSON object
                    try:
                        return json.loads(response_text[start_idx:i+1])
                    except json.JSONDecodeError:
                        break
    
    # Try 5: Parse line by line to get first valid JSON
    for line in response_text.split('\n'):
        line = line.strip()
        if line.startswith('{'):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    
    # All attempts failed - raise with original text for debugging
    raise json.JSONDecodeError(
        f"Could not extract valid JSON from response. First 200 chars: {response_text[:200]}",
        response_text,
        0
    )


class APIError(Exception):
    """Custom exception for API errors"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class APIClient:
    """
    Reusable API client with retry logic and exponential backoff
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        max_retries: int = 3,
        timeout: int = 600
    ):
        """
        Initialize API client
        
        Args:
            base_url: API base URL
            api_key: API authentication key
            max_retries: Maximum retry attempts (default: 3)
            timeout: Request timeout in seconds (default: 600)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        return min(2 ** attempt, 60)  # Max 60 seconds
    
    def call_chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.8,
        track_performance: bool = True
    ) -> Optional[str]:
        """
        Call chat completion API with retry logic
        
        Args:
            model: Model name
            messages: List of message dicts
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            track_performance: Whether to track performance metrics
        
        Returns:
            Generated content or None on failure
        
        Raises:
            APIError: On non-retryable errors
        """
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        last_error = None
        start_time = time.time()
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"API call attempt {attempt + 1}/{self.max_retries}")
                
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=self.timeout
                )
                
                # Success
                if response.status_code == 200:
                    try:
                        # Use robust JSON extraction to handle malformed responses
                        result = extract_json_from_response(response.text)
                        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                        
                        if not content:
                            logger.warning("Empty response from API")
                            return None
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        logger.debug(f"Response text (first 500 chars): {response.text[:500]}")
                        last_error = f"JSON parse error: {e}"
                        continue
                    
                    logger.info("API call successful")
                    
                    return content
                
                # Rate limit - always retry
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', self._calculate_backoff(attempt)))
                    logger.warning(f"Rate limited. Retrying after {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Server errors - retry
                elif 500 <= response.status_code < 600:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Server error {response.status_code}. Retrying after {backoff}s")
                    time.sleep(backoff)
                    continue
                
                # Client errors - don't retry
                else:
                    error_msg = response.text
                    logger.error(f"API error {response.status_code}: {error_msg}")
                    raise APIError(response.status_code, error_msg)
            
            except requests.exceptions.Timeout:
                backoff = self._calculate_backoff(attempt)
                logger.warning(f"Request timeout. Retrying after {backoff}s")
                time.sleep(backoff)
                last_error = "Request timeout"
                continue
            
            except requests.exceptions.ConnectionError as e:
                backoff = self._calculate_backoff(attempt)
                logger.warning(f"Connection error: {e}. Retrying after {backoff}s")
                time.sleep(backoff)
                last_error = str(e)
                continue
            
            except APIError:
                # Don't retry client errors
                raise
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                last_error = str(e)
                break
        
        # All retries exhausted
        logger.error(f"API call failed after {self.max_retries} attempts. Last error: {last_error}")
        
        return None
    
    def close(self):
        """Close session"""
        self.session.close()
