"""Influencer performance dashboard (Streamlit).

Run locally:   streamlit run app.py
Upload an Excel workbook (see influencer-data-template.xlsx) and every chart updates.
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import logic as L
from sample_data import make_sample

st.set_page_config(page_title="Influencer performance dashboard", page_icon="📊", layout="wide")

ACCENT = "#5438DC"
TIER_COLOURS = {"Nano": "#12A18A", "Micro": "#5438DC", "Mid": "#E0407F", "Macro": "#E59A1E", "Unknown": "#8884A0"}
HERE = Path(__file__).parent


def stretch(fn, *args, **kwargs):
    """Full-width rendering that works on both older and newer Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


@st.cache_data(show_spinner="Reading your workbook...")
def load_upload(name, data):
    raw_posts, raw_comm, raw_ugc = L.read_upload(name, data)
    posts, warnings = L.prepare_posts(raw_posts)
    return posts, L.prepare_community(raw_comm), L.prepare_ugc(raw_ugc), warnings


@st.cache_data
def load_sample():
    raw_posts, raw_comm, raw_ugc = make_sample()
    posts, _ = L.prepare_posts(raw_posts)
    return posts, L.prepare_community(raw_comm), L.prepare_ugc(raw_ugc), []


# ------------------------------------------------------------------ sidebar: data
with st.sidebar:
    st.header("Your data")
    upload = st.file_uploader("Upload an Excel or CSV file", type=["xlsx", "xls", "csv"],
                              help="Use the template: a Posts sheet, plus optional Community and UGC sheets.")
    template = HERE / "influencer-data-template.xlsx"
    if template.exists():
        st.download_button("Download the Excel template", template.read_bytes(),
                           file_name=template.name,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    anonymise = st.checkbox("Anonymise creator names", value=True,
                            help="Replaces names with creator_001, creator_002 and so on in tables.")

using_sample = upload is None
try:
    if using_sample:
        posts, community, ugc, warnings = load_sample()
    else:
        posts, community, ugc, warnings = load_upload(upload.name, upload.getvalue())
except L.DataError as err:
    st.error(str(err))
    st.info("Download the template from the sidebar to see the expected columns.")
    st.stop()
except Exception as err:  # unreadable or corrupted file
    st.error(f"That file couldn't be read ({type(err).__name__}). Check it is a valid .xlsx or .csv file.")
    st.stop()

# stable anonymised labels
names = sorted(posts["creator"].unique())
alias = {n: f"creator_{i + 1:03d}" for i, n in enumerate(names)}

# ------------------------------------------------------------------ sidebar: filters
with st.sidebar:
    st.header("Filters")
    dmin, dmax = posts["date"].min().date(), posts["date"].max().date()
    picked = st.date_input("Period", value=(dmin, dmax), min_value=dmin, max_value=dmax)
    start, end = (picked[0], picked[1]) if isinstance(picked, (list, tuple)) and len(picked) == 2 else (dmin, dmax)

    def multi(label, col, order=None):
        opts = sorted(posts[col].unique(), key=(lambda x: order.index(x) if order and x in order else 99))
        return st.multiselect(label, opts, default=opts)

    platforms = multi("Platform", "platform")
    tiers = multi("Creator tier", "tier", L.TIER_ORDER)
    collabs = multi("Collaboration", "collaboration")
    campaigns = multi("Campaign", "campaign")
    target = st.number_input("New contacts target", min_value=0, value=650, step=10)

flt = dict(start=start, end=end, platforms=platforms, tiers=tiers, collabs=collabs, campaigns=campaigns)
cur = L.apply_filters(posts, flt)
base = L.apply_filters(posts, flt, skip=("date",))
filtered_on = len(cur) != len(posts)

# ------------------------------------------------------------------ header
st.title("Influencer performance, UK & Ireland")
st.caption(f"Data from {dmin:%d %b %Y} to {dmax:%d %b %Y}. {len(posts):,} posts loaded.")
if using_sample:
    st.warning("**Sample data.** You are looking at generated figures for a fictional brand. "
               "Upload your own workbook in the sidebar and everything here updates.")
for w in warnings:
    st.warning(w)
if cur.empty:
    st.info("No posts match these filters. Widen the period or select more options in the sidebar.")
    st.stop()

# ------------------------------------------------------------------ KPIs
s, a = L.summarise(cur), L.summarise(posts)


def ugc_total(use_filters):
    if ugc is None:
        return None
    d = ugc[ugc["platform"].isin(platforms) | (ugc["platform"] == "All")]
    if use_filters:
        d = d[(d["month"] >= pd.Timestamp(start).to_period("M").to_timestamp()) &
              (d["month"] <= pd.Timestamp(end).to_period("M").to_timestamp())]
    return d["pieces"].sum()


kpis = [
    ("Reach", L.compact(s["reach"]), L.compact(a["reach"])),
    ("Engagement rate", L.pct(s["er"]), L.pct(a["er"])),
    ("Cost per engagement", L.gbp(s["cpe"]), L.gbp(a["cpe"])),
    ("Content pieces", L.num(s["posts"]), L.num(a["posts"])),
    ("UGC pieces tracked", "–" if ugc is None else L.num(ugc_total(True)), "–" if ugc is None else L.num(ugc_total(False))),
    ("Disclosure compliance", L.pct(s["compliance"]), L.pct(a["compliance"])),
]
for col, (label, value, overall) in zip(st.columns(6), kpis):
    with col:
        st.metric(label, value)
        st.caption(f"All data: {overall}" if filtered_on else " ")

# ------------------------------------------------------------------ trend
st.subheader("Monthly trend")
METRICS = {
    "Reach": ("reach", "bar", "~s"),
    "Engagement rate": ("er", "line", ".1%"),
    "Content pieces": ("content", "bar", ",d"),
    "Cost per engagement": ("cpe", "line", "£.2f"),
}
choice = st.radio("Metric", list(METRICS), horizontal=True, label_visibility="collapsed")
field, kind, axis_fmt = METRICS[choice]
all_months = pd.date_range(posts["month"].min(), posts["month"].max(), freq="MS")
mt = L.monthly_table(base, all_months, start, end)
x = alt.X("month:O", timeUnit="yearmonth", title=None, axis=alt.Axis(format="%b %y", labelAngle=0))
y = alt.Y(f"{field}:Q", title=None, axis=alt.Axis(format=axis_fmt), scale=alt.Scale(zero=True))
tip = [alt.Tooltip("month:T", title="Month", format="%B %Y"), alt.Tooltip(f"{field}:Q", title=choice, format=axis_fmt)]
fade = alt.condition("datum.in_range", alt.value(1), alt.value(0.3))
if kind == "bar":
    chart = alt.Chart(mt).mark_bar(color=ACCENT, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=x, y=y, opacity=fade, tooltip=tip)
else:
    line = alt.Chart(mt).encode(x=x, y=y)
    chart = (line.mark_line(color=ACCENT, opacity=0.3) +
             line.transform_filter("datum.in_range").mark_line(color=ACCENT) +
             line.mark_point(color=ACCENT, filled=True, size=70).encode(opacity=fade, tooltip=tip))
stretch(st.altair_chart, chart.properties(height=300))
st.caption("Months outside the selected period are faded." if (start, end) != (dmin, dmax) else "All months shown.")

# ------------------------------------------------------------------ insights
st.subheader("What the data says")
for line in L.insights(posts, flt):
    st.markdown(f"- {line}")

# ------------------------------------------------------------------ tier + platform
c1, c2 = st.columns([1.4, 1])
with c1:
    st.subheader("Creator tier performance")
    t = L.group_table(L.apply_filters(posts, flt, skip=("tier",)), "tier", L.TIER_ORDER)
    t["er_pct"] = t["er"] * 100
    stretch(st.dataframe, pd.DataFrame({
        "Tier": t["tier"], "Creators": t["creators"], "Posts": t["posts"],
        "Avg reach": t["avg_reach"].round(0), "Engagement rate (%)": t["er_pct"],
        "Cost per engagement (£)": t["cpe"], "Share of spend (%)": t["spend_share"] * 100,
    }), hide_index=True, column_config={
        "Avg reach": st.column_config.NumberColumn(format="%d"),
        "Engagement rate (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(max(t["er_pct"].max(), 1))),
        "Cost per engagement (£)": st.column_config.NumberColumn(format="£%.2f"),
        "Share of spend (%)": st.column_config.NumberColumn(format="%.0f%%"),
    })
with c2:
    st.subheader("Platform split")
    p = L.group_table(L.apply_filters(posts, flt, skip=("platform",)), "platform")
    stretch(st.dataframe, pd.DataFrame({
        "Platform": p["platform"], "Share of reach (%)": p["reach_share"] * 100,
        "Engagement rate (%)": p["er"] * 100, "Cost per engagement (£)": p["cpe"],
    }), hide_index=True, column_config={
        "Share of reach (%)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Engagement rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
        "Cost per engagement (£)": st.column_config.NumberColumn(format="£%.2f"),
    })

tier_chart = alt.Chart(t).mark_bar(cornerRadiusEnd=3).encode(
    y=alt.Y("tier:N", sort=L.TIER_ORDER, title=None),
    x=alt.X("cpe:Q", title="Cost per engagement (£)", axis=alt.Axis(format="£.2f")),
    color=alt.Color("tier:N", scale=alt.Scale(domain=list(TIER_COLOURS), range=list(TIER_COLOURS.values())), legend=None),
    tooltip=[alt.Tooltip("tier:N", title="Tier"), alt.Tooltip("cpe:Q", title="Cost per engagement", format="£.2f"),
             alt.Tooltip("er:Q", title="Engagement rate", format=".1%")])
stretch(st.altair_chart, tier_chart.properties(height=170))

# ------------------------------------------------------------------ campaigns
st.subheader("Campaign performance")
cp = L.group_table(cur, "campaign")
cp = cp.sort_values("posts", ascending=False)
stretch(st.dataframe, pd.DataFrame({
    "Campaign": cp["campaign"], "Posts": cp["posts"], "Reach": cp["reach"],
    "Engagement rate (%)": cp["er"] * 100, "Spend (£)": cp["cost"], "Cost per engagement (£)": cp["cpe"],
}), hide_index=True, column_config={
    "Reach": st.column_config.NumberColumn(format="%d"),
    "Engagement rate (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(max(cp["er"].max() * 100, 1))),
    "Spend (£)": st.column_config.NumberColumn(format="£%d"),
    "Cost per engagement (£)": st.column_config.NumberColumn(format="£%.2f"),
})

# ------------------------------------------------------------------ top creators + growth
c3, c4 = st.columns([1, 1])
with c3:
    st.subheader("Top creators by engagement")
    top = cur.groupby("creator").agg(Posts=("reach", "size"), Engagements=("engagements", "sum"),
                                     reach=("reach", "sum"), Tier=("tier", "first"),
                                     Platform=("platform", "first")).reset_index()
    top["Engagement rate (%)"] = np.where(top["reach"] > 0, top["Engagements"] / top["reach"] * 100, np.nan)
    top = top.sort_values("Engagements", ascending=False).head(10)
    top["Creator"] = top["creator"].map(alias) if anonymise else top["creator"]
    stretch(st.dataframe, top[["Creator", "Tier", "Platform", "Posts", "Engagements", "Engagement rate (%)"]],
            hide_index=True, column_config={
                "Engagements": st.column_config.NumberColumn(format="%d"),
                "Engagement rate (%)": st.column_config.NumberColumn(format="%.1f%%")})
with c4:
    st.subheader("Creator community growth")
    if community is None:
        st.info("Add a Community sheet (Month, New Contacts) to the workbook to see progress against your target.")
    else:
        cm = community.sort_values("month").copy()
        cm["cumulative"] = cm["new_contacts"].cumsum()
        bars = alt.Chart(cm).mark_bar(color="#D9D2F8").encode(
            x=alt.X("month:O", timeUnit="yearmonth", title=None, axis=alt.Axis(format="%b", labelAngle=0)),
            y=alt.Y("new_contacts:Q", title=None), tooltip=[alt.Tooltip("month:T", format="%B %Y"), "new_contacts:Q"])
        line = alt.Chart(cm).mark_line(color=ACCENT, point=True).encode(
            x=alt.X("month:O", timeUnit="yearmonth"), y=alt.Y("cumulative:Q", title=None),
            tooltip=[alt.Tooltip("month:T", format="%B %Y"), alt.Tooltip("cumulative:Q", title="Cumulative")])
        rule = alt.Chart(pd.DataFrame({"t": [target]})).mark_rule(color="#E0407F", strokeDash=[5, 4]).encode(y="t:Q")
        stretch(st.altair_chart, (bars + line + rule).properties(height=260))
        total = cm["cumulative"].iloc[-1]
        st.caption(f"{L.num(total)} new contacts so far, {total / target:.0%} of the {target:,} target." if target else
                   f"{L.num(total)} new contacts so far.")

# ------------------------------------------------------------------ definitions + export
with st.expander("How the metrics are calculated"):
    st.markdown("""
- **Engagement rate:** likes, comments, shares and saves divided by reach.
- **Cost per engagement:** creator fee plus product gifting value, divided by engagements.
- **Creator tiers:** Nano under 10k followers, Micro 10k to 50k, Mid 50k to 250k, Macro over 250k.
- **Disclosure compliance:** share of posts marked as correctly disclosed (ASA and CMA guidance). Posts with no value in that column are ignored.
- **Gifted and paid:** gifted means product only. Paid means a fee was paid, usually alongside product.
""")
export = cur.drop(columns=["month"]).copy()
if anonymise:
    export["creator"] = export["creator"].map(alias)
st.download_button("Download filtered data (CSV)", export.to_csv(index=False).encode("utf-8"),
                   file_name="filtered-influencer-data.csv", mime="text/csv")
