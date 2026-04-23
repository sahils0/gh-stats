#!/usr/bin/env python3
"""
Fetch the current GitHub follower count for a user, append it to a CSV,
and regenerate an SVG chart showing the last 30 days.
"""

import csv
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
import json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_USER = "sahils0"
DATA_FILE = Path(__file__).parent.parent / "data" / "followers.csv"
SVG_FILE = Path(__file__).parent.parent / "assets" / "followers-30d.svg"
WINDOW = 30  # days to show in the chart

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_follower_count(token: str | None = None) -> int:
    """Return the current follower count for GITHUB_USER via the GitHub API."""
    url = f"https://api.github.com/users/{GITHUB_USER}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return int(data["followers"])


def load_csv(path: Path) -> list[tuple[str, int]]:
    """Load existing CSV rows as (date_str, count) tuples."""
    if not path.exists():
        return []
    rows: list[tuple[str, int]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["date"], int(row["followers"])))
    return rows


def save_csv(path: Path, rows: list[tuple[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "followers"])
        writer.writerows(rows)


def upsert_today(rows: list[tuple[str, int]], count: int) -> list[tuple[str, int]]:
    """Replace today's entry if it exists, otherwise append it."""
    today = date.today().isoformat()
    updated = [(d, c) for d, c in rows if d != today]
    updated.append((today, count))
    updated.sort(key=lambda x: x[0])
    return updated


def last_n_days(rows: list[tuple[str, int]], n: int) -> list[tuple[str, int]]:
    """Return the n most-recent rows, filling gaps with None counts."""
    if not rows:
        return []
    return rows[-n:]


# ---------------------------------------------------------------------------
# SVG generation (no external dependencies)
# ---------------------------------------------------------------------------

WIDTH = 800
HEIGHT = 300
PAD_LEFT = 60
PAD_RIGHT = 20
PAD_TOP = 20
PAD_BOTTOM = 50
CHART_W = WIDTH - PAD_LEFT - PAD_RIGHT
CHART_H = HEIGHT - PAD_TOP - PAD_BOTTOM
LINE_COLOR = "#2196F3"
DOT_COLOR = "#1565C0"
GRID_COLOR = "#e0e0e0"
BG_COLOR = "#ffffff"
TEXT_COLOR = "#333333"
AXIS_COLOR = "#555555"


def generate_svg(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return ""

    dates = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    n = len(counts)

    min_c = min(counts)
    max_c = max(counts)
    span = max_c - min_c if max_c != min_c else 1

    def cx(i: int) -> float:
        if n == 1:
            return PAD_LEFT + CHART_W / 2
        return PAD_LEFT + i * CHART_W / (n - 1)

    def cy(v: int) -> float:
        return PAD_TOP + CHART_H - (v - min_c) / span * CHART_H

    # Build polyline points
    pts = " ".join(f"{cx(i):.1f},{cy(c):.1f}" for i, c in enumerate(counts))

    # Y-axis grid lines & labels (5 ticks)
    grid_lines = []
    for t in range(5):
        val = min_c + t * span / 4
        y = cy(val)
        grid_lines.append(
            f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{PAD_LEFT + CHART_W}" y2="{y:.1f}" '
            f'stroke="{GRID_COLOR}" stroke-width="1"/>'
        )
        grid_lines.append(
            f'<text x="{PAD_LEFT - 6}" y="{y:.1f}" text-anchor="end" '
            f'dominant-baseline="middle" font-size="11" fill="{TEXT_COLOR}">'
            f"{int(val)}</text>"
        )

    # X-axis labels: show first, middle, last
    x_labels = []
    label_indices = [0, n // 2, n - 1] if n >= 3 else list(range(n))
    label_indices = sorted(set(label_indices))
    for i in label_indices:
        x = cx(i)
        x_labels.append(
            f'<text x="{x:.1f}" y="{PAD_TOP + CHART_H + 20}" text-anchor="middle" '
            f'font-size="11" fill="{TEXT_COLOR}">{dates[i]}</text>'
        )

    # Dots
    dots = []
    for i, c in enumerate(counts):
        dots.append(
            f'<circle cx="{cx(i):.1f}" cy="{cy(c):.1f}" r="3.5" '
            f'fill="{DOT_COLOR}"/>'
        )

    # Filled area under the line
    fill_pts = (
        f"{PAD_LEFT:.1f},{PAD_TOP + CHART_H:.1f} "
        + pts
        + f" {PAD_LEFT + CHART_W:.1f},{PAD_TOP + CHART_H:.1f}"
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" \
width="{WIDTH}" height="{HEIGHT}" style="font-family:sans-serif;background:{BG_COLOR}">
  <!-- background -->
  <rect width="{WIDTH}" height="{HEIGHT}" fill="{BG_COLOR}"/>
  <!-- grid -->
  {"".join(grid_lines)}
  <!-- filled area -->
  <polygon points="{fill_pts}" fill="{LINE_COLOR}" fill-opacity="0.12"/>
  <!-- line -->
  <polyline points="{pts}" fill="none" stroke="{LINE_COLOR}" stroke-width="2.5" \
stroke-linejoin="round" stroke-linecap="round"/>
  <!-- dots -->
  {"".join(dots)}
  <!-- x labels -->
  {"".join(x_labels)}
  <!-- axes -->
  <line x1="{PAD_LEFT}" y1="{PAD_TOP}" x2="{PAD_LEFT}" \
y2="{PAD_TOP + CHART_H}" stroke="{AXIS_COLOR}" stroke-width="1.5"/>
  <line x1="{PAD_LEFT}" y1="{PAD_TOP + CHART_H}" \
x2="{PAD_LEFT + CHART_W}" y2="{PAD_TOP + CHART_H}" \
stroke="{AXIS_COLOR}" stroke-width="1.5"/>
  <!-- title -->
  <text x="{WIDTH // 2}" y="14" text-anchor="middle" font-size="13" \
fill="{TEXT_COLOR}" font-weight="bold">Followers – last {WINDOW} days</text>
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    token = os.getenv("GITHUB_TOKEN")
    count = fetch_follower_count(token)
    print(f"Current followers for {GITHUB_USER}: {count}")

    rows = load_csv(DATA_FILE)
    rows = upsert_today(rows, count)
    save_csv(DATA_FILE, rows)
    print(f"Saved {len(rows)} rows to {DATA_FILE}")

    window_rows = last_n_days(rows, WINDOW)
    svg = generate_svg(window_rows)
    SVG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SVG_FILE.write_text(svg, encoding="utf-8")
    print(f"SVG chart written to {SVG_FILE}")


if __name__ == "__main__":
    main()
