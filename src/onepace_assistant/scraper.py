"""Scraper for One Pace metadata from onepace.net."""

import json
import re
from typing import Any

import httpx

from .models import Arc

ONEPACE_WATCH_URL = "https://onepace.net/en/watch"

# Regex to extract RSC payload data from Next.js script tags
RSC_PAYLOAD_PATTERN = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.DOTALL)


class ScraperError(Exception):
    """Error during metadata scraping."""


def _unescape_rsc_string(s: str) -> str:
    """Unescape the RSC payload string."""
    # RSC payloads have escaped quotes and special chars
    return (
        s.replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def _extract_arcs_array(payload: str) -> list[dict]:
    """Extract the arcs data array from the RSC payload (supports modern and legacy formats)."""
    # 1. Handle timeline-based segments (current site version)
    # 2. Fallback for legacy data property structure
    patterns = [
        r'"timeline":\s*\{.*?"segments":\s*(\[)',
        r'"data":\s*(\[{"slug":")'
    ]

    for pattern in patterns:
        match = re.search(pattern, payload, re.DOTALL)
        if not match:
            continue

        # Extract the array using bracket matching
        start_idx = match.start(1)
        arr_str = payload[start_idx:]

        bracket_count = 0
        for i, c in enumerate(arr_str):
            if c == '[':
                bracket_count += 1
            elif c == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    try:
                        return json.loads(arr_str[:i + 1])
                    except json.JSONDecodeError:
                        break  # Try next pattern

    raise ScraperError("Could not extract arcs data from RSC payload")


def _normalize_arc_data(data: Any) -> Any:
    """
    Recursively normalizes payload data:
    - Replaces '$undefined' with None.
    - Maps 'playlistGroups' to 'playGroups' for compatibility with newer site versions.
    """
    if isinstance(data, list):
        return [_normalize_arc_data(item) for item in data]

    if isinstance(data, dict):
        normalized = {}
        for k, v in data.items():
            key = "playGroups" if k == "playlistGroups" else k
            normalized[key] = _normalize_arc_data(v)
        return normalized

    return None if data == "$undefined" else data


def extract_rsc_payload(html: str) -> str:
    """Extract and combine RSC payload strings from HTML."""
    matches = RSC_PAYLOAD_PATTERN.findall(html)
    if not matches:
        raise ScraperError("No RSC payload found in HTML")

    # Combine all payload chunks
    combined = ""
    for match in matches:
        combined += _unescape_rsc_string(match)

    return combined


def parse_arcs_from_html(html: str) -> list[Arc]:
    """Parse arc metadata from HTML content."""
    payload = extract_rsc_payload(html)
    arcs_data = _extract_arcs_array(payload)

    arcs = []
    for arc_data in arcs_data:
        try:
            # Normalize data: $undefined -> None, playlistGroups -> playGroups
            normalized_data = _normalize_arc_data(arc_data)
            arc = Arc.model_validate(normalized_data)
            arcs.append(arc)
        except Exception as e:
            # Log but don't fail on individual arc parsing errors
            print(f"Warning: Failed to parse arc '{arc_data.get('slug', 'unknown')}': {e}")

    return arcs


async def fetch_metadata() -> list[Arc]:
    """Fetch and parse all arc metadata from onepace.net."""
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "OnePaceAssistant/0.1.0 (https://github.com/one-pace-assistant)",
        },
        timeout=30.0,
    ) as client:
        response = await client.get(ONEPACE_WATCH_URL)
        response.raise_for_status()

    return parse_arcs_from_html(response.text)


def fetch_metadata_sync() -> list[Arc]:
    """Synchronous version of fetch_metadata for CLI use."""
    with httpx.Client(
        headers={
            "User-Agent": "OnePaceAssistant/0.1.0 (https://github.com/one-pace-assistant)",
        },
        timeout=30.0,
    ) as client:
        response = client.get(ONEPACE_WATCH_URL)
        response.raise_for_status()

    return parse_arcs_from_html(response.text)
