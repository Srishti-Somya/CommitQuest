"""Export GitHub contribution calendar for a user to CSV or JSON.

Usage:
  python3 scripts/export_contributions.py <username> <token> <from_date> <to_date> --csv out.csv
  python3 scripts/export_contributions.py <username> <token> <from_date> <to_date> --json out.json

Dates should be YYYY-MM-DD.
"""
import sys
import argparse
import json
import pandas as pd

from utils.fetch_github_data import fetch_data_for_duration


def weeks_to_dataframe(weeks):
    days = [day for week in weeks for day in week.get("contributionDays", [])]
    if not days:
        return pd.DataFrame()
    df = pd.DataFrame(days)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("token")
    parser.add_argument("from_date")
    parser.add_argument("to_date")
    parser.add_argument("--csv", dest="csvfile", help="Output CSV file path")
    parser.add_argument("--json", dest="jsonfile", help="Output JSON file path")
    args = parser.parse_args()

    data = fetch_data_for_duration(args.username, args.token, args.from_date, args.to_date)
    if not data or data.get("errors"):
        print("Error fetching data:", data)
        sys.exit(1)

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    df = weeks_to_dataframe(weeks)

    if args.csvfile:
        df.to_csv(args.csvfile)
        print(f"Wrote CSV to {args.csvfile}")

    if args.jsonfile:
        records = df.reset_index().to_dict(orient="records")
        with open(args.jsonfile, "w") as f:
            json.dump(records, f, indent=2, default=str)
        print(f"Wrote JSON to {args.jsonfile}")

    if not args.csvfile and not args.jsonfile:
        print(df.head())


if __name__ == "__main__":
    main()
