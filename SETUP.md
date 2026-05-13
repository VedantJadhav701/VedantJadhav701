# Setup Guide — GitHub Stats (5 minutes)

## What this does
A GitHub Action runs daily at 2 AM UTC. It:
1. Calls GitHub GraphQL API with your built-in GITHUB_TOKEN (no secrets needed)
2. Calculates real stars, commits, contributions, streaks, languages
3. Generates `assets/github-stats.svg` — a self-contained stats card
4. Commits the SVG back to your repo automatically

Your README embeds the SVG via raw.githubusercontent.com — always fresh.

---

## Step 1 — Copy files into your profile repo

Your profile repo is: github.com/VedantJadhav701/VedantJadhav701

Copy these files exactly:

```
VedantJadhav701/          ← your profile repo root
├── .github/
│   └── workflows/
│       └── update-stats.yml      ← copy this
├── scripts/
│   └── generate_stats.py         ← copy this
├── assets/                       ← create this empty folder (add a .gitkeep file)
└── README.md                     ← paste the stats section from README_STATS_SECTION.md
```

To create the assets folder on GitHub web UI:
- Click "Add file" → "Create new file"
- Type: `assets/.gitkeep`
- Commit it

---

## Step 2 — Trigger the Action manually (first run)

1. Go to your repo on GitHub
2. Click the **Actions** tab
3. On the left, click **"Update GitHub Stats Daily"**
4. Click **"Run workflow"** → **"Run workflow"** (green button)
5. Watch it run — takes about 20–30 seconds
6. After it finishes, `assets/github-stats.svg` will appear in your repo

---

## Step 3 — Paste the stats section into your README

Copy the content from `README_STATS_SECTION.md` and paste it into your `README.md`
where you want the stats to appear.

The key line is:
```markdown
![GitHub Stats](https://raw.githubusercontent.com/VedantJadhav701/VedantJadhav701/main/assets/github-stats.svg)
```

This loads the SVG file directly from your repo — no third-party service involved.

---

## After setup

- Action runs every day at 2 AM UTC automatically
- You can also trigger it manually anytime from the Actions tab
- No API keys, no secrets, no external services — uses the built-in GITHUB_TOKEN
- If the Action ever fails, check the Actions tab for logs

---

## Troubleshooting

**Action fails with "Resource not accessible"**
→ Go to repo Settings → Actions → General → Workflow permissions
→ Select "Read and write permissions" → Save

**SVG shows but streak is wrong**
→ Enable private contributions: GitHub Settings → Profile → tick "Include private contributions"
→ Re-run the Action manually

**assets/github-stats.svg not found in README**
→ Make sure you ran the Action at least once first
→ The file must exist in the repo before the README can load it
