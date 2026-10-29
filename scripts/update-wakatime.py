#!/usr/bin/env python3
"""Refresh the public WakaTime summary in the profile README."""

import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START = "<!--START_SECTION:waka-->"
END = "<!--END_SECTION:waka-->"


def fetch_stats(username: str) -> dict:
    encoded_username = quote(f"@{username}", safe="")
    url = f"https://api.wakatime.com/api/v1/users/{encoded_username}/stats/last_7_days"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "GarfieldZHU-profile"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    stats = payload.get("data")
    if not isinstance(stats, dict) or stats.get("status") != "ok":
        raise RuntimeError("WakaTime did not return a usable public stats response.")
    if stats.get("is_coding_activity_visible") is False:
        raise RuntimeError("WakaTime coding activity is not publicly visible.")
    return stats


def render(stats: dict) -> str:
    total = stats.get("human_readable_total")
    if not total:
        raise RuntimeError("WakaTime response did not include a total for the last seven days.")

    languages = [
        language
        for language in stats.get("languages", [])
        if language.get("name") != "Other" and language.get("total_seconds", 0) > 0
    ]
    languages.sort(key=lambda language: language.get("total_seconds", 0), reverse=True)

    def escape_markdown(value: str) -> str:
        return value.replace("|", "\\|")

    top_languages = [
        f"{escape_markdown(language['name'])} ({language.get('text', '')})"
        for language in languages[:5]
    ]
    language_summary = " · ".join(top_languages) if top_languages else "No language activity yet."
    return f"**Last 7 days:** {total}\n\n**Languages:** {language_summary}"


def update_readme(summary: str) -> bool:
    readme = README.read_text(encoding="utf-8")
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise RuntimeError("README must contain exactly one WakaTime marker pair.")

    start = readme.index(START) + len(START)
    end = readme.index(END)
    updated = f"{readme[:start]}\n{summary}\n{readme[end:]}"
    if updated == readme:
        return False
    README.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    username = os.environ.get("WAKATIME_USERNAME", "AlohaYo")
    changed = update_readme(render(fetch_stats(username)))
    print("Updated WakaTime stats." if changed else "WakaTime stats are already current.")
