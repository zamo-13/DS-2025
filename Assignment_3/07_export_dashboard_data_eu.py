"""Builds the 5 dashboard CSVs from the raw dsa-data backup, not the already-filtered files.

Territorial scope is EU-27, matched with a substring search on
territorial_scope: TikTok reports most decisions as one pan-EU/EEA bloc string
per row, X reports one country per row, so there's no shared column format to
filter on directly. Note that TikTok's bloc string also includes Norway and
Liechtenstein and there's no way to separate those out, so "EU-wide" for
TikTok is really EEA-wide in practice - see the caption in app.py for why that
matters. Date range is 2025-01-01 to 2025-06-30. No boundary-bleed category
drop and no category truncation this time - every STATEMENT_CATEGORY_* value
that shows up in the data gets kept.

Usage:
    python 07_export_dashboard_data_eu.py [--data-dir E:\\dsa-data] [--out-dir ...]
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import polars as pl

DEFAULT_DATA_ROOT = Path(r"E:\dsa-data")
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / ".." / "dashboard_data"

_PARQUET_GLOBS: dict[str, str] = {
    "TikTok": "tiktok___full/daily_dumps_chunked/*/*.parquet",
    "X": "x___full/daily_dumps_chunked/*/*.parquet",
}

# Same 27 codes as X's own DSA transparency report breakdown - EU members
# only, not EEA (so no Norway/Liechtenstein, unlike TikTok's bloc string).
_EU_27 = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
]
# quoted because territorial_scope stores codes as a serialized list, e.g.
# ["DE","FR"] - matching the quotes too avoids loose substring hits
_EU_27_PATTERN = "|".join(f'"{code}"' for code in _EU_27)

_H1_START = "2025-01-01"
_H1_END_EXCLUSIVE = "2025-07-01"

_FULLY_AUTOMATED = "AUTOMATED_DECISION_FULLY"

# 2 EU-wide events + 2 global events, all H1 2025, none overlapping the
# 23 Feb German election window. Baseline = 7 days before the event date,
# event window = event date + the following 6 days, so both are the same length.
EVENTS: list[dict[str, str]] = [
    {"name": "EU defense summit (ReArm Europe)", "date": "2025-03-06", "type": "EU"},
    {"name": "EU retaliatory tariffs vote", "date": "2025-04-09", "type": "EU"},
    {"name": "Trump second inauguration", "date": "2025-01-20", "type": "Global"},
    {"name": "Pope Francis's death", "date": "2025-04-21", "type": "Global"},
]


def _scan(data_root: Path, cols: list[str]) -> pl.LazyFrame:
    frames: list[pl.LazyFrame] = []
    for platform, glob in _PARQUET_GLOBS.items():
        path = data_root / glob
        load_cols = list(dict.fromkeys(cols + ["territorial_scope", "application_date", "platform_name"]))
        lf = pl.scan_parquet(str(path)).select(load_cols)
        lf = lf.filter(pl.col("territorial_scope").str.contains(_EU_27_PATTERN))
        lf = lf.filter(
            (pl.col("application_date") >= pl.lit(_H1_START).str.to_datetime(time_unit="ms"))
            & (pl.col("application_date") < pl.lit(_H1_END_EXCLUSIVE).str.to_datetime(time_unit="ms"))
        )
        # raw data labels X as "X (formerly Twitter)" - normalize so it doesn't
        # end up as its own group next to "X" everywhere downstream
        lf = lf.with_columns(
            pl.when(pl.col("platform_name") == "X (formerly Twitter)")
            .then(pl.lit("X"))
            .otherwise(pl.col("platform_name"))
            .alias("platform_name")
        )
        frames.append(lf.select(cols + ["platform_name"] if "platform_name" not in cols else cols))
    return pl.concat(frames)


def category_distribution(data_root: Path) -> pl.DataFrame:
    lf = _scan(data_root, ["platform_name", "category"])
    return (
        lf.group_by(["platform_name", "category"])
        .agg(pl.len().alias("count"))
        .collect(engine="streaming")
        .with_columns((pl.col("count") / pl.col("count").sum().over("platform_name") * 100).alias("pct"))
        .sort(["platform_name", "count"], descending=[False, True])
    )


def automation_rate(data_root: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    lf = _scan(data_root, ["platform_name", "category", "automated_decision"])
    grouped = lf.group_by(["platform_name", "automated_decision"]).agg(pl.len().alias("count")).collect(engine="streaming")
    overall = (
        grouped.with_columns((pl.col("count") / pl.col("count").sum().over("platform_name") * 100).alias("pct"))
        .filter(pl.col("automated_decision") == _FULLY_AUTOMATED)
        .select(["platform_name", "pct"])
        .rename({"pct": "fully_automated_pct"})
        .sort("platform_name")
    )
    by_cat = (
        lf.group_by(["platform_name", "category", "automated_decision"])
        .agg(pl.len().alias("count"))
        .collect(engine="streaming")
        .with_columns((pl.col("count") / pl.col("count").sum().over(["platform_name", "category"]) * 100).alias("pct"))
        .filter(pl.col("automated_decision") == _FULLY_AUTOMATED)
        .select(["platform_name", "category", "pct"])
        .rename({"pct": "fully_automated_pct"})
        .sort(["platform_name", "fully_automated_pct"], descending=[False, True])
    )
    return overall, by_cat


def amar_daily_intensity(data_root: Path, amar_eu: dict[str, dict[str, int]]) -> pl.DataFrame:
    lf = _scan(data_root, ["platform_name", "application_date"])
    daily = (
        lf.with_columns(
            pl.col("application_date").dt.strftime("%Y-%m-%d").alias("date"),
            pl.col("application_date").dt.strftime("%Y-%m").alias("month"),
        )
        .group_by(["platform_name", "date", "month"])
        .agg(pl.len().alias("raw_count"))
        .collect(engine="streaming")
    )
    amar_df = pl.DataFrame([
        {"platform_name": p, "month": m, "amar": v}
        for p, months in amar_eu.items() for m, v in months.items()
    ])
    return (
        daily.join(amar_df, on=["platform_name", "month"], how="inner")
        .with_columns((pl.col("raw_count") / pl.col("amar") * 1_000_000).round(2).alias("intensity_rate"))
        .drop("month")
        .sort(["platform_name", "date"])
    )


def event_deviation(daily_intensity: pl.DataFrame) -> pl.DataFrame:
    df = daily_intensity.with_columns(pl.col("date").str.to_date().alias("date"))
    rows = []
    for event in EVENTS:
        event_date = date.fromisoformat(event["date"])
        baseline_start = event_date - timedelta(days=7)
        baseline_end = event_date - timedelta(days=1)
        window_end = event_date + timedelta(days=6)

        baseline = (
            df.filter((pl.col("date") >= baseline_start) & (pl.col("date") <= baseline_end))
            .group_by("platform_name").agg(pl.col("intensity_rate").mean().alias("baseline_rate"))
        )
        window = (
            df.filter((pl.col("date") >= event_date) & (pl.col("date") <= window_end))
            .group_by("platform_name").agg(pl.col("intensity_rate").mean().alias("event_rate"))
        )
        merged = (
            baseline.join(window, on="platform_name")
            .with_columns(
                pl.lit(event["name"]).alias("event"),
                pl.lit(event["type"]).alias("event_type"),
                pl.lit(event["date"]).alias("event_date"),
                ((pl.col("event_rate") - pl.col("baseline_rate")) / pl.col("baseline_rate") * 100)
                .round(2).alias("pct_deviation"),
            )
        )
        rows.append(merged)
    return pl.concat(rows).select(
        ["event", "event_type", "event_date", "platform_name", "baseline_rate", "event_rate", "pct_deviation"]
    ).sort(["event_type", "event", "platform_name"])


def main(data_root: Path, out_dir: Path, amar_eu: dict[str, dict[str, int]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    cat_dist = category_distribution(data_root)
    cat_dist.write_csv(out_dir / "category_distribution.csv")
    print(f"wrote category_distribution.csv ({cat_dist.height} rows)")

    auto_overall, auto_by_cat = automation_rate(data_root)
    auto_overall.write_csv(out_dir / "automation_rate_overall.csv")
    auto_by_cat.write_csv(out_dir / "automation_rate_by_category.csv")
    print(f"wrote automation_rate_overall.csv ({auto_overall.height} rows), "
          f"automation_rate_by_category.csv ({auto_by_cat.height} rows)")

    daily = amar_daily_intensity(data_root, amar_eu)
    daily.write_csv(out_dir / "amar_daily_intensity.csv")
    print(f"wrote amar_daily_intensity.csv ({daily.height} rows)")

    event_dev = event_deviation(daily)
    event_dev.write_csv(out_dir / "event_deviation.csv")
    print(f"wrote event_deviation.csv ({event_dev.height} rows)")

    print(f"\nEU-wide dashboard CSVs written to: {out_dir.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export EU-wide dashboard CSVs from the raw E:\\dsa-data backup.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    # TikTok reports one flat 6-month AMAR figure, same as the DE constant.
    # X's two quarterly figures are summed straight from the per-country
    # breakdown tables in X's own DSA transparency reports (the same reports
    # that already gave the DE Q1/Q2 numbers) - see app.py's About tab for
    # the report dates.
    amar_eu = {
        "TikTok": {m: 169_000_000 for m in
                   ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"]},
        "X": {
            "2025-01": 94_830_300, "2025-02": 94_830_300, "2025-03": 94_830_300,
            "2025-04": 102_004_250, "2025-05": 102_004_250, "2025-06": 102_004_250,
        },
    }
    main(args.data_dir, args.out_dir, amar_eu)
