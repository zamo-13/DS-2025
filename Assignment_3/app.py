"""
DSA Content Moderation Dashboard — TikTok vs. X (EU-wide, H1 2025)
Assignment 3

Reads pre-aggregated CSVs (see 07_export_dashboard_data_eu.py) from DATA_DIR.


This dashboard asks whether TikTok and X react differently to EU-wide events
versus globally-relevant ones, using EU-27-scoped data. 

Run:
    streamlit run app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.environ.get("DASHBOARD_DATA_DIR", Path(__file__).parent / "dashboard_data"))

COLORS = {"TikTok": "#0B7C8C", "X": "#4A4A4A"}  # fixed, used identically everywhere
EVENT_TYPE_COLORS = {"EU": "#8E5FD1", "Global": "#B33A3A"}
BG = "rgba(0,0,0,0)"
RESAMPLE_FREQ = {"Daily": None, "Weekly": "7D", "Monthly": "MS"}

# Same 4 events used to build event_deviation.csv - kept here too so the
# chart's vlines/annotations line up with the table without re-deriving them.
EVENTS = [
    {"name": "Trump 2nd inauguration", "date": "2025-01-20", "type": "Global"},
    {"name": "EU defense summit (ReArm Europe)", "date": "2025-03-06", "type": "EU"},
    {"name": "EU retaliatory tariffs vote", "date": "2025-04-09", "type": "EU"},
    {"name": "Pope Francis's death", "date": "2025-04-21", "type": "Global"},
]

st.set_page_config(page_title="DSA Moderation Dashboard, TikTok vs. X (EU)", layout="wide")

CHART_LAYOUT = dict(
    plot_bgcolor=BG,
    paper_bgcolor=BG,
    font=dict(size=13),
    margin=dict(l=10, r=10, t=40, b=10),
)


def clean_axes(fig: go.Figure) -> go.Figure:
    """Apply data-ink-ratio-minded defaults: no gridlines, thin axis lines only."""
    fig.update_layout(**CHART_LAYOUT)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


@st.cache_data
def load_csv(name: str) -> pd.DataFrame | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    return pd.read_csv(path)


def shorten_category(cat: str) -> str:
    """Cosmetic-only relabeling of raw DSA category codes for readability."""
    if not isinstance(cat, str):
        return str(cat)
    return cat.replace("STATEMENT_CATEGORY_", "").replace("_", " ").title()


def add_event_markers(fig: go.Figure, y_annotation: float = 1.02) -> go.Figure:
    """Mark all 4 events on a time-series chart, colour-coded EU vs. Global."""
    for event in EVENTS:
        color = EVENT_TYPE_COLORS[event["type"]]
        fig.add_vline(x=pd.Timestamp(event["date"]), line_dash="dot", line_color=color)
        fig.add_annotation(
            x=pd.Timestamp(event["date"]), y=y_annotation, yref="paper", showarrow=False,
            text=event["name"], font=dict(size=9, color=color), textangle=-90, xanchor="right",
        )
    return fig


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
cat_dist = load_csv("category_distribution.csv")
auto_overall = load_csv("automation_rate_overall.csv")
auto_by_cat = load_csv("automation_rate_by_category.csv")
amar_daily = load_csv("amar_daily_intensity.csv")
event_dev = load_csv("event_deviation.csv")

missing = [
    n for n, df in [
        ("category_distribution.csv", cat_dist),
        ("automation_rate_overall.csv", auto_overall),
        ("automation_rate_by_category.csv", auto_by_cat),
        ("amar_daily_intensity.csv", amar_daily),
        ("event_deviation.csv", event_dev),
    ] if df is None
]

st.title(" TikTok & X EU-wide Content Moderation")
st.caption(
    "Moderation decisions affecting the EU information environment, January–June 2025. "
    "Dataset originates from the DSA Transparency Database, scoped to the 27 EU member states."
)

if missing:
    st.warning(
        f"Missing data files in `{DATA_DIR}/`: {', '.join(missing)}. "
        "Run `07_export_dashboard_data_eu.py` first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar — shared filter
# ---------------------------------------------------------------------------
all_platforms = sorted(set(cat_dist["platform_name"]).union(auto_overall["platform_name"]))
st.sidebar.header("Filters")
platforms = st.sidebar.multiselect("Platform", all_platforms, default=all_platforms)

if not platforms:
    st.info("Select at least one platform in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["About", "Overview", "Event Reactions"])

# --- Tab 1: About ------------------------------------------------------------
with tab1:
    st.markdown(
        "This Dashboard shows a comparison of how TikTok and X moderated content across the EU in "
        "the first half of 2025 including how much of it was automated, and whether the two "
        "platforms react differently to EU-wide political events versus globally-relevant ones."
    )
    st.markdown("**Overview**: Shows the automation contrast in decisions made for the moderation, plus what kind of content each platform "
                "moderates most, side by side on a shared scale.")
    st.markdown("**Event Reactions**: Shows whether moderation intensity shifts around 2 "
                "EU-wide events (an EU defense summit, an EU tariffs vote) and 2 "
                "globally-relevant events (a US presidential inauguration, a Pope's "
                "death), viewable as Daily, Weekly, or Monthly, with all 4 events marked "
                "and a deviation-from-baseline table/chart below.")
    st.markdown("Use the **Platform** filter in the sidebar to show just TikTok, just X, "
                "or both, on any tab.")

    st.divider()
    st.subheader("Data & methodology")
    st.markdown(
        "The app itself does no data processing. It just reads the 5 CSVs in "
        "`dashboard_data/`. Those come from `07_export_dashboard_data_eu.py`, included in "
        "this folder, which did the actual aggregation on raw data."
    )
    st.markdown(
        "**Data Source:** DSA Transparency Database (transparency.dsa.ec.europa.eu), TikTok and X, raw statement-of-reasons "
        "dumps for the full 2025 calendar year. The "
        "Transparency Database itself is public (https://code.europa.eu/dsa/transparency-database/dsa-tdb). the raw "
        "dumps used here are a bulk export of it, not included in this submission "
        "because of size, but the same underlying data is publicly re-obtainable through "
        "that site."
    )
    st.markdown(
        "**What the script (07_export_dashboard_data_eu.py) does?:** It filters to the 27 EU member states (matched on the "
        "`territorial_scope` field. TikTok reports most decisions as one pan-EU/EEA bloc "
        "string covering all 27 EU states plus Norway and Liechtenstein, X reports one "
        "country per row) and to 1 Jan – 30 Jun 2025. Everything else is a straight "
        "group-by-and-count category distribution and automation rate, overall and per "
        "category. No categories are dropped. Every category "
        "present in the raw data shows up in the CSVs and in the Overview tab's charts."
    )

    st.markdown(
        "**Normalisation made in the tab 'Event Reaction':** Moderation counts are divided by each platform's average "
        "monthly active recipients (a DSA-mandated disclosure) to get a per-user rate, "
        "otherwise TikTok's much larger user base makes any raw comparison meaningless. "
        "TikTok's figure, 169,000,000, is one flat number for the whole H1 2025 period, "
        "matching how TikTok itself reports it in 6-month blocks. X reports quarterly: "
        "94,830,300 for Jan–Mar (from X's DSA Transparency Report covering 1 Oct 2024 – "
        "31 Mar 2025) and 102,004,250 for Apr–Jun (from X's report covering 1 Apr – 30 Jun "
        "2025) both summed directly from the per-member-state breakdown table in those "
        "reports, not estimated."
    )
    st.markdown(
        "**The 4 events (Event Reactions tab):** Two EU-wide: the \"ReArm Europe\" defense "
        "summit (6 March 2025) and the EU's retaliatory tariff vote against the US "
        "(9 April 2025) both decided at the EU level, not by one member state. Two "
        "global: Trump's second inauguration (20 January 2025) and Pope Francis's death "
        "(21 April 2025). For each, the baseline is the mean daily intensity over the 7 "
        "days before the event, and the \"event window\" is the event date plus the "
        "following 6 days, so the two are directly comparable as a "
        "percentage change."
    )

# --- Tab 2: Overview ---------------------------------------------------------
with tab2:
    st.subheader("Automation reliance: the headline contrast")

    overall_f = auto_overall[auto_overall["platform_name"].isin(platforms)]
    cols = st.columns(len(overall_f) + 1)
    for i, row in enumerate(overall_f.itertuples()):
        cols[i].metric(
            f"{row.platform_name}  is fully automated",
            f"{row.fully_automated_pct:.1f}%",
        )
    cols[-1].caption(
        "Automation share of decisions with no human review at any stage, "
        "H1 2025 (Jan–Jun), decisions whose territorial scope includes an EU member state."
    )

    fig = px.bar(
        overall_f, x="platform_name", y="fully_automated_pct",
        color="platform_name", color_discrete_map=COLORS,
        text=overall_f["fully_automated_pct"].round(1).astype(str) + "%",
        labels={"fully_automated_pct": "% fully automated", "platform_name": ""},
    )
    fig.update_traces(textposition="outside", showlegend=False)
    fig = clean_axes(fig)
    st.plotly_chart(fig, width="stretch")

    st.divider()
    st.subheader("The two platforms moderate different kinds of content")

    cat_f = cat_dist[cat_dist["platform_name"].isin(platforms)].copy()
    cat_f["category_label"] = cat_f["category"].map(shorten_category)

    shared_max = cat_f["pct"].max() * 1.1
    n_categories = cat_f.groupby("platform_name").size().max()

    cols = st.columns(len(platforms))
    for i, p in enumerate(platforms):
        sub = cat_f[cat_f["platform_name"] == p].sort_values("pct")
        fig = px.bar(
            sub, x="pct", y="category_label", orientation="h",
            color_discrete_sequence=[COLORS.get(p, "#888")],
            labels={"pct": "% of decisions", "category_label": ""},
            title=p,
        )
        fig.update_xaxes(range=[0, shared_max])  # shared scale = true small multiples
        fig.update_layout(height=max(320, 24 * n_categories))
        fig = clean_axes(fig)
        cols[i].plotly_chart(fig, width="stretch")

    st.caption(
        "Every category present in the data is shown and none was left out."
    )

# --- Tab 3: Event Reactions --------------------------------------------------
with tab3:
    st.subheader("How does each platform react to global/EU events?")
    st.caption(
        "Two EU-wide events and two globally-relevant events, all in H1 2025. Four events is descriptive pattern-spotting, "
        "not a statistical test."
    )

    granularity = st.radio(
        "View by", ["Daily", "Weekly", "Monthly"], index=1, horizontal=True,
        help="Daily is the rawest signal but noisiest, especially for X's smaller volumes. "
             "Weekly and Monthly smooth that noise out at the cost of hiding single-day shifts.",
    )
    st.caption(
        "MAR = officially reported Monthly Active Recipients, the EU-wide normalisation base. "
        "TikTok: 169,000,000 (one flat H1 2025 figure, per TikTok's own 6-month reporting "
        "cadence). X: 94,830,300 (Jan–Mar 2025), 102,004,250 (Apr–Jun 2025) summed directly "
        "from X's own per-member-state DSA transparency tables."
    )

    daily_f = amar_daily[amar_daily["platform_name"].isin(platforms)].copy()
    daily_f["date"] = pd.to_datetime(daily_f["date"])

    freq = RESAMPLE_FREQ[granularity]
    if freq is None:
        period_f = daily_f.rename(columns={"date": "period"})[["platform_name", "period", "intensity_rate"]]
    else:
        period_f = (
            daily_f.set_index("date")
            .groupby("platform_name")["intensity_rate"]
            .resample(freq, label="left").sum()
            .reset_index()
            .rename(columns={"date": "period"})
        )
    period_f = period_f.sort_values(["platform_name", "period"])

    baseline = period_f.groupby("platform_name")["intensity_rate"].first()
    period_f["indexed"] = period_f["intensity_rate"] / period_f["platform_name"].map(baseline) * 100

    fig = px.line(
        period_f, x="period", y="indexed", color="platform_name",
        color_discrete_map=COLORS, markers=(granularity != "Daily"),
        labels={"indexed": f"Moderation intensity (first {granularity.lower()} period = 100)", "period": ""},
    )
    fig.add_hline(y=100, line_dash="dash", line_color="#BBBBBB")
    fig = add_event_markers(fig)
    fig = clean_axes(fig)
    fig.update_layout(margin=dict(t=70))
    st.plotly_chart(fig, width="stretch")

    with st.expander("How is this calculated?"):
        st.markdown(
            f"Each platform's daily intensity (decisions per million MAR) is divided by its "
            f"own value on the very first {granularity.lower()} period shown, then multiplied "
            f"by 100. So a value of 150 means \"50% higher than where this platform started\" "
            f"it's a relative comparison, not an absolute count. See the About tab for how the "
            f"underlying intensity number itself is built (AMAR normalisation) and how the "
            f"event baseline further down is defined."
        )

    st.markdown("**Raw intensity, per platform**")
    raw_cols = st.columns(len(platforms))
    for i, p in enumerate(platforms):
        sub = period_f[period_f["platform_name"] == p]
        fig_raw = px.line(
            sub, x="period", y="intensity_rate",
            color_discrete_sequence=[COLORS.get(p, "#888")],
            markers=(granularity != "Daily"),
            labels={"intensity_rate": "Decisions per million MAR", "period": ""},
            title=p,
        )
        fig_raw = add_event_markers(fig_raw)
        fig_raw = clean_axes(fig_raw)
        fig_raw.update_layout(margin=dict(t=70))
        raw_cols[i].plotly_chart(fig_raw, width="stretch")
    st.caption(
        "Each platform on its own y-axis, so its actual shape is visible. TikTok's raw intensity "
        "is roughly 1,000x higher than X's, which would flatten X into a near-invisible line on a "
        "shared absolute scale (the indexed chart above avoids that by comparing each platform to "
        "its own first-period value instead). Purple markers = EU-wide events, red = global events."
    )

    st.markdown("**Deviation from a 7-day pre-event baseline**")
    dev_f = event_dev[event_dev["platform_name"].isin(platforms)].copy()

    fig_dev = px.bar(
        dev_f, x="event", y="pct_deviation", color="platform_name",
        facet_col="event_type", barmode="group",
        color_discrete_map=COLORS,
        labels={"pct_deviation": "% deviation vs. baseline", "event": "", "event_type": ""},
    )
    fig_dev.update_xaxes(matches=None)
    fig_dev.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig_dev = clean_axes(fig_dev)
    st.plotly_chart(fig_dev, width="stretch")

    dev_display = dev_f.copy()
    dev_display["baseline_rate"] = dev_display["baseline_rate"].round(2).map("{:,.2f}".format)
    dev_display["event_rate"] = dev_display["event_rate"].round(2).map("{:,.2f}".format)
    dev_display["pct_deviation"] = dev_display["pct_deviation"].map("{:+.1f}%".format)
    dev_display = dev_display.rename(columns={
        "event": "Event", "event_type": "Type", "platform_name": "Platform",
        "baseline_rate": "Baseline (7d avg)", "event_rate": "Event week (7d avg)",
        "pct_deviation": "% deviation",
    })[["Event", "Type", "Platform", "Baseline (7d avg)", "Event week (7d avg)", "% deviation"]]
    st.dataframe(dev_display, width="stretch", hide_index=True)

    st.caption(
        "Baseline = mean daily intensity over the 7 days before the event; event window = the "
        "event date plus the following 6 days. TikTok's largest swing (+49.6%) follows a global "
        "event (Trump's inauguration); X's largest swing (-44.4%) follows an EU-wide event (the "
        "defense summit). On a small daily base for X, so treat that particular figure as "
        "noisier than the others. No consistent \"reacts more to EU\" or \"reacts more to global\" "
        "pattern holds across both platforms."
    )
