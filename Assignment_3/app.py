"""
DSA Content Moderation Dashboard — TikTok vs. X (Germany, H1 2025)
Assignment 3 — Data Visualization course

Reads 7 pre-aggregated CSVs (see 06_export_dashboard_data.py in the thesis
repo) from DATA_DIR. Does no raw-data processing itself — every number
here was computed once, upstream, from the v1/DE-scope parquet files.

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
BG = "rgba(0,0,0,0)"
ELECTION_DATE = pd.Timestamp("2025-02-23")
RESAMPLE_FREQ = {"Daily": None, "Weekly": "7D"}  # Monthly reads amar_monthly_intensity.csv directly

st.set_page_config(page_title="DSA Moderation Dashboard — TikTok vs. X", layout="wide")

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
    """Cosmetic-only relabeling of raw DSA category codes for readability.
    Not the abandoned v1/v2 harmonization — purely a display convenience."""
    if not isinstance(cat, str):
        return str(cat)
    label = cat.replace("STATEMENT_CATEGORY_", "").replace("_", " ").title()
    return label


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
cat_dist = load_csv("category_distribution.csv")
auto_overall = load_csv("automation_rate_overall.csv")
auto_by_cat = load_csv("automation_rate_by_category.csv")
gran_dist = load_csv("granularity_distribution.csv")
gran_other = load_csv("granularity_other_share.csv")
amar_daily = load_csv("amar_daily_intensity.csv")
amar_monthly = load_csv("amar_monthly_intensity.csv")
feb_dev = load_csv("february_deviation.csv")

missing = [
    n for n, df in [
        ("category_distribution.csv", cat_dist),
        ("automation_rate_overall.csv", auto_overall),
        ("automation_rate_by_category.csv", auto_by_cat),
        ("granularity_distribution.csv", gran_dist),
        ("granularity_other_share.csv", gran_other),
        ("amar_daily_intensity.csv", amar_daily),
        ("amar_monthly_intensity.csv", amar_monthly),
        ("february_deviation.csv", feb_dev),
    ] if df is None
]

st.title("Content Moderation on TikTok and X")
st.caption(
    "Moderation decisions affecting the German information environment, January–June 2025. "
    "Dataset originates from ongoing bachelor's thesis data collection (DSA Transparency Database)."
)

if missing:
    st.warning(
        f"Missing data files in `{DATA_DIR}/`: {', '.join(missing)}. "
        "Run `06_export_dashboard_data.py` first."
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
tab1, tab2, tab3, tab4 = st.tabs(
    ["Overview", "Platform Comparison", "Reporting Granularity", "Election Window"]
)

# --- Tab 1: Overview -------------------------------------------------------
with tab1:
    st.subheader("Automation reliance: the headline contrast")

    overall_f = auto_overall[auto_overall["platform_name"].isin(platforms)]
    cols = st.columns(len(overall_f) + 1)
    for i, row in enumerate(overall_f.itertuples()):
        cols[i].metric(
            f"{row.platform_name} — fully automated",
            f"{row.fully_automated_pct:.1f}%",
        )
    total_rows_note = (
        "Automation share of decisions with no human review at any stage, "
        "v1 period (Jan–Jun 2025), decisions whose territorial scope includes Germany."
    )
    cols[-1].caption(total_rows_note)

    fig = px.bar(
        overall_f, x="platform_name", y="fully_automated_pct",
        color="platform_name", color_discrete_map=COLORS,
        text=overall_f["fully_automated_pct"].round(1).astype(str) + "%",
        labels={"fully_automated_pct": "% fully automated", "platform_name": ""},
    )
    fig.update_traces(textposition="outside", showlegend=False)
    fig = clean_axes(fig)
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "TikTok resolves nearly all German-scoped moderation decisions without human review; "
        "X does close to none. This gap is the central finding driving the rest of this dashboard."
    )

# --- Tab 2: Platform Comparison --------------------------------------------
with tab2:
    st.subheader("The two platforms moderate different kinds of content")

    cat_f = cat_dist[cat_dist["platform_name"].isin(platforms)].copy()
    cat_f["category_label"] = cat_f["category"].map(shorten_category)

    top_n = st.slider("Show top N categories per platform (rest grouped as 'Other')", 5, 15, 8)

    frames = []
    for p, grp in cat_f.groupby("platform_name"):
        grp = grp.sort_values("pct", ascending=False)
        top = grp.head(top_n).copy()
        rest_pct = grp["pct"].iloc[top_n:].sum()
        if rest_pct > 0:
            top = pd.concat([top, pd.DataFrame(
                [{"platform_name": p, "category_label": "Other (grouped)", "pct": rest_pct}]
            )], ignore_index=True)
        frames.append(top)
    cat_top = pd.concat(frames, ignore_index=True)

    shared_max = cat_top["pct"].max() * 1.1

    cols = st.columns(len(platforms))
    for i, p in enumerate(platforms):
        sub = cat_top[cat_top["platform_name"] == p].sort_values("pct")
        fig = px.bar(
            sub, x="pct", y="category_label", orientation="h",
            color_discrete_sequence=[COLORS.get(p, "#888")],
            labels={"pct": "% of decisions", "category_label": ""},
            title=p,
        )
        fig.update_xaxes(range=[0, shared_max])  # shared scale = true small multiples
        fig = clean_axes(fig)
        cols[i].plotly_chart(fig, width="stretch")

    st.caption(
        "Bars use position/length encoding (not pie charts) for accurate comparison. "
        "Both panels share the same x-axis scale so proportions are directly comparable."
    )

# --- Tab 3: Reporting Granularity -------------------------------------------
with tab3:
    st.subheader("X never reports a specific outcome; TikTok usually does")

    other_f = gran_other[gran_other["platform_name"].isin(platforms)]
    cols = st.columns(len(other_f))
    for i, row in enumerate(other_f.itertuples()):
        cols[i].metric(
            f"{row.platform_name} — reports as 'Other'",
            f"{row.other_visibility_pct:.1f}%",
            help="Share of decisions with no specific visibility outcome on record.",
        )

    gran_f = gran_dist[gran_dist["platform_name"].isin(platforms)].copy()
    gran_f["visibility_label"] = (
        gran_f["decision_visibility"].fillna("(missing)")
        .str.replace(r'[\[\]"]', "", regex=True)
        .str.replace("DECISION_VISIBILITY_", "", regex=False)
        .str.replace("_", " ").str.title()
    )
    gran_f = gran_f[gran_f["pct"] >= 0.3]  # drop noise slivers under 0.3%

    fig = px.bar(
        gran_f, x="pct", y="platform_name", color="visibility_label",
        orientation="h",
        labels={"pct": "% of decisions", "platform_name": ""},
    )
    fig = clean_axes(fig)
    st.plotly_chart(fig, width="stretch")

    st.caption(
        "X records a specific outcome for essentially none of its decisions whose territorial scope "
        "includes Germany; TikTok specifies an outcome (e.g. content removed, age-restricted) most of "
        "the time. Reporting granularity differs sharply between platforms even where automation "
        "reliance is held aside."
    )

# --- Tab 4: Election Window --------------------------------------------------
with tab4:
    st.subheader("TikTok's moderation intensity surged into the election; X's didn't")

    granularity = st.radio(
        "View by", ["Daily", "Weekly", "Monthly"], index=1, horizontal=True,
        help="Daily is the rawest signal but noisiest, especially for X's smaller volumes. "
             "Weekly and Monthly smooth that noise out at the cost of hiding single-day shifts.",
    )
    st.caption(
        "MAR = officially reported Monthly Active Recipients, the normalisation base for both "
        "charts below. TikTok: 25,700,000 (constant, Jan–Jun 2025). X: 15,598,407 (Jan–Mar 2025), "
        "14,929,142 (Apr–Jun 2025) — note X's own reported figure changed partway through the period."
    )

    if granularity == "Monthly":
        # Use the official pre-aggregated monthly file directly instead of
        # resampling the daily file — it's built from the exact same raw
        # counts, but reading it straight avoids relying on resampling
        # approximating an already-official aggregate.
        period_f = amar_monthly[amar_monthly["platform_name"].isin(platforms)].copy()
        period_f["period"] = pd.to_datetime(period_f["month"], format="%Y-%m")
        period_f = period_f[["platform_name", "period", "intensity_rate"]]
    else:
        daily_f = amar_daily[amar_daily["platform_name"].isin(platforms)].copy()
        daily_f["date"] = pd.to_datetime(daily_f["date"])

        freq = RESAMPLE_FREQ[granularity]
        if freq is None:
            period_f = daily_f.rename(columns={"date": "period"})[["platform_name", "period", "intensity_rate"]]
        else:
            # intensity_rate is already normalised per day, so summing it
            # across a period (rather than re-deriving from raw counts)
            # gives the correct period rate as long as AMAR is constant
            # within that period — true for every week here except the one
            # straddling the X AMAR revision at end of March, a negligible
            # edge case. "7D" (not the anchored "W") + label="left" keeps bin
            # edges inside the actual data range (Jan 1 - Jun 30): a
            # calendar-week frequency would anchor to fixed weekday
            # boundaries and label a partial trailing/leading bin outside
            # the real data (e.g. into July).
            period_f = (
                daily_f.set_index("date")
                .groupby("platform_name")["intensity_rate"]
                .resample(freq, label="left").sum()
                .reset_index()
                .rename(columns={"date": "period"})
            )

    period_f = period_f.sort_values(["platform_name", "period"])

    # TikTok's and X's raw intensity differ by ~1000x, so a shared linear
    # axis flattens X to an invisible line (see the raw small multiples
    # below). Indexing both to their first period's value makes the
    # relative shift around the election comparable at a glance instead.
    baseline = period_f.groupby("platform_name")["intensity_rate"].first()
    period_f["indexed"] = period_f["intensity_rate"] / period_f["platform_name"].map(baseline) * 100

    fig = px.line(
        period_f, x="period", y="indexed", color="platform_name",
        color_discrete_map=COLORS, markers=(granularity != "Daily"),
        labels={"indexed": f"Moderation intensity (first {granularity.lower()} period = 100)", "period": ""},
    )
    fig.add_hline(y=100, line_dash="dash", line_color="#BBBBBB")
    fig.add_vline(x=ELECTION_DATE, line_dash="dot", line_color="#B33A3A")
    fig.add_annotation(x=ELECTION_DATE, y=1.02, yref="paper", showarrow=False,
                        text="German snap election (23 Feb)", font=dict(size=11, color="#B33A3A"))
    fig = clean_axes(fig)
    st.plotly_chart(fig, width="stretch")

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
        fig_raw.add_vline(x=ELECTION_DATE, line_dash="dot", line_color="#B33A3A")
        fig_raw = clean_axes(fig_raw)
        raw_cols[i].plotly_chart(fig_raw, width="stretch")
    st.caption(
        "Each platform on its own y-axis, so its actual shape is visible — on the indexed chart "
        "above, X's real trend is still readable because both platforms share one relative scale; "
        "on a shared *absolute* scale, TikTok's ~1,000x higher intensity would flatten X into a "
        "near-invisible line, which is why the two platforms get separate axes here instead."
    )

    st.markdown("**February vs. January baseline**")
    dev_f = feb_dev[feb_dev["platform_name"].isin(platforms)].copy()

    def _format_dev_row(row: pd.Series) -> pd.Series:
        if row["metric"] == "automation_rate":
            # 3 decimals (not 2): X's automation rate is ~0.003%, which
            # would otherwise display as "0.00%" for both Jan and Feb —
            # looking like no change despite the real +9% shift shown in
            # the % change column.
            jan, feb = f"{row['jan_rate']:.3f}%", f"{row['feb_rate']:.3f}%"
        else:
            jan, feb = f"{row['jan_rate']:,.2f}", f"{row['feb_rate']:,.2f}"
        return pd.Series({"January": jan, "February": feb, "% change": f"{row['pct_deviation']:+.1f}%"})

    dev_display = dev_f.apply(_format_dev_row, axis=1)
    dev_display.insert(0, "Platform", dev_f["platform_name"].values)
    dev_display.insert(0, "Metric", dev_f["metric"].values)
    st.dataframe(dev_display, width="stretch", hide_index=True)

    st.caption(
        "Moderation intensity is normalised by each platform's officially reported monthly active "
        "recipients (AMAR). The indexed scale compares each platform to its own first-period value "
        "(=100), so the shape of the change is comparable despite TikTok's raw intensity being roughly "
        "1,000x higher than X's — that gap is exactly why indexed is the default view; switch to "
        "\"Raw intensity rate\" above to see X's line flatten out and verify this yourself. The table "
        "below shows the underlying raw monthly rates."
    )
