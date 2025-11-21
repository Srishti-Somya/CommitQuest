"""Compatibility wrapper to expose `process_language_data` at repository root for tests.

This wraps `utils.process_github_data.process_language_data` and converts its
output to a simple mapping {language: count} which the test suite expects.
"""
from typing import Optional, Dict, Any

from utils.process_github_data import process_language_data as _proc_lang


def process_language_data(data: Dict[str, Any]) -> Optional[Dict[str, int]]:
    try:
        res = _proc_lang(data)
        if res is None:
            return None

        out = {}
        for lang, info in res.items():
            if isinstance(info, dict) and "count" in info:
                out[lang] = info["count"]
            elif isinstance(info, int):
                out[lang] = info
        return out
    except Exception:
        return None


if __name__ == "__main__":
    # simple local test
    print(process_language_data({}))
