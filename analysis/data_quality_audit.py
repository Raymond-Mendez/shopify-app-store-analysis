"""Data quality audit for the Shopify App Store dataset.

Run before trusting anything in the Power BI report. Every issue printed here affects a
visual on the Overview or Time Intelligence page, and each one is documented in the README.

Usage:
    python analysis/data_quality_audit.py
"""

from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load():
    apps = pd.read_csv(ROOT / "data" / "apps.csv")
    reviews = pd.read_csv(ROOT / "data" / "reviews.csv")
    return apps, reviews


def date_formats(reviews):
    """posted_at arrives in two different formats, which breaks a single-format parse."""
    shapes = reviews["posted_at"].astype(str).map(lambda value: re.sub(r"\d", "#", value))
    return shapes.value_counts()


def main():
    apps, reviews = load()

    print("=" * 64)
    print("SHOPIFY APP STORE - DATA QUALITY AUDIT")
    print("=" * 64)
    print(f"apps.csv:    {len(apps):,} rows x {apps.shape[1]} columns")
    print(f"reviews.csv: {len(reviews):,} rows x {reviews.shape[1]} columns")

    print("\n[1] MIXED DATE FORMATS in reviews.posted_at")
    for shape, count in date_formats(reviews).items():
        print(f"      {shape}  ->  {count:,} rows")
    print("      A single-format parse silently nulls whichever format it was not given,")
    print("      which would drop most of the Time Intelligence page.")
    parsed = pd.to_datetime(reviews["posted_at"], format="mixed")
    print(f"      format='mixed' parses all {len(parsed):,} rows: "
          f"{parsed.min():%Y-%m-%d} to {parsed.max():%Y-%m-%d}")

    print("\n[2] OUT-OF-RANGE RATINGS (scale should be 1-5)")
    counts = reviews["rating"].value_counts().sort_index()
    for rating, count in counts.items():
        flag = "  <-- invalid" if rating < 1 or rating > 5 else ""
        print(f"      rating {rating}: {count:,}{flag}")
    invalid = reviews[(reviews["rating"] < 1) | (reviews["rating"] > 5)]
    clean = reviews[(reviews["rating"] >= 1) & (reviews["rating"] <= 5)]
    print(f"      {len(invalid)} invalid rows. Average rating including them: "
          f"{reviews['rating'].mean():.3f}, excluding them: {clean['rating'].mean():.3f}")

    print("\n[3] INCONSISTENT CATEGORY CASING")
    for name in sorted(apps["category_name"].unique()):
        if name.isupper():
            flag = "  <-- ALL CAPS"
        elif name.islower():
            flag = "  <-- all lowercase"
        else:
            flag = ""
        print(f"      {name}{flag}")
    print(f"      {apps['category_name'].nunique()} distinct values; normalising the casing is")
    print("      required before they group correctly in a visual.")

    print("\n[4] MISSING AND DUPLICATE APP METADATA")
    print(f"      apps with no developer:   {apps['developer'].isna().sum()}")
    print(f"      duplicate app_name values: {apps['app_name'].duplicated().sum()}")
    print(f"      apps with no monthly_price_usd (free apps): "
          f"{apps['monthly_price_usd'].isna().sum()}")

    print("\n[5] APPS WITH ZERO REVIEWS")
    reviewed = reviews["app_id"].nunique()
    print(f"      {apps['app_id'].nunique() - reviewed} of {apps['app_id'].nunique()} apps have no reviews.")
    print("      An inner join drops them, so any 'average rating per app' visual is")
    print("      silently computed over the reviewed subset only.")

    print("\n" + "=" * 64)
    print("HEADLINE KPIS (after cleaning: valid ratings only, mixed date parse)")
    print("=" * 64)
    joined = clean.merge(apps, on="app_id", how="left")
    print(f"Apps:                 {apps['app_id'].nunique():,}")
    print(f"Developers:           {apps['developer'].nunique():,}")
    print(f"Reviews:              {len(clean):,}")
    print(f"Average rating:       {clean['rating'].mean():.2f}")
    print(f"Developer reply rate: {clean['has_developer_reply'].eq('Yes').mean() * 100:.1f}%")
    print(f"Apps with a free plan: {apps['has_free_plan'].eq('Yes').sum():,} "
          f"({apps['has_free_plan'].eq('Yes').mean() * 100:.0f}%)")
    print(f"Median monthly price: ${apps['monthly_price_usd'].median():.2f} (paid apps only)")

    print("\nREVIEW VOLUME BY YEAR")
    by_year = clean.assign(year=pd.to_datetime(clean["posted_at"], format="mixed").dt.year)
    for year, count in by_year["year"].value_counts().sort_index().items():
        print(f"      {year}: {count:,}")

    print("\nBY CATEGORY (casing normalised)")
    # Title-case for consistent grouping, with SEO kept as an acronym
    joined["category"] = joined["category_name"].str.title().replace({"Seo": "SEO"})
    summary = (
        joined.groupby("category")
        .agg(
            apps=("app_id", "nunique"),
            reviews=("review_id", "count"),
            avg_rating=("rating", "mean"),
            reply_rate=("has_developer_reply", lambda s: s.eq("Yes").mean() * 100),
        )
        .round(2)
        .sort_values("reviews", ascending=False)
    )
    print(summary.to_string())


if __name__ == "__main__":
    main()
