"""Generates fictional sample data in the same format as the Excel template."""
import numpy as np
import pandas as pd

TIERS = [  # name, follower range, base engagement rate, probability of a paid collaboration
    ("Nano", (2000, 9500), 0.075, 0.05),
    ("Micro", (10500, 48000), 0.055, 0.35),
    ("Mid", (55000, 230000), 0.038, 0.80),
    ("Macro", (260000, 900000), 0.024, 1.00),
]
PLATFORMS = [  # name, creator share, reach factor, engagement factor
    ("Instagram", 0.48, 0.32, 1.00),
    ("TikTok", 0.38, 0.85, 1.12),
    ("YouTube", 0.14, 0.18, 0.72),
]
CAMPAIGNS = ["Christmas gift range", "Valentine's collab", "Spring launch",
             "Summer events", "Autumn relaunch", "Always-on seeding"]
MONTH_CAMPAIGN = [0, 0, 0, 1, 1, 2, 2, 5, 3, 3, 3, 4]
BOOST = [1.25, 1.35, 1.5, 1.0, 1.1, 1.05, 1.2, 0.9, 1.15, 1.3, 1.1, 1.25]
NEW_CONTACTS = [38, 52, 61, 44, 49, 58, 63, 55, 60, 57, 66, 65]
UGC_BASE = [110, 190, 240, 120, 150, 130, 160, 140, 170, 210, 180, 230]


def make_sample(seed: int = 2026, start: str = "2025-10-01"):
    rng = np.random.default_rng(seed)
    months = pd.date_range(start, periods=12, freq="MS")

    creators = []
    for cid in range(1, 151):
        t = rng.choice(4, p=[0.45, 0.35, 0.16, 0.04])
        p = rng.choice(3, p=[0.48, 0.38, 0.14])
        lo, hi = TIERS[t][1]
        join = 0 if rng.random() < 0.4 else int(rng.integers(0, 12))
        creators.append((cid, t, p, int(rng.uniform(lo, hi)), join))

    rows = []
    for m, month in enumerate(months):
        eligible = [c for c in creators if c[4] <= m]
        for _ in range(round(62 * BOOST[m])):
            cid, t, p, followers, _ = eligible[int(rng.integers(0, len(eligible)))]
            tier_name, _, base_er, paid_p = TIERS[t]
            plat_name, _, reach_f, er_f = PLATFORMS[p]
            paid = rng.random() < paid_p
            reach = followers * reach_f * rng.uniform(0.55, 1.6)
            if p == 1 and rng.random() < 0.08:
                reach *= rng.uniform(3, 7)
            er = base_er * er_f * rng.uniform(0.75, 1.3) * (1.08 if BOOST[m] > 1.2 else 1)
            eng = reach * er
            if t == 0:
                fee, prod = (rng.uniform(60, 140), 15) if paid else (0, rng.uniform(14, 26))
            elif t == 1:
                fee, prod = (rng.uniform(120, 420), 18) if paid else (0, rng.uniform(18, 32))
            elif t == 2:
                fee, prod = (rng.uniform(700, 2400), 30) if paid else (0, rng.uniform(30, 60))
            else:
                fee, prod = rng.uniform(3500, 8500), 25
            camp = 5 if rng.random() < 0.3 else MONTH_CAMPAIGN[m]
            split = rng.dirichlet([78, 6, 7, 9])
            disclosed = rng.random() < (0.94 + 0.05 * (m / 11))
            rows.append({
                "Date": (month + pd.Timedelta(days=int(rng.integers(0, 28)))).date(),
                "Creator": f"creator_{cid:03d}",
                "Platform": plat_name,
                "Followers": followers,
                "Collaboration": "Paid" if (paid or t == 3) else "Gifted",
                "Campaign": CAMPAIGNS[camp],
                "Reach": int(reach),
                "Likes": int(eng * split[0]),
                "Comments": int(eng * split[1]),
                "Shares": int(eng * split[2]),
                "Saves": int(eng * split[3]),
                "Fee": int(fee),
                "Product Value": int(prod),
                "Disclosed": "Yes" if disclosed else "No",
            })
    posts = pd.DataFrame(rows)

    community = pd.DataFrame({"Month": [m.date() for m in months], "New Contacts": NEW_CONTACTS})

    ugc_rows = []
    for m, month in enumerate(months):
        for name, share, _, _ in PLATFORMS:
            ugc_rows.append({"Month": month.date(), "Platform": name,
                             "Pieces": int(round(UGC_BASE[m] * share * rng.uniform(0.85, 1.15)))})
    ugc = pd.DataFrame(ugc_rows)
    return posts, community, ugc
