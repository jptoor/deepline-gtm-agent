"""Export a capped, post-cutoff set of reply threads from Lemlist."""
from __future__ import annotations

import csv, json, subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

CUTOFF = datetime(2026, 3, 1, tzinfo=timezone.utc)
OUT = Path("deepline/data/jai-reply-copilot/voice-history-seed.csv")


def page(offset: int) -> list[dict]:
    command = ["deepline", "tools", "execute", "lemlist_get_activities", "--input", json.dumps({"type": "emailsReplied", "limit": 100, "offset": offset}), "--json"]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["toolResponse"]["raw"]


def main() -> None:
    chosen: dict[str, dict] = {}
    # Activities are returned newest-first. Fetch the first 1,500 records with
    # the provider's advertised 10 rps ceiling, then stop at the March cutoff.
    with ThreadPoolExecutor(max_workers=10) as pool:
        pages = list(pool.map(page, range(0, 1500, 100)))
    rows = sorted((row for batch in pages for row in batch), key=lambda row: row["createdAt"], reverse=True)
    for row in rows:
            occurred = datetime.fromisoformat(row["createdAt"].replace("Z", "+00:00"))
            if occurred < CUTOFF:
                break
            # Fetching the whole thread gives us the real outbound response(s),
            # unlike the activity list's campaign-send records.
            if row.get("contactId"):
                chosen.setdefault(row["contactId"], {"contact_id": row["contactId"], "user_id": row.get("sendUserId", ""), "created_at": row["createdAt"]})
                if len(chosen) == 500:
                    break
    with OUT.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["contact_id", "user_id", "created_at"])
        writer.writeheader()
        writer.writerows(chosen.values())
    print(f"Exported {len(chosen)} post-cutoff reply candidates to {OUT}")


if __name__ == "__main__":
    main()
