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
MAX_VISIBLE_LANGUAGES = 12
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
# GitHub Linguist language colors and aliases; source: https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml
LANGUAGE_COLORS = {
    "1c enterprise": "#814CCC",
    "2-dimensional array": "#38761D",
    "4d": "#004289",
    "abap": "#E8274B",
    "abap cds": "#555e25",
    "abl": "#5ce600",
    "abuild": "#0D597F",
    "acfm": "#fa0f00",
    "ackrc": "#476732",
    "aconf": "#d12127",
    "actionscript": "#882B0F",
    "actionscript 3": "#882B0F",
    "actionscript3": "#882B0F",
    "ad block": "#800000",
    "ad block filters": "#800000",
    "ada": "#02f88c",
    "ada2005": "#02f88c",
    "ada95": "#02f88c",
    "adb": "#800000",
    "adblock": "#800000",
    "adblock filter list": "#800000",
    "adobe composite font metrics": "#fa0f00",
    "adobe font metrics": "#fa0f00",
    "adobe multiple font metrics": "#fa0f00",
    "advpl": "#403a40",
    "agda": "#315665",
    "ags": "#B9D9FF",
    "ags script": "#B9D9FF",
    "ahk": "#6594b9",
    "aidl": "#34EB6B",
    "aiken": "#640ff8",
    "al": "#3AA2B5",
    "aleo": "#154BF9",
    "algol": "#D1E0DB",
    "alloy": "#64C800",
    "alpine abuild": "#0D597F",
    "altium": "#A89663",
    "altium designer": "#A89663",
    "amfm": "#fa0f00",
    "ampl": "#E6EFBB",
    "angelscript": "#C7D7DC",
    "answer set programming": "#A9CC29",
    "ant build system": "#A9157E",
    "antlers": "#ff269e",
    "antlr": "#9DC3FF",
    "apache": "#d12127",
    "apacheconf": "#d12127",
    "apex": "#1797c0",
    "api blueprint": "#2ACCA8",
    "apkbuild": "#0D597F",
    "apl": "#5A8164",
    "apollo guidance computer": "#0B3D91",
    "apples": "#101F1F",
    "applescript": "#101F1F",
    "arc": "#aa2afe",
    "arexx": "#d90e09",
    "arkts": "#0080ff",
    "as3": "#882B0F",
    "ascii stl": "#373b5e",
    "asciidoc": "#73a0c5",
    "asm": "#6E4C13",
    "asp": "#6a40fd",
    "asp.net": "#9400ff",
    "aspectj": "#a957b0",
    "aspx": "#9400ff",
    "aspx-vb": "#9400ff",
    "assembly": "#6E4C13",
    "astro": "#ff5a03",
    "asymptote": "#ff0000",
    "ats": "#1ac620",
    "ats2": "#1ac620",
    "au3": "#1C3552",
    "augeas": "#9CC134",
    "autohotkey": "#6594b9",
    "autoit": "#1C3552",
    "autoit3": "#1C3552",
    "autoitscript": "#1C3552",
    "avro idl": "#0040FF",
    "awk": "#c30e9b",
    "b": "#da7666",
    "b (formal method)": "#8aa8c5",
    "b3d": "#00FFAE",
    "b4x": "#00e4ff",
    "ballerina": "#FF5000",
    "baml": "#a855f7",
    "bash": "#89e051",
    "basic": "#ff0000",
    "basic for android": "#00e4ff",
    "bat": "#C1F12E",
    "batch": "#C1F12E",
    "batchfile": "#C1F12E",
    "bazel": "#76d275",
    "bbcode": "#CAFF42",
    "be": "#15A13C",
    "beef": "#a52f4e",
    "berry": "#15A13C",
    "bh": "#12223c",
    "bibtex": "#778899",
    "bicep": "#519aba",
    "bikeshed": "#5562ac",
    "bird": "#b6d7e4",
    "bird2": "#b6d7e4",
    "bird3": "#b6d7e4",
    "bison": "#6A463F",
    "bitbake": "#00bce4",
    "blade": "#f7523f",
    "blitz3d": "#00FFAE",
    "blitzbasic": "#00FFAE",
    "blitzmax": "#cd6400",
    "blitzplus": "#00FFAE",
    "blp": "#3584E4",
    "blueprint": "#3584E4",
    "bluespec": "#12223c",
    "bluespec bh": "#12223c",
    "bluespec bsv": "#12223c",
    "bluespec classic": "#12223c",
    "bmax": "#cd6400",
    "boo": "#d4bec1",
    "boogie": "#c80fa0",
    "bplus": "#00FFAE",
    "bqn": "#2b7067",
    "brainfuck": "#2F2530",
    "brighterscript": "#66AABB",
    "brightscript": "#662D91",
    "browserslist": "#ffd539",
    "bru": "#F4AA41",
    "bsdmake": "#427819",
    "bsv": "#12223c",
    "buildstream": "#006bff",
    "byond": "#447265",
    "bzl": "#76d275",
    "c": "#555555",
    "c#": "#7355dd",
    "c++": "#f34b7d",
    "c3": "#2563eb",
    "cabal": "#483465",
    "cabal config": "#483465",
    "caddy": "#22b638",
    "caddyfile": "#22b638",
    "cadence": "#00ef8b",
    "cairo": "#ff4a48",
    "cairo zero": "#ff4a48",
    "cake": "#7355dd",
    "cakescript": "#7355dd",
    "cameligo": "#3be133",
    "cangjie": "#00868B",
    "cap cds": "#0092d1",
    "cap'n proto": "#c42727",
    "carbon": "#222222",
    "cask": "#c065db",
    "cds": "#0092d1",
    "ceylon": "#dfa535",
    "cfc": "#ed2cd6",
    "cfm": "#ed2cd6",
    "cfml": "#ed2cd6",
    "chapel": "#8dc63f",
    "chpl": "#8dc63f",
    "chuck": "#3f8000",
    "circom": "#707575",
    "cirru": "#ccccff",
    "clarion": "#db901e",
    "clarity": "#5546ff",
    "classic asp": "#6a40fd",
    "classic qbasic": "#008080",
    "classic quickbasic": "#008080",
    "classic visual basic": "#2c6353",
    "clean": "#3F85AF",
    "click": "#E4E6F3",
    "clipper": "#403a40",
    "clips": "#00A300",
    "clojure": "#db5855",
    "closure templates": "#0d948f",
    "cloud firestore security rules": "#FFA000",
    "clue": "#0009b5",
    "cmake": "#DA3434",
    "coccinelle": "#c94949",
    "codeql": "#140f46",
    "coffee": "#244776",
    "coffee-script": "#244776",
    "coffeescript": "#244776",
    "coldfusion": "#ed2cd6",
    "coldfusion cfc": "#ed2cd6",
    "coldfusion html": "#ed2cd6",
    "collada": "#F1A42B",
    "commit": "#F44D27",
    "common lisp": "#3fb68b",
    "common workflow language": "#B5314C",
    "component pascal": "#B0CE4E",
    "conf": "#d1dbe0",
    "containerfile": "#384d54",
    "cooklang": "#E15A29",
    "coq": "#d0b68c",
    "cperl": "#0298c3",
    "cpp": "#f34b7d",
    "cql": "#006091",
    "cron": "#ead7ac",
    "cron table": "#ead7ac",
    "crontab": "#ead7ac",
    "crystal": "#000100",
    "csharp": "#7355dd",
    "cson": "#244776",
    "csound": "#1a1a1a",
    "csound document": "#1a1a1a",
    "csound score": "#1a1a1a",
    "csound-csd": "#1a1a1a",
    "csound-orc": "#1a1a1a",
    "csound-sco": "#1a1a1a",
    "css": "#663399",
    "csv": "#237346",
    "cucumber": "#5B2063",
    "cuda": "#3A4E3A",
    "cue": "#5886E1",
    "curry": "#531242",
    "cweb": "#00007a",
    "cwl": "#B5314C",
    "cylc": "#00b3fd",
    "cypher": "#34c0eb",
    "cython": "#fedf5b",
    "d": "#ba595e",
    "d2": "#526ee8",
    "d2lang": "#526ee8",
    "dafny": "#FFEC25",
    "darcs patch": "#8eff23",
    "dart": "#00B4AB",
    "daslang": "#d3d3d3",
    "dataweave": "#003a52",
    "debian package control file": "#D70751",
    "delphi": "#E3F171",
    "denizenscript": "#FBEE96",
    "dhall": "#dfafff",
    "directx 3d file": "#aace60",
    "django": "#a52a22",
    "dlang": "#ba595e",
    "dm": "#447265",
    "dockerfile": "#384d54",
    "dogescript": "#cca760",
    "dosbatch": "#C1F12E",
    "dosini": "#d1dbe0",
    "dotenv": "#e5d559",
    "dpatch": "#8eff23",
    "dune": "#89421e",
    "dylan": "#6c616e",
    "e": "#ccce35",
    "earthfile": "#2af0ff",
    "earthly": "#2af0ff",
    "eask": "#c065db",
    "easybuild": "#069406",
    "ec": "#913960",
    "ecere projects": "#913960",
    "ecl": "#8a1267",
    "eclipse": "#001d9d",
    "ecmarkdown": "#eb8131",
    "ecmarkup": "#eb8131",
    "ecr": "#2e1052",
    "edge": "#0dffe0",
    "edgeql": "#31A7FF",
    "editor-config": "#fff1f2",
    "editorconfig": "#fff1f2",
    "eeschema schematic": "#2f4aab",
    "eex": "#6e4a7e",
    "eiffel": "#4d6977",
    "ejs": "#a91e50",
    "electronic business card": "#ee2647",
    "elisp": "#c065db",
    "elixir": "#8847B9",
    "elm": "#60B5CC",
    "elvish": "#55BB55",
    "elvish transcript": "#55BB55",
    "emacs": "#c065db",
    "emacs lisp": "#c065db",
    "emberscript": "#FFF4F3",
    "envrc": "#89e051",
    "eq": "#a78649",
    "erb": "#701516",
    "erlang": "#B83998",
    "esdl": "#31A7FF",
    "euphoria": "#FF790B",
    "f*": "#572e30",
    "f#": "#b845fc",
    "factor": "#636746",
    "fancy": "#7b9db4",
    "fantom": "#14253c",
    "faust": "#c37240",
    "fb": "#141AC9",
    "fennel": "#fff3d7",
    "figfont": "#FFDDBB",
    "figlet font": "#FFDDBB",
    "filebench wml": "#F6B900",
    "firrtl": "#2f632f",
    "fish": "#4aae47",
    "flatbuffers": "#ed284a",
    "flex": "#DBCA00",
    "flix": "#d44a45",
    "fluent": "#ffcc33",
    "flux": "#88ccff",
    "forth": "#341708",
    "fortran": "#4d41b1",
    "fortran free form": "#4d41b1",
    "foxpro": "#403a40",
    "fpp": "#d37327",
    "freebasic": "#141AC9",
    "freemarker": "#0050b2",
    "frege": "#00cafe",
    "fsharp": "#b845fc",
    "fstar": "#572e30",
    "ftl": "#0050b2",
    "futhark": "#5f021f",
    "g-code": "#D08CF2",
    "game maker language": "#71b417",
    "gaml": "#FFC766",
    "gams": "#f49a22",
    "gap": "#0000cc",
    "gcc machine description": "#FFCFAB",
    "gdscript": "#355570",
    "gdshader": "#478CBF",
    "gedcom": "#003058",
    "gemfile.lock": "#701516",
    "gemini": "#ff6900",
    "gemtext": "#ff6900",
    "genero 4gl": "#63408e",
    "genero per": "#d8df39",
    "genie": "#fb855d",
    "genshi": "#951531",
    "gentoo ebuild": "#9400ff",
    "gentoo eclass": "#9400ff",
    "geojson": "#292929",
    "gerber image": "#d20b00",
    "gf": "#ff0000",
    "gherkin": "#5B2063",
    "git attributes": "#F44D27",
    "git blame ignore revs": "#F44D27",
    "git commit": "#F44D27",
    "git config": "#F44D27",
    "git revision list": "#F44D27",
    "git-ignore": "#000000",
    "gitattributes": "#F44D27",
    "gitconfig": "#F44D27",
    "gitignore": "#000000",
    "gitmodules": "#F44D27",
    "gjs": "#F5835F",
    "gleam": "#ffaff3",
    "glimmer js": "#F5835F",
    "glimmer ts": "#3178c6",
    "glsl": "#5686a5",
    "glyph": "#c1ac7f",
    "gno": "#226c57",
    "gnolang": "#226c57",
    "gnuplot": "#f0a9f0",
    "go": "#00ADD8",
    "go checksums": "#00ADD8",
    "go mod": "#00ADD8",
    "go module": "#00ADD8",
    "go sum": "#00ADD8",
    "go template": "#00ADD8",
    "go work": "#00ADD8",
    "go work sum": "#00ADD8",
    "go workspace": "#00ADD8",
    "go.mod": "#00ADD8",
    "go.sum": "#00ADD8",
    "go.work": "#00ADD8",
    "go.work.sum": "#00ADD8",
    "godot resource": "#355570",
    "golang": "#00ADD8",
    "golo": "#88562A",
    "gosu": "#82937f",
    "gotmpl": "#00ADD8",
    "grace": "#615f8b",
    "gradle": "#02303a",
    "gradle kotlin dsl": "#02303a",
    "grammatical framework": "#ff0000",
    "graphql": "#e10098",
    "graphviz (dot)": "#2596be",
    "groff": "#ecdebe",
    "groovy": "#4298b8",
    "groovy server pages": "#4298b8",
    "gsc": "#FF6800",
    "gsp": "#4298b8",
    "gtk": "#7fe719",
    "gtk 1": "#7fe719",
    "gtk 2": "#7fe719",
    "gtkrc": "#7fe719",
    "gts": "#3178c6",
    "hack": "#878787",
    "haml": "#ece2a9",
    "handlebars": "#f7931e",
    "haproxy": "#106da9",
    "harbour": "#0e60e3",
    "hare": "#9d7424",
    "hashicorp configuration language": "#844FBA",
    "haskell": "#5e5086",
    "haxe": "#df7900",
    "hbs": "#f7931e",
    "hcl": "#844FBA",
    "heex": "#6e4a7e",
    "help": "#199f4b",
    "hip": "#4F3A4F",
    "hiveql": "#dce200",
    "hls playlist": "#179C7D",
    "hlsl": "#aace60",
    "hocon": "#9ff8ee",
    "holyc": "#ffefaf",
    "hoon": "#00b171",
    "hosts": "#308888",
    "hosts file": "#308888",
    "html": "#e34c26",
    "html+django": "#a52a22",
    "html+ecr": "#2e1052",
    "html+eex": "#6e4a7e",
    "html+erb": "#701516",
    "html+jinja": "#a52a22",
    "html+php": "#4f5d95",
    "html+razor": "#512be4",
    "html+ruby": "#701516",
    "htmlbars": "#f7931e",
    "htmldjango": "#a52a22",
    "http": "#005C9C",
    "hurl": "#FF0288",
    "hxml": "#f68712",
    "hy": "#7790B2",
    "hylang": "#7790B2",
    "ical": "#ec564c",
    "icalendar": "#ec564c",
    "idl": "#a3522f",
    "idris": "#b30000",
    "ignore": "#000000",
    "ignore list": "#000000",
    "igor": "#0000cc",
    "igor pro": "#0000cc",
    "igorpro": "#0000cc",
    "ijm": "#99AAFF",
    "il assembly": "#512BD4",
    "ilasm": "#512BD4",
    "ile rpg": "#2BDE21",
    "imagej macro": "#99AAFF",
    "imba": "#16cec6",
    "imhex": "#3a6be0",
    "imhex pattern language": "#3a6be0",
    "imhexpatternlanguage": "#3a6be0",
    "imhexpl": "#3a6be0",
    "inc": "#4F5D95",
    "ini": "#d1dbe0",
    "inno setup": "#264b99",
    "io": "#a9188d",
    "ioke": "#078193",
    "ipython notebook": "#DA5B0B",
    "isabelle": "#FEFE00",
    "isabelle root": "#FEFE00",
    "ispc": "#2D68B1",
    "j": "#9EEDFF",
    "jac": "#FC792D",
    "jai": "#ab8b4b",
    "janet": "#0886a5",
    "jar manifest": "#b07219",
    "jasmin": "#d03600",
    "jass": "#FF0303",
    "jass2": "#FF0303",
    "java": "#b07219",
    "java properties": "#2A6277",
    "java server page": "#4298b8",
    "java server pages": "#2A6277",
    "java template engine": "#2A6277",
    "javascript": "#f1e05a",
    "javascript+erb": "#f1e05a",
    "jcl": "#d90e09",
    "jest snapshot": "#15c213",
    "jetbrains mps": "#21D789",
    "jflex": "#DBCA00",
    "jinja": "#a52a22",
    "jison": "#56b3cb",
    "jison lex": "#56b3cb",
    "jolie": "#843179",
    "jq": "#c7254e",
    "jruby": "#701516",
    "js": "#f1e05a",
    "json": "#292929",
    "json with comments": "#292929",
    "json5": "#267CB9",
    "jsonc": "#292929",
    "jsoniq": "#40d47e",
    "jsonl": "#292929",
    "jsonld": "#0c479c",
    "jsonnet": "#0064bd",
    "jsp": "#2A6277",
    "jte": "#2A6277",
    "julia": "#a270ba",
    "julia repl": "#a270ba",
    "jupyter notebook": "#DA5B0B",
    "just": "#384d54",
    "justfile": "#384d54",
    "kaitai struct": "#773b37",
    "kak": "#6f8042",
    "kakounescript": "#6f8042",
    "kakscript": "#6f8042",
    "kcl": "#7ABABF",
    "kdl": "#ffb3b3",
    "kerboscript": "#41adf0",
    "keyvalues": "#f26025",
    "kframework": "#4195c5",
    "kicad layout": "#2f4aab",
    "kicad legacy layout": "#2f4aab",
    "kicad schematic": "#2f4aab",
    "koka": "#215166",
    "kolmafia ash": "#B9D9B9",
    "kotlin": "#A97BFF",
    "krl": "#28430A",
    "ksy": "#773b37",
    "kvlang": "#1da6e0",
    "labview": "#fede06",
    "lambdapi": "#8027a3",
    "langium": "#2c8c87",
    "lark": "#2980B9",
    "lasso": "#999999",
    "lassoscript": "#999999",
    "latex": "#3D6117",
    "latte": "#f2a542",
    "leex": "#6e4a7e",
    "leo": "#C4FFC2",
    "less": "#1d365d",
    "less-css": "#1d365d",
    "lex": "#DBCA00",
    "lfe": "#4C3023",
    "lhaskell": "#5e5086",
    "lhs": "#5e5086",
    "ligolang": "#0e74ff",
    "lilypond": "#9ccc7c",
    "liquid": "#67b8de",
    "liquidsoap": "#990066",
    "lisp": "#3fb68b",
    "litcoffee": "#244776",
    "literate agda": "#315665",
    "literate coffeescript": "#244776",
    "literate haskell": "#5e5086",
    "live-script": "#499886",
    "livecode script": "#0c5ba5",
    "livescript": "#499886",
    "llvm": "#185619",
    "llvm tablegen": "#6E8B3D",
    "lobster": "#f95428",
    "logtalk": "#295b9a",
    "lolcode": "#cc9900",
    "lookml": "#652B81",
    "ls": "#499886",
    "lsl": "#3d9970",
    "lua": "#000080",
    "luau": "#00A2FF",
    "m2": "#d8ffff",
    "m3u": "#179C7D",
    "m3u playlist": "#179C7D",
    "m68k": "#005daa",
    "macaulay2": "#d8ffff",
    "macruby": "#701516",
    "make": "#427819",
    "makefile": "#427819",
    "mako": "#7e858d",
    "man": "#ecdebe",
    "man page": "#ecdebe",
    "man-page": "#ecdebe",
    "manpage": "#ecdebe",
    "markdown": "#083fa1",
    "marko": "#42bff2",
    "markojs": "#42bff2",
    "mask": "#f97732",
    "mathematica": "#dd1100",
    "mathematical programming system": "#0530ad",
    "matlab": "#e16737",
    "max": "#c4a79c",
    "max/msp": "#c4a79c",
    "maxmsp": "#c4a79c",
    "maxscript": "#00a6a6",
    "mcfunction": "#E22837",
    "md": "#083fa1",
    "mdoc": "#ecdebe",
    "mdsvex": "#5f9ea0",
    "mdx": "#fcb32c",
    "mediawiki": "#fc5757",
    "mercury": "#ff2b2b",
    "mermaid": "#ff3670",
    "mermaid example": "#ff3670",
    "meson": "#007800",
    "metal": "#8f14e9",
    "metta": "#6a5acd",
    "mf": "#427819",
    "miniscript": "#4B4A56",
    "miniyaml": "#ff1111",
    "minizinc": "#06a9e6",
    "mint": "#02b046",
    "mirah": "#c7a938",
    "mirc script": "#3d57c3",
    "mlir": "#5EC8DB",
    "mma": "#dd1100",
    "modelica": "#de1d31",
    "modula-2": "#10253f",
    "modula-3": "#223388",
    "mojo": "#ff4c1f",
    "monkey c": "#8D6747",
    "moonbit": "#b92381",
    "moonscript": "#ff4585",
    "motoko": "#fbb03b",
    "motorola 68k assembly": "#005daa",
    "move": "#4a137a",
    "mps": "#21D789",
    "mql4": "#62A8D6",
    "mql5": "#4A76B8",
    "msil": "#512BD4",
    "mtml": "#b7e1f4",
    "mupad": "#244963",
    "mustache": "#724b3b",
    "nanorc": "#2d004d",
    "nargo": "#2f1f49",
    "nasal": "#1d2c4e",
    "nasm": "#6E4C13",
    "ncl": "#28431f",
    "nearley": "#990000",
    "nemerle": "#3d3c6e",
    "neosnippet": "#199f4b",
    "nesc": "#94B0C7",
    "netlinx": "#0aa0ff",
    "netlinx+erb": "#747faa",
    "netlogo": "#ff6375",
    "newlisp": "#87AED7",
    "nextflow": "#3ac486",
    "nginx": "#009639",
    "nginx configuration file": "#009639",
    "nickel": "#E0C3FC",
    "nim": "#ffc200",
    "nit": "#009917",
    "nix": "#7e7eff",
    "nixos": "#7e7eff",
    "njk": "#3d8137",
    "nmodl": "#00356B",
    "node": "#f1e05a",
    "noir": "#2f1f49",
    "npm config": "#cb3837",
    "npmrc": "#cb3837",
    "nroff": "#ecdebe",
    "nu": "#c9df40",
    "nu-script": "#4E9906",
    "numpy": "#9C8AF9",
    "nunjucks": "#3d8137",
    "nush": "#c9df40",
    "nushell": "#4E9906",
    "nushell-script": "#4E9906",
    "nvim": "#199f4b",
    "nwscript": "#111522",
    "oasv2": "#85ea2d",
    "oasv2-json": "#85ea2d",
    "oasv2-yaml": "#85ea2d",
    "oasv3": "#85ea2d",
    "oasv3-json": "#85ea2d",
    "oasv3-yaml": "#85ea2d",
    "obj-c": "#438eff",
    "obj-c++": "#6866fb",
    "obj-j": "#ff0c5a",
    "objc": "#438eff",
    "objc++": "#6866fb",
    "objective-c": "#438eff",
    "objective-c++": "#6866fb",
    "objective-j": "#ff0c5a",
    "objectivec": "#438eff",
    "objectivec++": "#6866fb",
    "objectivej": "#ff0c5a",
    "objectpascal": "#E3F171",
    "objectscript": "#424893",
    "objj": "#ff0c5a",
    "ocaml": "#ef7a08",
    "octave": "#e16737",
    "odin": "#60AFFE",
    "odin-lang": "#60AFFE",
    "odinlang": "#60AFFE",
    "omgrofl": "#cabbff",
    "omnet++ msg": "#a0e0a0",
    "omnet++ ned": "#08607c",
    "omnetpp-msg": "#a0e0a0",
    "omnetpp-ned": "#08607c",
    "ooc": "#b0b77e",
    "opal": "#f7ede0",
    "open policy agent": "#7d9199",
    "openapi specification v2": "#85ea2d",
    "openapi specification v3": "#85ea2d",
    "opencl": "#ed2e2d",
    "openedge": "#5ce600",
    "openedge abl": "#5ce600",
    "openqasm": "#AA70FF",
    "openscad": "#e5cd45",
    "opentofu": "#844FBA",
    "option list": "#476732",
    "opts": "#476732",
    "opy": "#78b355",
    "org": "#77aa99",
    "osascript": "#101F1F",
    "overpassql": "#cce2aa",
    "overpy": "#78b355",
    "oxygene": "#cdd0e3",
    "oz": "#fab738",
    "p4": "#7055b5",
    "pact": "#F7A8B8",
    "pan": "#cc0000",
    "pandoc": "#083fa1",
    "papyrus": "#6600cc",
    "parrot": "#f3ca0a",
    "pascal": "#E3F171",
    "pawn": "#dbb284",
    "pcbnew": "#2f4aab",
    "pddl": "#0d00ff",
    "peg.js": "#234d6b",
    "pep8": "#C76F5B",
    "perl": "#0298c3",
    "perl-6": "#0000fb",
    "perl6": "#0000fb",
    "php": "#4F5D95",
    "picolisp": "#6067af",
    "piglatin": "#fcd7de",
    "pike": "#005390",
    "pip requirements": "#FFD343",
    "pkg-config": "#2b5e82",
    "pkgconf": "#2b5e82",
    "pkl": "#6b9543",
    "plantuml": "#fbbd16",
    "plpgsql": "#336790",
    "plsql": "#dad8d8",
    "pogoscript": "#d80074",
    "polar": "#ae81ff",
    "portugol": "#f8bd00",
    "posh": "#012456",
    "postcss": "#dc3a0c",
    "postscr": "#da291c",
    "postscript": "#da291c",
    "pov-ray": "#6bac65",
    "pov-ray sdl": "#6bac65",
    "povray": "#6bac65",
    "power query": "#d38e0d",
    "powerbuilder": "#8f0f8d",
    "powerquery": "#d38e0d",
    "powershell": "#012456",
    "praat": "#c8506d",
    "prisma": "#0c344b",
    "pro*c": "#bb8368",
    "processing": "#0096D8",
    "procfile": "#3B2F63",
    "progress": "#5ce600",
    "prolog": "#74283c",
    "promela": "#de0000",
    "propeller spin": "#7fa2a7",
    "pug": "#a86454",
    "puppet": "#302B6D",
    "purebasic": "#5a6986",
    "purescript": "#1D222D",
    "pwsh": "#012456",
    "py": "#3572A5",
    "py3": "#3572A5",
    "pycon": "#3572A5",
    "pyret": "#ee1e10",
    "pyrex": "#fedf5b",
    "python": "#3572A5",
    "python console": "#3572A5",
    "python traceback": "#3572A5",
    "python3": "#3572A5",
    "q": "#0040cd",
    "q#": "#fed659",
    "qb": "#008080",
    "qb64": "#008080",
    "qbasic": "#008080",
    "ql": "#140f46",
    "qml": "#44a51c",
    "qsharp": "#fed659",
    "qt script": "#00b841",
    "quake": "#882233",
    "quakec": "#975777",
    "quartus simulation ip": "#58C42E",
    "quickbasic": "#008080",
    "quint": "#9d6ce5",
    "r": "#198CE7",
    "racket": "#3c5caa",
    "ragel": "#9d5200",
    "ragel-rb": "#9d5200",
    "ragel-ruby": "#9d5200",
    "rake": "#701516",
    "raku": "#0000fb",
    "raml": "#77d9fb",
    "rascal": "#fffaa0",
    "rascript": "#2C97FA",
    "razor": "#512be4",
    "rb": "#701516",
    "rbs": "#701516",
    "rbx": "#701516",
    "rdoc": "#701516",
    "reason": "#ff5847",
    "reasonligo": "#ff5847",
    "rebol": "#358a5b",
    "record jar": "#0673ba",
    "red": "#f50000",
    "red/system": "#f50000",
    "redscript": "#f44336",
    "regex": "#009a00",
    "regexp": "#009a00",
    "regular expression": "#009a00",
    "ren'py": "#ff7f7f",
    "renpy": "#ff7f7f",
    "rescript": "#ed5051",
    "restructuredtext": "#141414",
    "rexx": "#d90e09",
    "rez": "#FFDAB3",
    "rhai": "#FBA63B",
    "rhtml": "#701516",
    "ring": "#2D54CB",
    "riot": "#A71E49",
    "rmarkdown": "#198ce7",
    "robotframework": "#00c0b5",
    "roc": "#7c38f5",
    "rocq": "#d0b68c",
    "rocq prover": "#d0b68c",
    "roff": "#ecdebe",
    "roff manpage": "#ecdebe",
    "ron": "#a62c00",
    "ros interface": "#22314e",
    "rosmsg": "#22314e",
    "rouge": "#cc0088",
    "routeros script": "#DE3941",
    "rpgle": "#2BDE21",
    "rs": "#dea584",
    "rs-274x": "#d20b00",
    "rscript": "#198CE7",
    "rss": "#0060ac",
    "rst": "#141414",
    "ruby": "#701516",
    "runoff": "#665a4e",
    "rust": "#dea584",
    "rusthon": "#3572A5",
    "sail": "#259dd5",
    "salt": "#57bcad",
    "saltstack": "#57bcad",
    "saltstate": "#57bcad",
    "sarif": "#292929",
    "sas": "#B34936",
    "sass": "#a53b70",
    "scala": "#c22d40",
    "scaml": "#bd181a",
    "scenic": "#fdc700",
    "scheme": "#1e4aec",
    "scilab": "#ca0f21",
    "scss": "#c6538c",
    "sdc": "#e4cc98",
    "sed": "#64b970",
    "self": "#0579aa",
    "sfv": "#C9BFED",
    "sh": "#89e051",
    "shaderlab": "#222c37",
    "shell": "#89e051",
    "shell script": "#89e051",
    "shell-script": "#89e051",
    "shellcheck config": "#cecfcb",
    "shellcheckrc": "#cecfcb",
    "shen": "#120F14",
    "simple file verification": "#C9BFED",
    "singularity": "#64E6AD",
    "sip": "#4E8D83",
    "slang": "#1fbec9",
    "slash": "#007eff",
    "slice": "#003fa2",
    "slim": "#2b2b2b",
    "slint": "#2379F4",
    "smalltalk": "#596706",
    "smarty": "#f0c040",
    "smithy": "#c44536",
    "sml": "#dc566d",
    "smpl": "#c94949",
    "snakefile": "#419179",
    "snakemake": "#419179",
    "snipmate": "#199f4b",
    "snippet": "#32AB90",
    "solidity": "#AA6746",
    "sourcemod": "#f69e1d",
    "sourcepawn": "#f69e1d",
    "soy": "#0d948f",
    "sparql": "#0C4597",
    "spicedb schema": "#a5318a",
    "splus": "#198CE7",
    "sqf": "#3F3F3F",
    "sql": "#e38c00",
    "sqlpl": "#e38c00",
    "sqlrpgle": "#2BDE21",
    "squeak": "#596706",
    "squirrel": "#800000",
    "srecode template": "#348a34",
    "stan": "#b2011d",
    "standard ml": "#dc566d",
    "starlark": "#76d275",
    "stata": "#1a5f91",
    "stl": "#373b5e",
    "stla": "#373b5e",
    "stringtemplate": "#3fb34f",
    "stylus": "#ff6347",
    "subrip text": "#9e0101",
    "sugarss": "#2fcc9f",
    "supercollider": "#46390b",
    "surql": "#ff00a0",
    "surrealql": "#ff00a0",
    "survex data": "#ffcc99",
    "svelte": "#ff3e00",
    "svg": "#ff9900",
    "sway": "#00F58C",
    "sweave": "#198ce7",
    "swift": "#F05138",
    "systemverilog": "#DAE1C2",
    "tab-seperated values": "#237346",
    "tablegen": "#6E8B3D",
    "tabular model definition language": "#f0c913",
    "tact": "#48b5ff",
    "talon": "#333333",
    "tcl": "#e4cc98",
    "teal": "#00B1BC",
    "templ": "#66D0DD",
    "terra": "#00004c",
    "terraform": "#844FBA",
    "terraform template": "#7b42bb",
    "tex": "#3D6117",
    "textgrid": "#c8506d",
    "textile": "#ffe7ac",
    "textmate properties": "#df66e4",
    "thrift": "#D12127",
    "ti program": "#A0AA87",
    "tl-verilog": "#C40023",
    "tla": "#4b0079",
    "tm-properties": "#df66e4",
    "tmdl": "#f0c913",
    "toit": "#c2c9fb",
    "tolk": "#30A1F5",
    "toml": "#9c4221",
    "topojson": "#292929",
    "tor config": "#59316b",
    "torrc": "#59316b",
    "tree-sitter query": "#8ea64c",
    "troff": "#ecdebe",
    "ts": "#3178c6",
    "tsp": "#4A3665",
    "tsq": "#8ea64c",
    "tsql": "#e38c00",
    "tsv": "#237346",
    "tsx": "#3178c6",
    "turing": "#cf142b",
    "twig": "#c1d026",
    "txl": "#0178b8",
    "typ": "#239dad",
    "typescript": "#3178c6",
    "typescriptreact": "#3178c6",
    "typespec": "#4A3665",
    "typst": "#239dad",
    "ucode": "#00b8d4",
    "ultisnip": "#199f4b",
    "ultisnips": "#199f4b",
    "unified parallel c": "#4e3617",
    "unity3d asset": "#222c37",
    "uno": "#9933cc",
    "unrealscript": "#a54c4d",
    "untyped plutus core": "#36adbd",
    "ur": "#ccccee",
    "ur/web": "#ccccee",
    "urweb": "#ccccee",
    "v": "#4f87c4",
    "vala": "#a56de2",
    "valve data format": "#f26025",
    "vb .net": "#945db7",
    "vb 6": "#2c6353",
    "vb.net": "#945db7",
    "vb6": "#2c6353",
    "vba": "#867db1",
    "vbnet": "#945db7",
    "vbscript": "#15dcdc",
    "vcard": "#ee2647",
    "vcl": "#148AA8",
    "vdf": "#f26025",
    "velocity": "#507cff",
    "velocity template language": "#507cff",
    "vento": "#ff0080",
    "verilog": "#b2b7f8",
    "verse": "#518ef8",
    "vespa": "#61D790",
    "vespa schema definition": "#61D790",
    "vhdl": "#adb2cb",
    "vim": "#199f4b",
    "vim help file": "#199f4b",
    "vim script": "#199f4b",
    "vim snippet": "#199f4b",
    "vimhelp": "#199f4b",
    "viml": "#199f4b",
    "vimscript": "#199f4b",
    "virtual contact file": "#ee2647",
    "visual basic": "#945db7",
    "visual basic .net": "#945db7",
    "visual basic 6": "#2c6353",
    "visual basic 6.0": "#2c6353",
    "visual basic classic": "#2c6353",
    "visual basic for applications": "#867db1",
    "vlang": "#4f87c4",
    "volt": "#1F1F1F",
    "vtl": "#507cff",
    "vue": "#41b883",
    "vyper": "#9F4CF2",
    "wasm": "#04133b",
    "wast": "#04133b",
    "wdl": "#42f1f4",
    "web ontology language": "#5b70bd",
    "webassembly": "#04133b",
    "webassembly interface type": "#6250e7",
    "wgsl": "#1a5e9a",
    "whiley": "#d5c397",
    "wiki": "#fc5757",
    "wikitext": "#fc5757",
    "winbatch": "#C1F12E",
    "windows registry entries": "#52d5ff",
    "wisp": "#7582D1",
    "wit": "#6250e7",
    "witcher script": "#ff0000",
    "wl": "#dd1100",
    "wolfram": "#dd1100",
    "wolfram lang": "#dd1100",
    "wolfram language": "#dd1100",
    "wollok": "#a23738",
    "workflow description language": "#42f1f4",
    "world of warcraft addon data": "#f7e43f",
    "wren": "#383838",
    "wrenlang": "#383838",
    "wsdl": "#0060ac",
    "x10": "#4B6BEF",
    "xbase": "#403a40",
    "xc": "#99DA07",
    "xdc": "#e4cc98",
    "xhtml": "#e34c26",
    "xmake": "#22a079",
    "xml": "#0060ac",
    "xml property list": "#0060ac",
    "xml+genshi": "#951531",
    "xml+kid": "#951531",
    "xojo": "#81bd41",
    "xonsh": "#285EEF",
    "xquery": "#5232e7",
    "xsd": "#0060ac",
    "xsl": "#EB8CEB",
    "xslt": "#EB8CEB",
    "xten": "#4B6BEF",
    "xtend": "#24255d",
    "yacc": "#4B6C4B",
    "yaml": "#cb171e",
    "yara": "#220000",
    "yas": "#32AB90",
    "yasnippet": "#32AB90",
    "yml": "#cb171e",
    "yul": "#794932",
    "zap": "#0d665e",
    "zenscript": "#00BCD1",
    "zephir": "#118f9e",
    "zig": "#ec915c",
    "zil": "#dc75e5",
    "zimpl": "#d67711",
    "zmodel": "#ff7100",
    "zsh": "#89e051",
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
