"""
generate_stats.py
Fetches real GitHub data via GraphQL API and produces:
  - assets/github-stats.svg   (embed in README as an image)
  - assets/stats.json         (raw data for shields.io dynamic badges)

Run locally:  GH_TOKEN=<your_pat> GH_USER=VedantJadhav701 python scripts/generate_stats.py
"""

import os
import json
import math
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
TOKEN    = os.environ["GH_TOKEN"]
USERNAME = os.environ.get("GH_USER", "VedantJadhav701")
OUT_DIR  = Path("assets")
OUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type":  "application/json",
}

# ── GraphQL query ────────────────────────────────────────────────────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers      { totalCount }
    following      { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { contributionCount date }
        }
      }
    }
  }
}
"""

# ── Helpers ──────────────────────────────────────────────────────────────────
def gql(query, variables):
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def calc_streaks(weeks):
    """Return current streak and longest streak from contribution calendar."""
    days = []
    for week in weeks:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort()

    today = datetime.now(timezone.utc).date()

    # ── current streak (count backwards from today) ──
    current = 0
    current_start = None
    expected = today
    for date_str, count in reversed(days):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if d > today:
            continue
        if d == expected or (d == expected - timedelta(1) and current == 0):
            if count > 0:
                current += 1
                current_start = date_str
                expected = d - timedelta(1)
            elif current == 0:
                expected = d - timedelta(1)
            else:
                break
        elif d < expected:
            break

    # ── longest streak ──
    longest = cur = 0
    longest_start = longest_end = cur_start = None
    for date_str, count in days:
        if count > 0:
            cur += 1
            if cur_start is None:
                cur_start = date_str
            if cur > longest:
                longest, longest_start, longest_end = cur, cur_start, date_str
        else:
            cur, cur_start = 0, None

    return dict(
        current=current,
        current_start=current_start,
        current_end=str(today),
        longest=longest,
        longest_start=longest_start,
        longest_end=longest_end,
    )


def calc_languages(repos):
    lang_bytes: dict = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            n = edge["node"]["name"]
            c = edge["node"]["color"] or "#8b949e"
            lang_bytes.setdefault(n, {"bytes": 0, "color": c})
            lang_bytes[n]["bytes"] += edge["size"]
    total = sum(v["bytes"] for v in lang_bytes.values()) or 1
    langs = [
        {"name": k, "color": v["color"], "pct": round(v["bytes"] / total * 100, 2)}
        for k, v in lang_bytes.items()
    ]
    langs.sort(key=lambda x: x["pct"], reverse=True)
    return langs[:6]


def fmt(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def date_range(start, end):
    if not start or not end:
        return ""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end,   "%Y-%m-%d")
    return f"{s.strftime('%d %b')} – {e.strftime('%d %b %Y')}"


# ── SVG generation ────────────────────────────────────────────────────────────
def lang_bar_svg(langs, x, y, w, h=10):
    """Render a segmented language bar."""
    parts = []
    cx = x
    for i, l in enumerate(langs):
        seg_w = round(l["pct"] / 100 * w, 2)
        rx_left  = h // 2 if i == 0 else 0
        rx_right = h // 2 if i == len(langs) - 1 else 0
        parts.append(
            f'<rect x="{cx}" y="{y}" width="{seg_w}" height="{h}" '
            f'rx="{max(rx_left, rx_right)}" fill="{l["color"]}"/>'
        )
        cx += seg_w
    return "\n".join(parts)


def build_svg(stats):
    s = stats
    W, H = 520, 450
    PAD = 20

    # contribution grid (mini) — last 26 weeks × 7 days
    weeks_data = s["raw_weeks"][-26:]
    cell = 7
    gap  = 2
    grid_x = PAD
    grid_y = 340
    levels = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

    grid_svg = []
    for wi, week in enumerate(weeks_data):
        for di, day in enumerate(week["contributionDays"]):
            c = day["contributionCount"]
            lvl = 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
            gx = grid_x + wi * (cell + gap)
            gy = grid_y + di * (cell + gap)
            grid_svg.append(
                f'<rect x="{gx}" y="{gy}" width="{cell}" height="{cell}" '
                f'rx="1" fill="{levels[lvl]}"/>'
            )

    grid_block = "\n    ".join(grid_svg)
    grid_w = len(weeks_data) * (cell + gap) - gap

    # language bar
    langs = s["languages"]
    lb = lang_bar_svg(langs, PAD, 268, W - PAD * 2, 12)

    # legend dots - fixed positioning to avoid overlap
    legend_parts = []
    
    # First row - 3 languages
    legend_y = 265
    for i, l in enumerate(langs[:3]):
        lx = PAD + (i * 155)
        legend_parts.append(
            f'<circle cx="{lx}" cy="{legend_y}" r="5" fill="{l["color"]}"/>'
            f'<text x="{lx + 12}" y="{legend_y - 2}" font-size="11" font-weight="600" fill="#e6edf3">'
            f'{l["name"]}</text>'
            f'<text x="{lx + 12}" y="{legend_y + 14}" font-size="10" fill="#58a6ff" font-weight="600">'
            f'{l["pct"]}%</text>'
        )
    
    # Second row - remaining 3 languages
    legend_y_2 = 295
    for i, l in enumerate(langs[3:6]):
        lx = PAD + (i * 155)
        legend_parts.append(
            f'<circle cx="{lx}" cy="{legend_y_2}" r="5" fill="{l["color"]}"/>'
            f'<text x="{lx + 12}" y="{legend_y_2 - 2}" font-size="11" font-weight="600" fill="#e6edf3">'
            f'{l["name"]}</text>'
            f'<text x="{lx + 12}" y="{legend_y_2 + 14}" font-size="10" fill="#58a6ff" font-weight="600">'
            f'{l["pct"]}%</text>'
        )

    legend = "\n    ".join(legend_parts)

    # streak dates
    cur_dates = date_range(s["streak"]["current_start"], s["streak"]["current_end"])
    lng_dates = date_range(s["streak"]["longest_start"], s["streak"]["longest_end"])

    updated = datetime.now(timezone.utc).strftime("%-d %b %Y")

    svg = f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"
     xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Vedant Jadhav GitHub stats card">
  <title>VedantJadhav701 GitHub Stats</title>

  <!-- Background with gradient -->
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0d1117;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#161b22;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <rect width="{W}" height="{H}" rx="12" fill="url(#bgGradient)"/>
  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#30363d" stroke-width="2"/>

  <!-- Header -->
  <text x="{PAD}" y="28" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="14" font-weight="700" fill="#f0883e">
    ⚡ VedantJadhav701 — GitHub Stats
  </text>
  <text x="{W - PAD}" y="28" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="10" fill="#8b949e" text-anchor="end">
    Updated {updated}
  </text>

  <line x1="{PAD}" y1="38" x2="{W - PAD}" y2="38" stroke="#21262d" stroke-width="2"/>

  <!-- Stat boxes - Row 1 -->
  <!-- Stars -->
  <g>
    <rect x="{PAD}" y="55" width="105" height="70" rx="10" fill="#1c2128" stroke="#21262d" stroke-width="1" filter="url(#shadow)"/>
    <text x="{PAD + 52}" y="82" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="20" font-weight="700" fill="#f0c040" text-anchor="middle">⭐</text>
    <text x="{PAD + 52}" y="102" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="22" font-weight="700" fill="#f0c040" text-anchor="middle">{fmt(s["total_stars"])}</text>
    <text x="{PAD + 52}" y="118" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="10" fill="#8b949e" text-anchor="middle">Stars</text>
  </g>

  <!-- Commits -->
  <g>
    <rect x="{PAD + 115}" y="55" width="105" height="70" rx="10" fill="#1c2128" stroke="#21262d" stroke-width="1"/>
    <text x="{PAD + 167}" y="82" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="20" font-weight="700" fill="#58a6ff" text-anchor="middle">💻</text>
    <text x="{PAD + 167}" y="102" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="22" font-weight="700" fill="#58a6ff" text-anchor="middle">{fmt(s["total_commits"])}</text>
    <text x="{PAD + 167}" y="118" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="10" fill="#8b949e" text-anchor="middle">Commits</text>
  </g>

  <!-- Contributions -->
  <g>
    <rect x="{PAD + 230}" y="55" width="105" height="70" rx="10" fill="#1c2128" stroke="#21262d" stroke-width="1"/>
    <text x="{PAD + 282}" y="82" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="20" font-weight="700" fill="#3fb950" text-anchor="middle">📊</text>
    <text x="{PAD + 282}" y="102" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="22" font-weight="700" fill="#3fb950" text-anchor="middle">{fmt(s["total_contributions"])}</text>
    <text x="{PAD + 282}" y="118" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="10" fill="#8b949e" text-anchor="middle">Contributions</text>
  </g>

  <!-- Current Streak (Full Width) -->
  <g>
    <rect x="{PAD}" y="140" width="{W - PAD * 2}" height="80" rx="10" fill="#1c2128" stroke="#f85149" stroke-width="2"/>
    <text x="{PAD + 15}" y="163" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="12" font-weight="600" fill="#f85149">🔥 CURRENT STREAK</text>
    <text x="{W - PAD - 15}" y="167" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="32" font-weight="700" fill="#f85149" text-anchor="end">{s["streak"]["current"]}</text>
    <text x="{W - PAD - 15}" y="187" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="11" fill="#8b949e" text-anchor="end">days</text>
    <text x="{PAD + 15}" y="185" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="11" fill="#8b949e">{cur_dates}</text>
    <text x="{PAD + 15}" y="210" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
          font-size="10" fill="#484f58">🏆 Longest: {s["streak"]["longest"]} days ({lng_dates})</text>
  </g>

  <!-- Separator line -->
  <line x1="{PAD}" y1="235" x2="{W - PAD}" y2="235" stroke="#21262d" stroke-width="1"/>

  <!-- Language bar title -->
  <text x="{PAD}" y="258" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="12" font-weight="600" fill="#e6edf3">📝 Top Languages</text>
  
  <!-- Language bar -->
  <rect x="{PAD}" y="268" width="{W - PAD * 2}" height="12" rx="6" fill="#161b22" stroke="#21262d" stroke-width="1"/>
  {lb}
  
  <!-- Legend - separated rows -->
  <g id="legend-row-1">
    {legend}
  </g>

  <!-- Separator line -->
  <line x1="{PAD}" y1="330" x2="{W - PAD}" y2="330" stroke="#21262d" stroke-width="1"/>

  <!-- Contribution grid title -->
  <text x="{PAD}" y="360" font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="12" font-weight="600" fill="#e6edf3">📈 Contributions (Last 26 Weeks)</text>
  
  <!-- Contribution grid -->
  {grid_block}

  <!-- Grid legend -->
  <text x="{PAD}" y="{grid_y + 50}"
        font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="9" fill="#8b949e">Less</text>
  {''.join(f'<rect x="{PAD + 35 + i*12}" y="{grid_y + 40}" width="8" height="8" rx="2" fill="{levels[i]}"/>' for i in range(5))}
  <text x="{PAD + 100}" y="{grid_y + 50}"
        font-family="&apos;Segoe UI&apos;,system-ui,sans-serif"
        font-size="9" fill="#8b949e">More</text>
</svg>"""

    return svg


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Fetching stats for @{USERNAME} …")
    data = gql(QUERY, {"login": USERNAME})
    user = data["user"]

    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    languages   = calc_languages(repos)

    cc      = user["contributionsCollection"]
    cal     = cc["contributionCalendar"]
    streaks = calc_streaks(cal["weeks"])

    stats = {
        "updated_at":          datetime.now(timezone.utc).isoformat(),
        "username":            USERNAME,
        "public_repos":        user["repositories"]["totalCount"],
        "followers":           user["followers"]["totalCount"],
        "following":           user["following"]["totalCount"],
        "total_stars":         total_stars,
        "total_commits":       cc["totalCommitContributions"],
        "total_prs":           cc["totalPullRequestContributions"],
        "total_issues":        cc["totalIssueContributions"],
        "total_contributions": cal["totalContributions"],
        "streak":              streaks,
        "languages":           languages,
        "raw_weeks":           cal["weeks"],          # used for SVG grid
    }

    # write stats.json (without raw_weeks to keep it clean)
    clean = {k: v for k, v in stats.items() if k != "raw_weeks"}
    json_path = OUT_DIR / "stats.json"
    json_path.write_text(json.dumps(clean, indent=2))
    print(f"✅ Wrote {json_path}")

    # write SVG
    svg_path = OUT_DIR / "github-stats.svg"
    svg_path.write_text(build_svg(stats))
    print(f"✅ Wrote {svg_path}")

    print("\nStats summary:")
    print(f"  Stars:         {total_stars}")
    print(f"  Commits:       {cc['totalCommitContributions']}")
    print(f"  Contributions: {cal['totalContributions']}")
    print(f"  Streak:        {streaks['current']} days (longest: {streaks['longest']})")


if __name__ == "__main__":
    main()
