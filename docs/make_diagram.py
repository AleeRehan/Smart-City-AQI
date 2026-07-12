"""
Renders docs/architecture.png — the medallion pipeline diagram.
Run once:  python make_diagram.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ---- palette ----
BRONZE = "#c98a3c"
SILVER = "#9aa4b0"
GOLD = "#d9b036"
SRC = "#5b8def"
API = "#8b7cf6"
ETL = "#1fb6a8"
DASH = "#22c3d6"
INK = "#1f2733"
LAYER_BG = "#f3f5f8"
LAYER_EDGE = "#d8dee6"

fig, ax = plt.subplots(figsize=(11, 13))
ax.set_xlim(0, 100)
ax.set_ylim(0, 118)
ax.axis("off")


def box(x, y, w, h, text, fc, tc="white", fs=11, bold=True, sub=None):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2",
        linewidth=0, facecolor=fc, mutation_aspect=1))
    weight = "bold" if bold else "normal"
    if sub:
        ax.text(x + w / 2, y + h * 0.62, text, ha="center", va="center",
                color=tc, fontsize=fs, fontweight=weight)
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
                color=tc, fontsize=fs - 3, alpha=0.9)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                color=tc, fontsize=fs, fontweight=weight)


def layer(x, y, w, h, label):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.4,rounding_size=2",
        linewidth=1.2, facecolor=LAYER_BG, edgecolor=LAYER_EDGE))
    ax.text(x + 1.5, y + h - 2.4, label, ha="left", va="center",
            color="#6b7683", fontsize=9.5, fontweight="bold")


def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
        linewidth=2, color="#7b8493", shrinkA=0, shrinkB=0))


# ---- title ----
ax.text(50, 114, "Smart City Air Quality — Pipeline Architecture",
        ha="center", fontsize=16, fontweight="bold", color=INK)
ax.text(50, 110.5, "Medallion architecture on Snowflake (Bronze · Silver · Gold)",
        ha="center", fontsize=10.5, color="#6b7683")

# ---- sources ----
box(12, 99, 32, 8, "IoT Simulator", SRC, sub="Python · 10 sensors · 5 cities")
box(56, 99, 32, 8, "OpenAQ V3 API", API, sub="Pakistan reference · requests")

# ---- ETL ----
box(30, 87, 40, 7.5, "Python ETL — Pandas", ETL,
    sub="clean · validate · AQI tag · dedup")
arrow(28, 99, 40, 94.5)   # iot -> etl
arrow(72, 99, 60, 94.5)   # openaq -> etl

# ---- Bronze layer ----
layer(8, 71, 84, 12, "SNOWFLAKE — BRONZE (RAW)")
box(12, 73, 36, 6.5, "RAW.IOT_READINGS", BRONZE, fs=10, sub="raw sensor readings")
box(52, 73, 36, 6.5, "RAW.OPENAQ_RAW", BRONZE, fs=10, sub="raw API readings")
arrow(45, 87, 30, 79.7)   # etl -> bronze iot  (loaders write bronze)
arrow(55, 87, 70, 79.7)   # etl -> bronze openaq

# ---- Silver layer ----
layer(8, 55, 84, 11, "SNOWFLAKE — SILVER (CLEAN)")
box(20, 56.5, 60, 6.5, "CLEAN.AQI_CLEAN", SILVER, tc=INK, fs=10,
    sub="validated · AQI category · health risk · both sources joined")
arrow(50, 71, 50, 63.2)   # bronze -> silver

# ---- Gold layer ----
layer(8, 39, 84, 11, "SNOWFLAKE — GOLD (ANALYTICS)")
box(20, 40.5, 60, 6.5, "ANALYTICS.CITY_DAILY", GOLD, tc=INK, fs=10,
    sub="avg / max / min AQI · avg PM2.5 · dominant risk · reading count")
arrow(50, 55, 50, 47.2)   # silver -> gold
ax.text(52, 51.4, "build_gold.py  ·  SQL INSERT…SELECT", ha="left", va="center",
        fontsize=8.5, color="#6b7683", style="italic")

# ---- Dashboard ----
box(30, 27, 40, 8, "Streamlit Dashboard", DASH,
    sub="KPIs · bar · trend · donut · source compare")
arrow(50, 39, 50, 35.2)   # gold -> dashboard

# ---- deliverables strip ----
ax.text(50, 21, "Deliverables", ha="center", fontsize=10, fontweight="bold", color=INK)
labels = ["D1 simulator", "D2 OpenAQ", "D3 ETL",
          "D4 Bronze", "D5 Silver+Gold", "D6 dashboard"]
n = len(labels)
w = 13
gap = 1.5
total = n * w + (n - 1) * gap
start = (100 - total) / 2
for i, lab in enumerate(labels):
    x = start + i * (w + gap)
    ax.add_patch(FancyBboxPatch(
        (x, 14), w, 4.5, boxstyle="round,pad=0.3,rounding_size=1.5",
        linewidth=1, facecolor="white", edgecolor=LAYER_EDGE))
    ax.text(x + w / 2, 16.25, lab, ha="center", va="center",
            fontsize=8, color=INK)

ax.text(50, 9, "Both sources load independently into Bronze · Silver validates & unifies · "
        "Gold aggregates per city per day",
        ha="center", fontsize=8.5, color="#8b949e")

plt.tight_layout()
fig.savefig("docs/architecture.png", dpi=170, bbox_inches="tight",
            facecolor="white")
print("Saved docs/architecture.png")
