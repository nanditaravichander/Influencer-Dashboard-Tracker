"""Data loading, cleaning and metric calculations. No Streamlit code in here."""
import io
import re

import numpy as np
import pandas as pd

TIER_ORDER = ["Nano", "Micro", "Mid", "Macro"]
TIER_BINS = [0, 10_000, 50_000, 250_000, float("inf")]  # Nano <10k, Micro 10-50k, Mid 50-250k, Macro 250k+

# Accepted column names (case and punctuation are ignored). First field = name used internally.
POST_ALIASES = {
    "date": ["date", "post date", "posted", "posted date", "month"],
    "creator": ["creator", "influencer", "handle", "creator name", "name"],
    "platform": ["platform", "channel", "network"],
    "followers": ["followers", "follower count", "audience"],
    "tier": ["tier", "creator tier"],
    "collaboration": ["collaboration", "collab type", "type", "gifted or paid", "gifted paid"],
    "campaign": ["campaign", "campaign name"],
    "reach": ["reach", "views", "impressions"],
    "engagements": ["engagements", "total engagements"],
    "likes": ["likes"],
    "comments": ["comments"],
    "shares": ["shares"],
    "saves": ["saves"],
    "fee": ["fee", "creator fee", "paid fee", "cost"],
    "product_value": ["product value", "product cost", "gifting value"],
    "disclosed": ["disclosed", "disclosure", "disclosed correctly", "ad label", "compliant"],
}
COMMUNITY_ALIASES = {
    "date": ["month", "date"],
    "new_contacts": ["new contacts", "contacts", "new creators", "new influencer contacts"],
}
UGC_ALIASES = {
    "date": ["month", "date"],
    "platform": ["platform", "channel"],
    "pieces": ["pieces", "ugc", "ugc pieces", "count", "posts"],
}
PLATFORM_FIXES = {
    "ig": "Instagram", "insta": "Instagram", "instagram": "Instagram",
    "tiktok": "TikTok", "tik tok": "TikTok", "tt": "TikTok",
    "youtube": "YouTube", "yt": "YouTube", "you tube": "YouTube",
}


class DataError(Exception):
    """Raised with a plain-English message when the uploaded file can't be used."""


def _key(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _rename(df, aliases):
    present = {_key(c): c for c in df.columns}
    mapping = {}
    for canon, names in aliases.items():
        for n in names:
            if _key(n) in present and present[_key(n)] not in mapping:
                mapping[present[_key(n)]] = canon
                break
    return df.rename(columns=mapping)


def _num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _to_bool(series):
    s = series.astype(str).str.strip().str.lower()
    out = pd.Series(pd.NA, index=series.index, dtype="boolean")
    out[s.isin(["yes", "y", "true", "1", "compliant", "ok"])] = True
    out[s.isin(["no", "n", "false", "0", "non compliant", "missing"])] = False
    return out


def read_upload(name, data):
    """Returns (posts_raw, community_raw, ugc_raw). Extra sheets are optional."""
    if name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(data)), None, None
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    by_name = {_key(k): v for k, v in sheets.items()}
    if "posts" in by_name:
        posts = by_name["posts"]
    else:
        candidates = [v for k, v in by_name.items() if k not in ("read me", "readme", "instructions")]
        if not candidates:
            raise DataError("The workbook has no data sheets. Add a sheet called 'Posts'.")
        posts = candidates[0]
    return posts, by_name.get("community"), by_name.get("ugc")


def prepare_posts(raw):
    warnings = []
    df = _rename(raw.dropna(how="all").copy(), POST_ALIASES)

    needed = {"date": "Date", "platform": "Platform", "reach": "Reach"}
    missing = [label for col, label in needed.items() if col not in df.columns]
    has_eng = "engagements" in df.columns or any(c in df.columns for c in ("likes", "comments", "shares", "saves"))
    if not has_eng:
        missing.append("Engagements (or Likes / Comments / Shares / Saves)")
    if missing:
        raise DataError("The Posts sheet is missing these columns: " + ", ".join(missing) + ".")

    if "creator" in df.columns:
        example = df["creator"].astype(str).str.lower().str.startswith("example creator")
        df = df[~example].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    bad = int(df["date"].isna().sum())
    if bad:
        warnings.append(f"{bad} row(s) were skipped because the date could not be read.")
        df = df[df["date"].notna()].copy()
    if df.empty:
        raise DataError("The Posts sheet has no usable rows yet. Add your posts below the headers and delete the example row.")

    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    p = df["platform"].astype(str).str.strip()
    df["platform"] = p.str.lower().map(PLATFORM_FIXES).fillna(p.str.title())
    df["reach"] = _num(df["reach"])
    if "engagements" in df.columns:
        df["engagements"] = _num(df["engagements"])
    else:
        df["engagements"] = sum(_num(df[c]) if c in df.columns else 0 for c in ("likes", "comments", "shares", "saves"))
    df["fee"] = _num(df["fee"]) if "fee" in df.columns else 0.0
    df["product_value"] = _num(df["product_value"]) if "product_value" in df.columns else 0.0
    df["cost"] = df["fee"] + df["product_value"]

    if "creator" not in df.columns:
        df["creator"] = "Unknown"
    df["creator"] = df["creator"].fillna("Unknown").astype(str)
    if "campaign" not in df.columns:
        df["campaign"] = "Uncategorised"
    df["campaign"] = df["campaign"].fillna("Uncategorised").astype(str)

    if "tier" in df.columns:
        t = df["tier"].astype(str).str.strip().str.title()
        df["tier"] = t.where(t.isin(TIER_ORDER), "Unknown")
    elif "followers" in df.columns:
        f = pd.to_numeric(df["followers"], errors="coerce")
        df["tier"] = pd.cut(f, TIER_BINS, labels=TIER_ORDER, right=False).astype(object).fillna("Unknown")
    else:
        df["tier"] = "Unknown"

    if "collaboration" in df.columns:
        s = df["collaboration"].astype(str).str.lower()
        inferred = np.where(df["fee"] > 0, "Paid", "Gifted")
        df["collaboration"] = np.where(s.str.contains("gift|unpaid"), "Gifted",
                                       np.where(s.str.contains("paid"), "Paid", inferred))
    else:
        df["collaboration"] = np.where(df["fee"] > 0, "Paid", "Gifted")

    df["disclosed"] = _to_bool(df["disclosed"]) if "disclosed" in df.columns else pd.Series(pd.NA, index=df.index, dtype="boolean")

    keep = ["date", "month", "creator", "platform", "tier", "collaboration", "campaign",
            "reach", "engagements", "fee", "product_value", "cost", "disclosed"]
    return df[keep].reset_index(drop=True), warnings


def prepare_community(raw):
    if raw is None or raw.dropna(how="all").empty:
        return None
    df = _rename(raw.dropna(how="all").copy(), COMMUNITY_ALIASES)
    if "date" not in df.columns or "new_contacts" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df[df["date"].notna()]
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["new_contacts"] = _num(df["new_contacts"])
    out = df.groupby("month", as_index=False)["new_contacts"].sum()
    return out if len(out) else None


def prepare_ugc(raw):
    if raw is None or raw.dropna(how="all").empty:
        return None
    df = _rename(raw.dropna(how="all").copy(), UGC_ALIASES)
    if "date" not in df.columns or "pieces" not in df.columns:
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df[df["date"].notna()]
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["pieces"] = _num(df["pieces"])
    if "platform" in df.columns:
        p = df["platform"].astype(str).str.strip()
        df["platform"] = p.str.lower().map(PLATFORM_FIXES).fillna(p.str.title())
    else:
        df["platform"] = "All"
    out = df[["month", "platform", "pieces"]]
    return out if len(out) else None


# ---------------- metrics ----------------

def summarise(d):
    reach, eng, cost = d["reach"].sum(), d["engagements"].sum(), d["cost"].sum()
    disc = d["disclosed"].dropna()
    return {
        "posts": len(d),
        "creators": d["creator"].nunique(),
        "reach": reach,
        "engagements": eng,
        "cost": cost,
        "er": eng / reach if reach else np.nan,
        "cpe": cost / eng if eng else np.nan,
        "avg_reach": reach / len(d) if len(d) else np.nan,
        "compliance": float(disc.astype(float).mean()) if len(disc) else np.nan,
        "undisclosed": int((~disc.astype(bool)).sum()) if len(disc) else 0,
        "checked": len(disc),
    }


def apply_filters(df, f, skip=()):
    m = pd.Series(True, index=df.index)
    if "date" not in skip:
        m &= (df["date"].dt.date >= f["start"]) & (df["date"].dt.date <= f["end"])
    if "platform" not in skip:
        m &= df["platform"].isin(f["platforms"])
    if "tier" not in skip:
        m &= df["tier"].isin(f["tiers"])
    if "collab" not in skip:
        m &= df["collaboration"].isin(f["collabs"])
    if "campaign" not in skip:
        m &= df["campaign"].isin(f["campaigns"])
    return df[m]


def monthly_table(d, all_months, start, end):
    g = d.groupby("month").agg(reach=("reach", "sum"), engagements=("engagements", "sum"),
                               cost=("cost", "sum"), content=("reach", "size"))
    g = g.reindex(all_months).fillna(0)
    g["er"] = np.where(g["reach"] > 0, g["engagements"] / g["reach"], np.nan)
    g["cpe"] = np.where(g["engagements"] > 0, g["cost"] / g["engagements"], np.nan)
    g.index.name = "month"
    g = g.reset_index()
    s, e = pd.Timestamp(start).to_period("M").to_timestamp(), pd.Timestamp(end).to_period("M").to_timestamp()
    g["in_range"] = (g["month"] >= s) & (g["month"] <= e)
    return g


def group_table(d, col, order=None):
    rows = []
    for key, g in d.groupby(col):
        r = summarise(g)
        r[col] = key
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    if order:
        out["_o"] = out[col].map({k: i for i, k in enumerate(order)}).fillna(len(order))
        out = out.sort_values("_o").drop(columns="_o")
    total_cost = out["cost"].sum()
    out["spend_share"] = out["cost"] / total_cost if total_cost else np.nan
    reach_total = out["reach"].sum()
    out["reach_share"] = out["reach"] / reach_total if reach_total else np.nan
    return out.reset_index(drop=True)


# ---------------- formatting ----------------

def compact(v):
    if v is None or pd.isna(v):
        return "–"
    v = float(v)
    if v >= 1e6:
        return f"{v / 1e6:.{0 if v >= 1e7 else 1}f}".rstrip("0").rstrip(".") + "M"
    if v >= 1e3:
        return f"{v / 1e3:.{0 if v >= 1e5 else 1}f}".rstrip("0").rstrip(".") + "k"
    return f"{v:.0f}"


def pct(v):
    return "–" if v is None or pd.isna(v) else f"{v * 100:.1f}%"


def gbp(v):
    return "–" if v is None or pd.isna(v) else f"£{v:,.2f}"


def gbp0(v):
    return "–" if v is None or pd.isna(v) else f"£{v:,.0f}"


def num(v):
    return "–" if v is None or pd.isna(v) else f"{v:,.0f}"


# ---------------- insights ----------------

def insights(df, f):
    cur = apply_filters(df, f)
    if cur.empty:
        return []
    out = []

    t = group_table(apply_filters(df, f, skip=("tier",)), "tier", TIER_ORDER)
    t = t[(t["posts"] >= 5) & (t["tier"].isin(TIER_ORDER))] if not t.empty else t
    if len(t) > 1:
        e, c, r = t.loc[t["er"].idxmax()], t.loc[t["cpe"].idxmin()], t.loc[t["avg_reach"].idxmax()]
        if e["tier"] == c["tier"]:
            lead = (f"{e['tier']} creators win on both quality and cost: the highest engagement rate ({pct(e['er'])}) "
                    f"and the lowest cost per engagement ({gbp(c['cpe'])}).")
        else:
            lead = (f"{e['tier']} creators earn the highest engagement rate at {pct(e['er'])}, and {c['tier']} creators "
                    f"are the cheapest per engagement at {gbp(c['cpe'])}.")
        out.append(f"{lead} {r['tier']} creators deliver the biggest average reach per post, at {compact(r['avg_reach'])}.")

    p = group_table(apply_filters(df, f, skip=("platform",)), "platform")
    p = p[p["posts"] >= 5] if not p.empty else p
    if len(p) > 1:
        e, c = p.loc[p["er"].idxmax()], p.loc[p["cpe"].idxmin()]
        out.append(f"{e['platform']} has the strongest engagement rate ({pct(e['er'])}), while {c['platform']} gives "
                   f"the lowest cost per engagement ({gbp(c['cpe'])}).")

    y = apply_filters(df, f, skip=("collab",))
    g, pd_ = summarise(y[y["collaboration"] == "Gifted"]), summarise(y[y["collaboration"] == "Paid"])
    if g["posts"] >= 5 and pd_["posts"] >= 5:
        out.append(f"Gifted posts cost {gbp(g['cpe'])} per engagement against {gbp(pd_['cpe'])} for paid collaborations, "
                   f"with engagement rates of {pct(g['er'])} and {pct(pd_['er'])}. Paid work buys reach; gifting buys efficiency.")

    s = summarise(cur)
    if s["checked"]:
        if s["undisclosed"] == 0:
            out.append("Every post with a disclosure check carried a clear label.")
        else:
            out.append(f"{s['undisclosed']:,} of {s['checked']:,} checked posts ({pct(s['undisclosed'] / s['checked'])}) "
                       "lacked a clear disclosure in this view. Flag these for creator follow-up under ASA and CMA guidance.")
    return out
