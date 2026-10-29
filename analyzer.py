"""Support Ticket Analyzer — turn a ticket export into an ops summary.

Reads a CSV of support tickets and reports:
  * ticket volume by category and priority
  * average resolution time (hours) for resolved tickets
  * SLA breach rate per priority (resolved after its SLA target)
  * the busiest day and the most common category

Usage:
    python analyzer.py tickets.csv [--report report.md] [--summary summary.csv]

Ticket CSV columns:
    id, created_date, resolved_date, category, priority, status
    - dates: YYYY-MM-DD
    - priority: Low / Medium / High / Critical
    - status: resolved / open
    - resolved_date may be blank for open tickets

SLA targets (hours from creation to resolution):
    Critical: 8, High: 24, Medium: 72, Low: 120

Only the Python standard library + pandas are needed.
"""

import argparse
import sys

import pandas as pd

SLA_HOURS = {"Critical": 8, "High": 24, "Medium": 72, "Low": 120}


def load_tickets(path):
    df = pd.read_csv(path)
    required = {"id", "created_date", "resolved_date", "category", "priority", "status"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")
    df["created_date"] = pd.to_datetime(df["created_date"])
    df["resolved_date"] = pd.to_datetime(df["resolved_date"], errors="coerce")
    return df


def analyze(df):
    resolved = df[df["status"] == "resolved"].copy()
    resolved["resolution_hours"] = (
        resolved["resolved_date"] - resolved["created_date"]
    ).dt.total_seconds() / 3600
    resolved["sla_target"] = resolved["priority"].map(SLA_HOURS)
    resolved["breached_sla"] = resolved["resolution_hours"] > resolved["sla_target"]

    by_category = df["category"].value_counts().rename_axis("category").reset_index(name="tickets")
    by_priority = df["priority"].value_counts().rename_axis("priority").reset_index(name="tickets")

    sla_by_priority = (
        resolved.groupby("priority")
        .agg(tickets=("id", "count"),
             avg_resolution_hours=("resolution_hours", "mean"),
             sla_breaches=("breached_sla", "sum"))
        .reset_index()
    )
    sla_by_priority["sla_breach_rate_pct"] = (
        sla_by_priority["sla_breaches"] / sla_by_priority["tickets"] * 100
    ).round(1)
    sla_by_priority["avg_resolution_hours"] = sla_by_priority["avg_resolution_hours"].round(1)

    busiest_day = df["created_date"].dt.date.value_counts().idxmax()
    summary = {
        "total_tickets": len(df),
        "resolved": len(resolved),
        "open": int((df["status"] == "open").sum()),
        "avg_resolution_hours": round(resolved["resolution_hours"].mean(), 1)
        if len(resolved) else None,
        "overall_sla_breach_rate_pct": round(resolved["breached_sla"].mean() * 100, 1)
        if len(resolved) else None,
        "top_category": by_category.iloc[0]["category"],
        "busiest_day": str(busiest_day),
    }
    return summary, by_category, by_priority, sla_by_priority


def render_report(summary, by_category, by_priority, sla_by_priority):
    lines = ["# Support Ticket Summary", ""]
    lines.append(f"- Total tickets: {summary['total_tickets']}")
    lines.append(f"- Resolved: {summary['resolved']} | Open: {summary['open']}")
    lines.append(f"- Average resolution time: {summary['avg_resolution_hours']} hours")
    lines.append(f"- Overall SLA breach rate: {summary['overall_sla_breach_rate_pct']}%")
    lines.append(f"- Most common category: {summary['top_category']}")
    lines.append(f"- Busiest day: {summary['busiest_day']}")
    lines.append("")
    lines.append("## Tickets by category")
    for _, row in by_category.iterrows():
        lines.append(f"- {row['category']}: {row['tickets']}")
    lines.append("")
    lines.append("## Tickets by priority")
    for _, row in by_priority.iterrows():
        lines.append(f"- {row['priority']}: {row['tickets']}")
    lines.append("")
    lines.append("## SLA performance by priority")
    lines.append("| Priority | Resolved | Avg resolution (h) | Breaches | Breach rate |")
    lines.append("|---|---|---|---|---|")
    for _, row in sla_by_priority.iterrows():
        lines.append(
            f"| {row['priority']} | {row['tickets']} | {row['avg_resolution_hours']} "
            f"| {row['sla_breaches']} | {row['sla_breach_rate_pct']}% |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze a support ticket CSV export.")
    parser.add_argument("csv", help="Path to the tickets CSV file")
    parser.add_argument("--report", default="report.md", help="Markdown report to write")
    parser.add_argument("--summary", default="summary.csv",
                        help="Per-priority SLA summary CSV to write")
    args = parser.parse_args(argv)

    df = load_tickets(args.csv)
    summary, by_category, by_priority, sla_by_priority = analyze(df)
    report = render_report(summary, by_category, by_priority, sla_by_priority)
    print(report)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report)
    sla_by_priority.to_csv(args.summary, index=False)
    print(f"Wrote {args.report} and {args.summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
