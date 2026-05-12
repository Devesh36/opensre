"""Linear integration demo — simulate an alert and create a ticket automatically.

Usage:
    uv run python -m tests.synthetic.linear_demo
"""

import json
from datetime import datetime, timezone

from app.integrations.store import get_integration


def main() -> None:
    print("=" * 55)
    print("  🚀 OpenSRE → Linear Integration Demo")
    print("=" * 55)

    # 1. Load stored Linear config
    print("\n[1/4] Loading Linear config from store...")
    record = get_integration("linear")
    if not record:
        print("  ❌ Linear integration not found. Run: opensre integrations setup linear")
        return

    linear = record["credentials"]
    print("  ✅ Linear configured!")

    # 2. Simulate an alert coming in
    print("\n[2/4] Simulating alert...")

    alert = {
        "name": "High error rate in checkout-api",
        "severity": "critical",
        "service": "checkout-api (production)",
        "message": "Error rate 18.7% (threshold 5%), last 15 minutes. P99 latency 2.3s.",
        "source": "Grafana",
        "dashboard": "checkout-api/production/overview",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(f"  🔔 Alert: {alert['name']}")
    print(f"  📈 {alert['message']}")

    # 3. Simulate investigation findings
    print("\n[3/4] Agent investigating...")
    print("  🔍 Checking Grafana dashboard...")
    print("  🔍 Querying logs for errors...")
    print("  🔍 Checking database connection pool...")

    findings = f"""
## Investigation Report: {alert["name"]}

**Severity:** {alert["severity"]}  
**Service:** {alert["service"]}  
**Source:** {alert["source"]}  
**Time:** {alert["timestamp"]}

### Alert Details
{alert["message"]}

### Root Cause Analysis
Database connection pool exhausted due to slow query on `transactions` table.
Full table scan on 50M rows causing query timeout at 30s.

### Impact
- Payment processing delayed by ~8 minutes
- ~1,500 customers affected
- 23 failed transactions

### Evidence
- **Grafana:** {alert["dashboard"]}
- **Logs:** Connection pool timeout errors in checkout-api logs
- **CloudWatch:** ConnectionPoolFullCount = 98/100 at peak

### Recommendation
1. Add composite index on `transactions(status, created_at)`
2. Increase pool size from 100 → 200
3. Add PagerDuty alert at 80% pool usage
"""
    print("  ✅ Investigation complete!")

    # 4. Create Linear ticket
    print(f"\n[4/4] Creating Linear ticket...")

    from app.tools.LinearCreateIssueTool import linear_create_issue

    result = linear_create_issue.run(
        api_key=linear["api_key"],
        team_id=linear["default_team_id"],
        title=f"[Incident] {alert['name']}",
        description=findings.strip(),
        priority=2,
    )

    if result["available"]:
        print(f"  ✅ Ticket created!")
        print(f"  🆔 {result['issue_identifier']}")
        print(f"  🔗 {result['url']}")
    else:
        print(f"  ❌ Failed: {result.get('error', 'unknown error')}")

    print("\n" + "=" * 55)
    print("  Demo complete! 🎉")
    print("=" * 55)


if __name__ == "__main__":
    main()
