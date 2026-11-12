"""Verify Gemini API access with one minimal call.

Reads GOOGLE_API_KEY via settings (from .env); never prints the key.
Prints "success" on HTTP 200, or "HTTP <status>" on any error.

Usage:
    uv run python scripts/verify_gemini.py
    uv run python scripts/verify_gemini.py --model gemini-2.5-flash
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zeroops.config import settings  # loads .env, syncs GOOGLE_API_KEY to env


def main():
    parser = argparse.ArgumentParser(description="Verify Gemini API access")
    parser.add_argument(
        "--model",
        default="gemini-4-hydrogen",
        help="Model ID to test (default: gemini-4-hydrogen)",
    )
    args = parser.parse_args()

    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        print("error: GOOGLE_API_KEY not set — add it to .env")
        sys.exit(1)

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{args.model}:generateContent?key={key}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": "hi"}]}],
        "generationConfig": {"maxOutputTokens": 1},
    }).encode()

    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()  # consume body; don't print it
            print("success")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"error: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
