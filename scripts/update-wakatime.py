#!/usr/bin/env python3
"""Refresh the public WakaTime summary in the profile README."""

import html
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SVG_CARD = ROOT / "wakatime.svg"
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


def render_svg(stats: dict) -> str:
    total = stats.get("human_readable_total")
    if not total:
        raise RuntimeError("WakaTime response did not include a total for the last seven days.")

    languages = [
        language
        for language in stats.get("languages", [])
        if language.get("name") != "Other" and language.get("total_seconds", 0) > 0
    ]
    languages.sort(key=lambda language: language.get("total_seconds", 0), reverse=True)
    total_language_seconds = sum(language.get("total_seconds", 0) for language in languages)
    languages = languages[:5]

    rows = []
    for index, language in enumerate(languages):
        y = 126 + index * 35
        seconds = language.get("total_seconds", 0)
        percent = (seconds / total_language_seconds * 100) if total_language_seconds else 0
        bar_width = round(276 * percent / 100)
        if percent > 0:
            bar_width = max(bar_width, 3)
        name = html.escape(str(language.get("name", "Unknown")), quote=True)
        duration = html.escape(str(language.get("text", "")), quote=True)
        rows.append(
            f'''  <g class="language-row">
    <text x="32" y="{y}" class="language">{name}</text>
    <text x="168" y="{y}" class="duration">{duration}</text>
    <rect x="288" y="{y - 11}" width="276" height="8" rx="4" class="track" />
    <rect x="288" y="{y - 11}" width="{bar_width}" height="8" rx="4" class="bar" />
    <text x="594" y="{y}" class="percent" text-anchor="end">{percent:.1f}%</text>
  </g>'''
        )

    rows_markup = "\n".join(rows) or '''  <text x="32" y="143" class="empty">No language activity in the last 7 days.</text>'''
    total_text = html.escape(str(total), quote=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="322" viewBox="0 0 640 322" role="img" aria-labelledby="title description">
  <title id="title">WakaTime coding activity</title>
  <desc id="description">Programming language usage over the last seven days. Total coding time: {total_text}.</desc>
  <defs>
    <linearGradient id="accent" x1="0" x2="1">
      <stop offset="0%" stop-color="#a78bfa" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <style>
      .card {{ fill: #111827; stroke: #334155; stroke-width: 1.5; }}
      .title {{ fill: #f8fafc; font: 600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .subtitle {{ fill: #94a3b8; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .total {{ fill: #e2e8f0; font: 600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .language {{ fill: #e2e8f0; font: 500 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .duration {{ fill: #94a3b8; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .percent {{ fill: #cbd5e1; font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .track {{ fill: #263244; }}
      .bar {{ fill: url(#accent); }}
      .empty {{ fill: #cbd5e1; font: 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    </style>
  </defs>
  <rect x="1" y="1" width="638" height="320" rx="18" class="card" />
  <circle cx="39" cy="39" r="17" fill="url(#accent)" />
  <text x="39" y="45" text-anchor="middle" fill="#111827" font-family="sans-serif" font-size="17" font-weight="700">W</text>
  <text x="66" y="37" class="title">WakaTime</text>
  <text x="66" y="57" class="subtitle">Top languages · last 7 days</text>
  <text x="608" y="31" class="subtitle" text-anchor="end">TOTAL TIME</text>
  <text x="608" y="52" class="total" text-anchor="end">{total_text}</text>
  <line x1="26" y1="78" x2="614" y2="78" stroke="#334155" />
{rows_markup}
  <text x="32" y="300" class="subtitle">Updated from my public WakaTime profile</text>
</svg>
'''


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


def update_svg(svg: str) -> bool:
    if SVG_CARD.exists() and SVG_CARD.read_text(encoding="utf-8") == svg:
        return False
    SVG_CARD.write_text(svg, encoding="utf-8")
    return True


if __name__ == "__main__":
    username = os.environ.get("WAKATIME_USERNAME", "AlohaYo")
    stats = fetch_stats(username)
    changed_readme = update_readme(render(stats))
    changed_svg = update_svg(render_svg(stats))
    if changed_readme or changed_svg:
        print("Updated WakaTime README and language card.")
    else:
        print("WakaTime stats and language card are already current.")
