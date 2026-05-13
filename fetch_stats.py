import os
import json
import requests
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["GH_TOKEN"]
USERNAME = "VedantJadhav701"

HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json",
}

STATS_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes {
        stargazerCount
        primaryLanguage { name color }
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
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    followers { totalCount }
    following { totalCount }
    repositories { totalCount }
  }
}
"""

def run_query(query, variables):
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data["data"]

def calc_streaks(weeks):
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda x: x[0])

    today = datetime.now(timezone.utc).date()
    
    # Current streak - go backwards from today
    current_streak = 0
    current_start = None
    check_date = today
    for date_str, count in reversed(days):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if d == check_date or d == check_date - timedelta(days=1):
            if count > 0:
                current_streak += 1
                current_start = date_str
                check_date = d - timedelta(days=1)
            elif d == today:
                check_date = today - timedelta(days=1)
                continue
            else:
                break
        elif d < check_date:
            if count > 0:
                current_streak += 1
                current_start = date_str
                check_date = d - timedelta(days=1)
            else:
                break

    # Longest streak
    longest = 0
    longest_start = None
    longest_end = None
    cur = 0
    cur_start = None
    for date_str, count in days:
        if count > 0:
            cur += 1
            if cur_start is None:
                cur_start = date_str
            if cur > longest:
                longest = cur
                longest_start = cur_start
                longest_end = date_str
        else:
            cur = 0
            cur_start = None

    return {
        "current": current_streak,
        "current_start": current_start,
        "longest": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
    }

def calc_languages(repos):
    lang_bytes = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"]
            size = edge["size"]
            if name not in lang_bytes:
                lang_bytes[name] = {"bytes": 0, "color": color}
            lang_bytes[name]["bytes"] += size

    total = sum(v["bytes"] for v in lang_bytes.values())
    if total == 0:
        return []

    langs = [
        {"name": k, "color": v["color"], "pct": round(v["bytes"] / total * 100, 2)}
        for k, v in lang_bytes.items()
    ]
    langs.sort(key=lambda x: x["pct"], reverse=True)
    return langs[:8]

def main():
    print(f"Fetching stats for {USERNAME}...")
    data = run_query(STATS_QUERY, {"login": USERNAME})
    user = data["user"]

    repos = user["repositories"]["nodes"]
    total_stars = sum(r["stargazerCount"] for r in repos)
    languages = calc_languages(repos)

    cc = user["contributionsCollection"]
    calendar = cc["contributionCalendar"]
    total_contributions = calendar["totalContributions"]
    streaks = calc_streaks(calendar["weeks"])

    stats = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "username": USERNAME,
        "public_repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "total_stars": total_stars,
        "total_commits": cc["totalCommitContributions"],
        "total_prs": cc["totalPullRequestContributions"],
        "total_issues": cc["totalIssueContributions"],
        "total_contributions": total_contributions,
        "streak": {
            "current": streaks["current"],
            "current_start": streaks["current_start"],
            "longest": streaks["longest"],
            "longest_start": streaks["longest_start"],
            "longest_end": streaks["longest_end"],
        },
        "languages": languages,
    }

    with open("stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print("stats.json written:")
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
