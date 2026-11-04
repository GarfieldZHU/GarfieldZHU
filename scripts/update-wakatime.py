#!/usr/bin/env python3
"""Refresh the shared WakaTime card and its profile README embed."""

import html
import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SVG_CARD = ROOT / "wakatime.svg"
SVG_VARIANTS = {
    ("en", "light"): ROOT / "wakatime-en-light.svg",
    ("en", "dark"): ROOT / "wakatime-en-dark.svg",
    ("zh-CN", "light"): ROOT / "wakatime-zh-CN-light.svg",
    ("zh-CN", "dark"): ROOT / "wakatime-zh-CN-dark.svg",
}
START = "<!--START_SECTION:waka-->"
END = "<!--END_SECTION:waka-->"
PROFILE_IMAGE_BASE = "https://raw.githubusercontent.com/GarfieldZHU/GarfieldZHU/master"
WAKATIME_URL = "https://wakatime.com/@AlohaYo"
CARD_WIDTH = 640
MAX_VISIBLE_LANGUAGES = 10
WAKATIME_TIMEOUT_SECONDS = 20
WAKATIME_MAX_ATTEMPTS = 4
WAKATIME_RETRY_DELAYS_SECONDS = (2, 5, 10)
CHINA_TIMEZONE = timezone(timedelta(hours=8))
SVG_SOURCE_RE = re.compile(r'(<text x="28" y="\d+" class="source">).*?(</text>)', re.DOTALL)
CARD_COPY = {
    "en": {
        "title": "Garfield Zhu's Coding Activities",
        "period": "LAST 7 DAYS",
        "period_description": "the last 7 days",
        "others": "Others",
        "empty": "No coding activity over the last 7 days.",
        "source": "Bars relative to largest entry · Data: WakaTime · GitHub Linguist colors",
        "description": "Coding activity over {period}: {total}. Languages shown: {languages}. Bars are scaled against the largest listed entry; percentages show each entry's share of total language time.",
    },
    "zh-CN": {
        "title": "Garfield Zhu 的编程活动",
        "period": "近 7 天",
        "period_description": "过去 7 天",
        "others": "其他",
        "empty": "过去 7 天没有编程活动。",
        "source": "条长相对最大项目 · 数据：WakaTime · 语言颜色：GitHub Linguist",
        "description": "{period}的编程活动：{total}。统计语言：{languages}。条长以最大项目为基准，占比表示该项占总语言用时的比例。",
    },
}
CARD_PALETTES = {
    "dark": {
        "card": "#0b1220",
        "border": "#263449",
        "title": "#f8fafc",
        "period": "#94a3b8",
        "total": "#e2e8f0",
        "language": "#e2e8f0",
        "duration": "#94a3b8",
        "track": "#334155",
        "empty": "#cbd5e1",
        "source": "#64748b",
        "dot_outline": "#ffffff",
        "dot_outline_opacity": ".28",
    },
    "light": {
        "card": "#ffffff",
        "border": "#d8e1ec",
        "title": "#172033",
        "period": "#64748b",
        "total": "#334155",
        "language": "#263449",
        "duration": "#64748b",
        "track": "#e2e8f0",
        "empty": "#64748b",
        "source": "#64748b",
        "dot_outline": "#0f172a",
        "dot_outline_opacity": ".14",
    },
}
LANGUAGE_COLORS = {
    "c": "#555555",
    "c#": "#178600",
    "c++": "#f34b7d",
    "css": "#563d7c",
    "go": "#00ADD8",
    "html": "#e34c26",
    "java": "#b07219",
    "javascript": "#f1e05a",
    "json": "#292929",
    "kotlin": "#A97BFF",
    "markdown": "#083fa1",
    "php": "#4F5D95",
    "python": "#3572A5",
    "ruby": "#701516",
    "rust": "#dea584",
    "shell": "#89e051",
    "shell script": "#89e051",
    "swift": "#F05138",
    "toml": "#9c4221",
    "typescript": "#3178c6",
    "yaml": "#cb171e",
}
OTHER_COLOR = "#718096"


class RetryableStatsError(RuntimeError):
    """WakaTime may return a usable response after a short delay."""


class NonRetryableStatsError(RuntimeError):
    """The public stats cannot be fetched without a configuration change."""


def validate_stats(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise RetryableStatsError("the API response was not a JSON object")

    stats = payload.get("data")
    if not isinstance(stats, dict) or stats.get("status") != "ok":
        status = stats.get("status", "missing") if isinstance(stats, dict) else "missing"
        raise RetryableStatsError(f"the API returned stats status {status!r}")

    if stats.get("is_coding_activity_visible") is False:
        raise NonRetryableStatsError("WakaTime coding activity is not publicly visible")
    if stats.get("is_coding_activity_visible") is not True:
        raise RetryableStatsError("the API did not confirm that coding activity is visible")
    if stats.get("is_up_to_date") is not True:
        raise RetryableStatsError("WakaTime is still calculating the latest stats")
    if stats.get("range") != "last_7_days":
        raise RetryableStatsError("the API returned a stats range other than last_7_days")

    human_readable_total = stats.get("human_readable_total")
    if not isinstance(human_readable_total, str) or not human_readable_total.strip():
        raise RetryableStatsError("the API response did not include a readable total")
    if not isinstance(stats.get("languages"), list):
        raise RetryableStatsError("the API response did not include a language list")

    total_seconds = stats.get("total_seconds")
    if total_seconds is not None:
        try:
            parsed_total = float(total_seconds)
        except (TypeError, ValueError) as error:
            raise RetryableStatsError("the API returned an invalid total_seconds value") from error
        if not math.isfinite(parsed_total) or parsed_total < 0:
            raise RetryableStatsError("the API returned an invalid total_seconds value")

    for language in stats["languages"]:
        if not isinstance(language, dict):
            raise RetryableStatsError("the API returned an invalid language entry")
        try:
            seconds = float(language.get("total_seconds", 0) or 0)
        except (TypeError, ValueError) as error:
            raise RetryableStatsError("the API returned an invalid language duration") from error
        if not math.isfinite(seconds) or seconds < 0:
            raise RetryableStatsError("the API returned an invalid language duration")

    return stats


def fetch_stats_once(username: str) -> dict:
    encoded_username = quote(f"@{username}", safe="")
    url = f"https://api.wakatime.com/api/v1/users/{encoded_username}/stats/last_7_days"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "GarfieldZHU-profile"},
    )
    try:
        with urlopen(request, timeout=WAKATIME_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 429 or error.code >= 500:
            raise RetryableStatsError(f"WakaTime returned HTTP {error.code}") from error
        raise NonRetryableStatsError(f"WakaTime returned HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RetryableStatsError(f"WakaTime request failed: {error}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RetryableStatsError("WakaTime returned invalid JSON") from error

    return validate_stats(payload)


def fetch_stats(username: str) -> dict:
    last_error = None
    for attempt in range(1, WAKATIME_MAX_ATTEMPTS + 1):
        try:
            return fetch_stats_once(username)
        except NonRetryableStatsError:
            raise
        except RetryableStatsError as error:
            last_error = error
            if attempt == WAKATIME_MAX_ATTEMPTS:
                break

            delay = WAKATIME_RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"WakaTime attempt {attempt}/{WAKATIME_MAX_ATTEMPTS} failed: {error}. "
                f"Retrying in {delay}s."
            )
            time.sleep(delay)

    raise RuntimeError(
        f"WakaTime stats were unusable after {WAKATIME_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def render(_stats: dict, cache_version: str) -> str:
    """Embed the shared SVG card in the GitHub profile README."""
    light_image_url = f"{PROFILE_IMAGE_BASE}/wakatime-en-light.svg?v={cache_version}"
    dark_image_url = f"{PROFILE_IMAGE_BASE}/wakatime-en-dark.svg?v={cache_version}"
    fallback_image_url = f"{PROFILE_IMAGE_BASE}/wakatime.svg?v={cache_version}"
    return f'''<div align="center">
  <a href="{WAKATIME_URL}">
    <picture>
      <source media="(prefers-color-scheme: light)" srcset="{light_image_url}" />
      <source media="(prefers-color-scheme: dark)" srcset="{dark_image_url}" />
      <img src="{fallback_image_url}" width="640" alt="Garfield Zhu's coding activities over the last 7 days" />
    </picture>
  </a>
</div>'''


def compact_duration(seconds: float) -> str:
    minutes = max(0, round(float(seconds) / 60))
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m" if minutes else "<1m"


def language_rows(stats: dict) -> tuple[list[dict], float]:
    languages = []
    for language in stats.get("languages", []):
        name = str(language.get("name", "Unknown")).strip()
        seconds = float(language.get("total_seconds", 0) or 0)
        # WakaTime's built-in "Other" bucket is excluded from its public
        # language total, so keep it out of both the bars and denominator.
        if not name or name.casefold() == "other" or seconds <= 0:
            continue
        languages.append({"name": name, "total_seconds": seconds})

    languages.sort(key=lambda language: language["total_seconds"], reverse=True)
    total_seconds = sum(language["total_seconds"] for language in languages)

    if len(languages) > MAX_VISIBLE_LANGUAGES:
        visible = languages[:MAX_VISIBLE_LANGUAGES]
        remainder = languages[MAX_VISIBLE_LANGUAGES:]
        visible.append({
            "name": "Others",
            "total_seconds": sum(language["total_seconds"] for language in remainder),
        })
    else:
        visible = languages

    return visible, total_seconds


def render_svg(
    stats: dict,
    locale: str = "en",
    theme: str = "dark",
    freshness_label: str = "",
) -> str:
    copy = CARD_COPY.get(locale, CARD_COPY["en"])
    palette = CARD_PALETTES.get(theme, CARD_PALETTES["dark"])
    human_readable_total = stats.get("human_readable_total")
    if not human_readable_total:
        raise RuntimeError("WakaTime response did not include a total for the last seven days.")

    languages, total_language_seconds = language_rows(stats)
    largest_entry_seconds = max(
        (language["total_seconds"] for language in languages), default=0
    )
    total_seconds = float(stats.get("total_seconds") or total_language_seconds)
    total = compact_duration(total_seconds) if total_seconds > 0 else str(human_readable_total)
    total_text = html.escape(total, quote=True)

    margin = 28
    column_gap = 20
    column_width = (CARD_WIDTH - margin * 2 - column_gap) / 2
    rows_per_column = max(1, (len(languages) + 1) // 2)
    rows_top = 84
    row_height = 46
    footer_rule_y = rows_top + rows_per_column * row_height + 4
    card_height = footer_rule_y + 28

    rows = []
    for index, language in enumerate(languages):
        column = index % 2
        row = index // 2
        x = margin + column * (column_width + column_gap)
        y = rows_top + row * row_height
        seconds = language["total_seconds"]
        percent = (seconds / total_language_seconds * 100) if total_language_seconds else 0
        track_width = column_width - 16
        bar_width = (
            track_width * seconds / largest_entry_seconds
            if largest_entry_seconds > 0 else 0
        )
        source_name = language["name"]
        display_name = copy["others"] if source_name == "Others" else source_name
        name = html.escape(display_name, quote=True)
        duration = compact_duration(seconds)
        stats_label = html.escape(f"{duration} · {percent:.1f}%", quote=True)
        color = LANGUAGE_COLORS.get(source_name.casefold(), OTHER_COLOR)
        rows.append(
            f'''  <g class="language-row">
    <circle cx="{x + 4:.1f}" cy="{y + 5}" r="4" fill="{color}" stroke="{palette['dot_outline']}" stroke-opacity="{palette['dot_outline_opacity']}" />
    <text x="{x + 15:.1f}" y="{y + 9}" class="language">{name}</text>
    <text x="{x + column_width:.1f}" y="{y + 9}" class="duration" text-anchor="end">{stats_label}</text>
    <rect x="{x + 15:.1f}" y="{y + 18}" width="{track_width:.1f}" height="6" rx="3" class="track" />
    <rect x="{x + 15:.1f}" y="{y + 18}" width="{bar_width:.1f}" height="6" rx="3" fill="{color}" />
  </g>'''
        )

    if rows:
        rows_markup = "\n".join(rows)
    else:
        rows_markup = f'''  <text x="{margin}" y="{rows_top + 12}" class="empty">{html.escape(copy["empty"])}</text>'''

    language_names = ", ".join(
        copy["others"] if language["name"] == "Others" else language["name"]
        for language in languages
    ) or copy["empty"]
    description = html.escape(copy["description"].format(
        period=copy["period_description"], total=total, languages=language_names
    ), quote=True)
    title = html.escape(copy["title"], quote=True)
    period = html.escape(copy["period"], quote=True)
    source_text = f"{copy['source']} · {freshness_label}" if freshness_label else copy["source"]
    source = html.escape(source_text, quote=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{card_height}" viewBox="0 0 {CARD_WIDTH} {card_height}" role="img" aria-labelledby="title description">
  <title id="title">{title} · {period}</title>
  <desc id="description">{description}</desc>
  <defs>
    <style>
      .card {{ fill: {palette['card']}; stroke: {palette['border']}; stroke-width: 1.5; }}
      .title {{ fill: {palette['title']}; font: 600 18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: -.2px; }}
      .period {{ fill: {palette['period']}; font: 600 9px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 1px; }}
      .total {{ fill: {palette['total']}; font: 600 14px ui-monospace, SFMono-Regular, Menlo, monospace; }}
      .language {{ fill: {palette['language']}; font: 500 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .duration {{ fill: {palette['duration']}; font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }}
      .track {{ fill: {palette['track']}; }}
      .empty {{ fill: {palette['empty']}; font: 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .source {{ fill: {palette['source']}; font: 10px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    </style>
  </defs>
  <rect x="1" y="1" width="{CARD_WIDTH - 2}" height="{card_height - 2}" rx="15" class="card" />
  <text x="28" y="37" class="title">{title}</text>
  <line x1="477" y1="14" x2="477" y2="48" stroke="{palette['border']}" />
  <text x="612" y="23" class="period" text-anchor="end">{period}</text>
  <text x="612" y="43" class="total" text-anchor="end">{total_text}</text>
  <line x1="26" y1="61" x2="614" y2="61" stroke="{palette['border']}" />
{rows_markup}
  <line x1="26" y1="{footer_rule_y}" x2="614" y2="{footer_rule_y}" stroke="{palette['border']}" />
  <text x="28" y="{card_height - 10}" class="source">{source}</text>
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


def update_svg(path: Path, svg: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == svg:
        return False
    path.write_text(svg, encoding="utf-8")
    return True


def mark_svg_refresh_failed(path: Path, locale: str, cache_version: str) -> bool:
    if not path.exists():
        raise RuntimeError(f"Cannot retain the previous WakaTime card; missing {path.name}.")

    svg = path.read_text(encoding="utf-8")
    if locale == "zh-CN":
        freshness = f"WakaTime · 沿用缓存统计 · 刷新失败 · 生成于 {cache_version}（UTC+8）"
    else:
        freshness = f"WakaTime · cached stats · refresh failed · generated {cache_version} (UTC+8)"
    replacement = rf"\g<1>{html.escape(freshness, quote=True)}\g<2>"
    updated, count = SVG_SOURCE_RE.subn(replacement, svg, count=1)
    if count != 1:
        raise RuntimeError(f"Could not find a WakaTime card footer in {path.name}.")
    if updated == svg:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def shanghai_date() -> str:
    return datetime.now(timezone.utc).astimezone(CHINA_TIMEZONE).strftime("%Y-%m-%d")


def svg_paths() -> list[tuple[str, Path]]:
    variants = [(locale, path) for (locale, _theme), path in SVG_VARIANTS.items()]
    return [("en", SVG_CARD), *variants]


def refresh_with_cached_cards(cache_version: str, error: Exception) -> None:
    print(
        f"::warning::WakaTime refresh failed ({error}). Retaining the previous stats and "
        f"marking today's cards as cached."
    )
    changed_svg = False
    for locale, path in svg_paths():
        changed_svg = mark_svg_refresh_failed(path, locale, cache_version) or changed_svg
    update_readme(render({}, cache_version))
    if changed_svg:
        print(f"Refreshed all WakaTime card assets for {cache_version} using clearly marked cached stats.")
    else:
        print(f"WakaTime cards already show the cached state for {cache_version}.")


if __name__ == "__main__":
    username = os.environ.get("WAKATIME_USERNAME", "AlohaYo")
    cache_version = shanghai_date()
    try:
        stats = fetch_stats(username)
    except (RetryableStatsError, NonRetryableStatsError, RuntimeError) as error:
        refresh_with_cached_cards(cache_version, error)
    else:
        changed_readme = update_readme(render(stats, cache_version))
        freshness = f"Updated {cache_version} (UTC+8)"
        changed_svg = update_svg(
            SVG_CARD,
            render_svg(stats, "en", "dark", freshness_label=freshness),
        )
        for (locale, theme), path in SVG_VARIANTS.items():
            localized_freshness = (
                f"更新于 {cache_version}（UTC+8）" if locale == "zh-CN"
                else freshness
            )
            changed_svg = update_svg(
                path,
                render_svg(stats, locale, theme, freshness_label=localized_freshness),
            ) or changed_svg
        if changed_readme or changed_svg:
            print(f"Updated WakaTime README and language cards for {cache_version} (UTC+8).")
        else:
            print(f"WakaTime cards for {cache_version} (UTC+8) are already current.")
