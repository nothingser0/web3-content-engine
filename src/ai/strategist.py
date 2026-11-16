#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from src.utils.logger import setup_logger
    from src.utils.common import setup_console_encoding
    from src.utils.config import load_api_config
    from src.core.topic_templates import get_topic_templates, merge_unique_topics
    from src.core.prompt_loader import PromptLoader
else:
    from ..utils.logger import setup_logger
    from ..utils.common import setup_console_encoding
    from ..utils.config import load_api_config
    from ..core.topic_templates import get_topic_templates, merge_unique_topics
    from ..core.prompt_loader import PromptLoader

setup_console_encoding()
logger = setup_logger(__name__)
_prompt_loader = PromptLoader()


def _load_prompt(name: str) -> str:
    return _prompt_loader.load(name)


def enrich_topics_with_fallback(topics_json: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(topics_json) >= 3:
        return topics_json

    first_topic = topics_json[0] if topics_json else {}
    mode = str(first_topic.get('mode', '')).strip().lower()
    if mode in ['manual', 'twitter', 'trending']:
        return topics_json

    first_topic_text = str(topics_json[0].get('text', '')).lower() if topics_json else ''
    first_person_keywords = ['aku', 'gw', 'gue', 'ketipu', 'rugi', 'tolongin', 'help me', 'abis', 'pernah']
    # Use word boundary matching to avoid false positives (e.g., "habis" should not match "abis")
    has_first_person = any(re.search(r'\b' + re.escape(kw) + r'\b', first_topic_text) for kw in first_person_keywords)
    if has_first_person:
        return topics_json

    first_topic = topics_json[0] if topics_json else {}
    mode = str(first_topic.get('mode', 'Auto')).strip().lower()
    context = str(first_topic.get('context', '')).strip()
    pillar = str(first_topic.get('pillar', 'general')).strip() or 'general'
    fallback_topics = get_topic_templates(mode, include_batch=True)
    existing_topics = [str(topic.get('text', '')).strip() for topic in topics_json]
    merged_topics = merge_unique_topics(existing_topics, fallback_topics)

    enriched: list[dict[str, Any]] = []
    for index, text in enumerate(merged_topics[: max(6, len(topics_json))]):
        if index < len(topics_json):
            enriched.append(topics_json[index])
            continue

        enriched.append(
            {
                'text': text,
                'context': context,
                'pillar': pillar,
                'mode': first_topic.get('mode', 'Auto'),
            }
        )

    return enriched


def _remove_extra_data(content: str) -> str:
    """Remove extra data after the last closing brace/bracket"""
    last_brace = content.rfind('}')
    last_bracket = content.rfind(']')
    last_pos = max(last_brace, last_bracket)
    
    if last_pos > 0:
        return content[:last_pos + 1].strip()
    return content


def _add_closing_braces(content: str) -> str:
    """Add missing closing braces and brackets in correct order"""
    open_braces = content.count('{')
    close_braces = content.count('}')
    open_brackets = content.count('[')
    close_brackets = content.count(']')
    
    # Add missing brackets first (close arrays), then braces (close objects)
    # This handles: {"angles": [obj1, obj2... → {"angles": [obj1, obj2]}
    if open_brackets > close_brackets:
        content += ']' * (open_brackets - close_brackets)
    if open_braces > close_braces:
        content += '}' * (open_braces - close_braces)
    
    return content


def _fix_trailing_commas(content: str) -> str:
    """Remove trailing commas before closing braces/brackets"""
    content = content.replace(',}', '}')
    content = content.replace(',]', ']')
    content = content.replace(', }', '}')
    content = content.replace(', ]', ']')
    return content


def _fix_unterminated_strings(content: str) -> str:
    """Try to fix unterminated strings by removing incomplete last object"""
    # Find the last complete object in the angles array
    # Strategy: Find the last occurrence of }, then {, and keep everything before that
    
    # Find "angles": [ to locate the array start
    angles_start = content.find('"angles"')
    if angles_start < 0:
        return content
    
    # Find the opening bracket of the angles array
    bracket_start = content.find('[', angles_start)
    if bracket_start < 0:
        return content
    
    # Try to find the last complete object by looking for pattern: },\n    {
    # Remove everything after the last complete object
    import re
    
    # Find all complete objects (ending with })
    # Then remove the last incomplete one
    last_complete = content.rfind('},')
    if last_complete > bracket_start:
        # Keep everything up to and including the last complete object
        # Then add closing brackets
        truncated = content[:last_complete + 1]
        # Add closing array bracket and object brace
        truncated += '\n  ]\n}'
        return truncated
    
    return content


def _attempt_json_repair(content: str) -> str | None:
    """
    Attempt to repair common JSON formatting issues using multiple strategies.
    Tries strategies in order from simplest to most aggressive.
    
    Returns:
        Repaired JSON string or None if all strategies fail
    """
    strategies = [
        ("Parse as-is", lambda c: c),
        ("Remove extra data", _remove_extra_data),
        ("Fix trailing commas", _fix_trailing_commas),
        ("Add missing braces", _add_closing_braces),
        ("Fix unterminated strings", _fix_unterminated_strings),
        ("Remove extra + add braces", lambda c: _add_closing_braces(_remove_extra_data(c))),
        ("Fix unterminated + add braces", lambda c: _add_closing_braces(_fix_unterminated_strings(c))),
        ("Remove extra + fix commas + add braces", lambda c: _add_closing_braces(_fix_trailing_commas(_remove_extra_data(c)))),
        ("Full repair (all strategies)", lambda c: _add_closing_braces(_fix_trailing_commas(_fix_unterminated_strings(_remove_extra_data(c))))),
    ]
    
    for strategy_name, repair_func in strategies:
        try:
            repaired = repair_func(content)
            if repaired:
                json.loads(repaired)  # Validate
                logger.info(f"✓ JSON repaired successfully using: {strategy_name}")
                return repaired
        except Exception:
            continue
    
    logger.debug("All JSON repair strategies failed")
    return None


def call_strategist_ai(topics_json, mode="auto", force_model=None):
    """
    Generate content angles using AI strategist.
    
    Args:
        topics_json: List of topic dictionaries
        mode: Strategist mode - "auto", "manual", "batch", or "twitter"
              - "auto": Auto-detect from keywords (default, backward compatible)
              - "manual": First-person stories with framework extraction
              - "batch": Evergreen educational content
              - "twitter": Trending/viral content
        force_model: Optional model to force use (bypasses router for fallback testing)
    
    Returns:
        AI-generated angles or None on error
    """
    api_url, api_key = load_api_config()
    
    from src.core.model_router import ModelRouter
    from src.utils.config import WEB3_CONTENT_MODEL_OVERRIDE
    use_router = True
    router = None
    model = None
    
    # Check for forced model (for retry fallback testing)
    if force_model:
        logger.info(f"[Strategist] Using forced model: {force_model}")
        model = force_model
        use_router = False
    # Emergency override bypasses router
    elif WEB3_CONTENT_MODEL_OVERRIDE:
        logger.info(f"[Strategist] Using override model: {WEB3_CONTENT_MODEL_OVERRIDE}")
        model = WEB3_CONTENT_MODEL_OVERRIDE
        use_router = False
    else:
        router = ModelRouter(api_url, api_key)
    
    topics_text = ""
    for i, topic in enumerate(topics_json, 1):
        text = topic.get('text', '')
        context = topic.get('context', '')
        pillar = topic.get('pillar', 'general')
        topic_mode = topic.get('mode', '')
        
        topics_text += f"\n[{i}] Topic: {text}"
        if context:
            topics_text += f"\n    Context: {context}"
        topics_text += f"\n    Pillar: {pillar}\n"
        if topic_mode:
            topics_text += f"    Mode: {topic_mode}\n"
    
    # Mode detection with auto-detection fallback
    if mode == "auto":
        # Auto-detect from keywords (backward compatibility)
        first_person_keywords = ['aku', 'gw', 'gue', 'ketipu', 'rugi', 'tolongin', 'help me', 'abis', 'pernah']
        # Use word boundary matching to avoid false positives (e.g., "habis" should not match "abis")
        has_first_person = any(re.search(r'\b' + re.escape(kw) + r'\b', topics_text.lower()) for kw in first_person_keywords)
        detected_mode = "manual" if has_first_person else "batch"
        logger.info(f"[Strategist] Auto-detected mode: {detected_mode}")
    else:
        detected_mode = mode
        logger.info(f"[Strategist] Explicit mode: {detected_mode}")
    
    # Load mode-specific overlays
    first_person_override = ""
    twitter_override = ""
    
    if detected_mode == "manual":
        first_person_override = _load_prompt("strategist/strategist_first_person_override.txt") + "\n\n"
        distribution_rule = _load_prompt("strategist/strategist_distribution_manual.txt")
    elif detected_mode == "twitter":
        # Twitter override is optional (might not exist yet)
        try:
            twitter_override = _load_prompt("strategist/strategist_twitter_override.txt") + "\n\n"
        except FileNotFoundError:
            logger.warning("[Strategist] strategist_twitter_override.txt not found, skipping twitter override")
        distribution_rule = _load_prompt("strategist/strategist_distribution_trending.txt")
    else:  # detected_mode == "batch"
        distribution_rule = _load_prompt("strategist/strategist_distribution_evergreen.txt")
    
    try:
        prompt_template = _load_prompt('strategist/strategist_surabaya_human.txt')
        current_date = datetime.now().strftime("%B %d, %Y")
        current_month = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year
        
        relevance_context = _load_prompt("strategist/strategist_relevance_context.txt").format(
            current_date=current_date,
            current_month=current_month,
            current_year=current_year,
            distribution_rule=distribution_rule,
        ) + "\n\n"
        
        prompt = first_person_override + twitter_override + relevance_context + prompt_template.replace('{topics}', topics_text)
    except FileNotFoundError:
        logger.exception("Strategist prompt file not found")
        return None
    
    messages = [{"role": "user", "content": prompt}]
    
    if use_router and router:
        # Use router for 3-tier fallback
        logger.info(f"[Strategist] Using router (Kategori A)")
        print(f"    API: {api_url}", file=sys.stderr)
        
        # Show mode context
        mode_label = topics_json[0].get('mode', 'Auto') if topics_json else 'Auto'
        mode_hints = {
            'Evergreen': '📚 Educational, timeless content (valid 3-6+ months)',
            'Auto': '🎯 AI decides best mix (prefer evergreen when possible)',
            'Trending': '📈 Topical content (frame as evaluation/lesson, avoid hype)'
        }
        mode_hint = mode_hints.get(mode_label, mode_hints['Evergreen'])
        print(f"    Mode: {mode_label} - {mode_hint}", file=sys.stderr)
        print(f"    Expected: 3 content angles in Surabaya style", file=sys.stderr)
        print(f"    Time estimate: 30-90 seconds (depending on model load)", file=sys.stderr)
        print(f"", file=sys.stderr)
        
        content = router.call_with_fallback(
            role="strategist",
            messages=messages,
            max_tokens=4096,
            temperature=0.8
            # Note: response_format removed - not all models/APIs support it
        )
        
        if not content:
            logger.error("[Strategist] All router tiers failed")
            return None
    else:
        # Use override model (emergency fallback)
        logger.info(f"[Strategist] Calling override model: {model}")
        print(f"    API: {api_url}", file=sys.stderr)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.8
            # Note: response_format removed - not all models/APIs support it
        }
        
        try:
            response = requests.post(
                f"{api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=600
            )
            
            if response.status_code != 200:
                logger.error(f"API Error: {response.status_code}")
                return None
            
            # Try to parse response as JSON
            try:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            except json.JSONDecodeError as json_err:
                # Response has extra data or malformed JSON at response level
                logger.warning(f"Response JSON malformed: {json_err}, attempting to repair at response level")
                try:
                    # Get raw text and apply "remove extra data" strategy
                    raw_text = response.text
                    last_brace = raw_text.rfind('}')
                    if last_brace > 0:
                        truncated = raw_text[:last_brace + 1]
                        result = json.loads(truncated)
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        logger.info("✓ Repaired response-level JSON (removed extra data)")
                    else:
                        logger.error("Could not find valid JSON structure in response")
                        return None
                except Exception as repair_err:
                    logger.error(f"Failed to repair response JSON: {repair_err}")
                    return None
            
        except requests.exceptions.Timeout:
            logger.error("Request timeout after 600s")
            return None
        except Exception as e:
            logger.error(f"Error calling override model: {e}")
            return None
    
    # Parse JSON from content
    try:
        # Extract JSON from markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Try parsing
        angles_data = json.loads(content)
        return angles_data
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error: {e}")
        logger.error(f"Problematic content (first 500 chars): {content[:500]}")
        logger.error(f"Problematic content (last 500 chars): {content[-500:]}")
        
        # Try to repair common JSON issues
        try:
            repaired = _attempt_json_repair(content)
            if repaired:
                angles_data = json.loads(repaired)
                logger.info("✓ JSON repaired successfully")
                return angles_data
        except Exception as repair_error:
            logger.error(f"JSON repair also failed: {repair_error}")
        
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

def display_angles(angles_data, mode='auto'):
    """Display angles with mode-aware sorting"""
    if not angles_data or 'angles' not in angles_data:
        return
    
    # Detect if any angle contains first-person keywords (personal story)
    first_person_keywords = ['aku', 'gw', 'gue', 'ketipu', 'rugi', 'tolongin', 'help me', 'abis', 'pernah']
    has_first_person_angles = False
    
    for angle in angles_data['angles']:
        title = angle.get('title', '').lower()
        hook = angle.get('hook', '').lower()
        if any(kw in title or kw in hook for kw in first_person_keywords):
            has_first_person_angles = True
            angle['_first_person_match'] = True
        else:
            angle['_first_person_match'] = False
    
    # Sort differently based on whether first-person angles exist
    if has_first_person_angles:
        # Personal story mode: prioritize first-person angles, then by viral score
        angles = sorted(
            angles_data['angles'], 
            key=lambda x: (
                x.get('_first_person_match', False),  # First-person angles first
                x.get('viral_score', 0),              # Then by viral potential
                x.get('evergreen_score', 0)           # Then by evergreen
            ), 
            reverse=True
        )
    else:
        # Mode-aware sorting
        if mode == 'evergreen':
            # Evergreen mode: prioritize evergreen content
            angles = sorted(
                angles_data['angles'], 
                key=lambda x: (x.get('evergreen_score', x.get('recency_score', 0)), x.get('viral_score', 0)), 
                reverse=True
            )
        else:
            # Auto/Trending mode: prioritize viral content
            angles = sorted(
                angles_data['angles'], 
                key=lambda x: (x.get('viral_score', 0), x.get('evergreen_score', 0)), 
                reverse=True
            )
    
    is_batch_mode = mode in {'auto', 'evergreen', 'batch'}

    print("\n" + "=" * 60, file=sys.stderr)
    print("STRATEGIST SUGGESTIONS - PILIH ANGLE", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    for i, angle in enumerate(angles, 1):
        viral_score = angle.get('viral_score', 0)
        evergreen_score = angle.get('evergreen_score', angle.get('recency_score', 0))  # Fallback to recency_score
        evergreen_category = angle.get('evergreen_category', 'N/A')
        content_pillar = angle.get('content_pillar', angle.get('pillar', 'N/A'))
        title = angle.get('title', '')
        top = " [TOP PICK]" if i == 1 else ""
        
        print(f"\n[{i}] {title}{top}", file=sys.stderr)
        print(f"    Hook: {angle.get('hook', '')[:80]}...", file=sys.stderr)
        print(f"    Pillar: {content_pillar}", file=sys.stderr)
        print(f"    Formats: {', '.join(angle.get('suggested_formats', []))}", file=sys.stderr)
        if is_batch_mode:
            print(f"    Category: {evergreen_category}", file=sys.stderr)
            print(f"    Scores: Viral={viral_score}/10, Evergreen={evergreen_score}/10", file=sys.stderr)
        else:
            print(f"    Scores: Viral={viral_score}/10", file=sys.stderr)
        
        # Show key points
        key_points = angle.get('key_points', [])
        if key_points:
            print(f"    Key Points:", file=sys.stderr)
            for point in key_points[:2]:  # Show first 2 points
                print(f"      • {point[:60]}...", file=sys.stderr)
    
    print("\n" + "=" * 60, file=sys.stderr)


def main():
    """Main"""
    print("=" * 60, file=sys.stderr)
    print("AI STRATEGIST V3 - Web3 Content Pipeline", file=sys.stderr)
    print("(Surabaya Style: aku/kamu + slang Suroboyo)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    # Read input
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        try:
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                topics_json = json.load(f)
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            sys.exit(1)
    else:
        topics_json = json.load(sys.stdin)
    
    original_topic_count = len(topics_json)
    topics_json = enrich_topics_with_fallback(topics_json)
    if original_topic_count < len(topics_json):
        logger.info(f"Loaded {len(topics_json)} input topics ({original_topic_count} provided + {len(topics_json) - original_topic_count} evergreen fallback seeds)")
    else:
        logger.info(f"Loaded {len(topics_json)} input topics")
    
    # Extract mode from first topic for mode-aware sorting
    first_topic = topics_json[0] if topics_json else {}
    mode = str(first_topic.get('mode', 'auto')).strip().lower()
    
    # Regeneration loop: keep generating unique angles
    TARGET_ANGLES = 8          # Target number of angles (more realistic)
    MIN_ACCEPTABLE_ANGLES = 4  # Minimum acceptable angles (flexible for partial success)
    MAX_ATTEMPTS = 5           # Maximum retry attempts (increased for better success rate)
    accumulated_angles = []
    seen_titles = set()
    attempt = 0

    while len(accumulated_angles) < TARGET_ANGLES and attempt < MAX_ATTEMPTS:
        attempt += 1
        logger.info(f"Generation attempt {attempt}/{MAX_ATTEMPTS} (current: {len(accumulated_angles)}/{TARGET_ANGLES})")
        
        # Determine which model to use based on attempt (tier fallback for JSON errors)
        force_model = None
        if attempt == 2:
            from src.utils.config import STRATEGIST_MODEL_FB1
            force_model = STRATEGIST_MODEL_FB1
            logger.info(f"[Strategist] Attempt {attempt}: Forcing FB1 tier model ({force_model})")
        elif attempt == 3:
            from src.utils.config import STRATEGIST_MODEL_FB2
            force_model = STRATEGIST_MODEL_FB2
            logger.info(f"[Strategist] Attempt {attempt}: Forcing FB2 tier model ({force_model})")
        
        # Call AI with explicit mode and optional forced model
        angles_data = call_strategist_ai(topics_json, mode=mode, force_model=force_model)
        
        if not angles_data:
            logger.warning(f"Attempt {attempt} failed to generate angles")
            continue
        
        # Filter against accumulated angles (intra-accumulation dedup)
        new_angles = []
        for angle in angles_data.get('angles', []):
            title = angle.get('title', '')
            normalized_title = title.strip().lower()
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                new_angles.append(angle)
                accumulated_angles.append(angle)
                if len(accumulated_angles) >= TARGET_ANGLES:
                    break
        
        logger.info(f"Added {len(new_angles)} new unique angles (total: {len(accumulated_angles)}/{TARGET_ANGLES})")
        
        # Break if we have enough
        if len(accumulated_angles) >= TARGET_ANGLES:
            break

    # Check results with more lenient acceptance criteria
    if not accumulated_angles:
        logger.error("Failed to generate any unique angles after all attempts")
        sys.exit(1)
    elif len(accumulated_angles) < MIN_ACCEPTABLE_ANGLES:
        logger.error(f"Only generated {len(accumulated_angles)} angles, minimum required is {MIN_ACCEPTABLE_ANGLES}")
        logger.error("Try running again or check if AI model is working properly")
        sys.exit(1)
    elif len(accumulated_angles) < TARGET_ANGLES:
        logger.warning(f"Only generated {len(accumulated_angles)}/{TARGET_ANGLES} angles (target not met)")
        logger.warning("Continuing with partial results - consider running again for more variety")

    # Trim to exactly TARGET_ANGLES if we have more
    if len(accumulated_angles) > TARGET_ANGLES:
        accumulated_angles = accumulated_angles[:TARGET_ANGLES]

    # Rebuild angles_data structure with accumulated angles
    angles_data = {
        'angles': accumulated_angles,
        'total_count': len(accumulated_angles),
        'generated_at': datetime.now().isoformat()
    }

    logger.info(f"Final: Generated {len(accumulated_angles)} unique angles in {attempt} attempt(s)")

    display_angles(angles_data, mode)

    angles = angles_data.get('angles', [])
    if not isinstance(angles, list):
        angles = []

    output = {
        "angles": angles,
        "total_count": len(angles),
        "generated_at": datetime.now().isoformat()
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    
if __name__ == "__main__":
    main()



