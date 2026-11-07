import pandas as pd

from analyzer import analyze, load_tickets


def test_analyzer_with_sample_csv(tmp_path):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text(
        "\n".join(
            [
                "id,created_date,resolved_date,category,priority,status",
                "1,2026-01-01,2026-01-02,Billing,High,resolved",
                "2,2026-01-01,2026-01-06,Technical,Low,resolved",
                "3,2026-01-02,,Billing,Medium,open",
            ]
        ),
        encoding="utf-8",
    )

    df = load_tickets(csv_path)

    assert pd.api.types.is_datetime64_any_dtype(df["created_date"])
    assert pd.api.types.is_datetime64_any_dtype(df["resolved_date"])

    summary, by_category, by_priority, sla_by_priority = analyze(df)

    assert summary == {
        "total_tickets": 3,
        "resolved": 2,
        "open": 1,
        "avg_resolution_hours": 72.0,
        "overall_sla_breach_rate_pct": 0.0,
        "top_category": "Billing",
        "busiest_day": "2026-01-01",
    }

    assert by_category.set_index("category")["tickets"].to_dict() == {
        "Billing": 2,
        "Technical": 1,
    }
    assert by_priority.set_index("priority")["tickets"].to_dict() == {
        "High": 1,
        "Low": 1,
        "Medium": 1,
    }
    assert sla_by_priority.set_index("priority")[
        ["tickets", "avg_resolution_hours", "sla_breaches", "sla_breach_rate_pct"]
    ].to_dict("index") == {
        "High": {
            "tickets": 1,
            "avg_resolution_hours": 24.0,
            "sla_breaches": 0,
            "sla_breach_rate_pct": 0.0,
        },
        "Low": {
            "tickets": 1,
            "avg_resolution_hours": 120.0,
            "sla_breaches": 0,
            "sla_breach_rate_pct": 0.0,
        },
    }
