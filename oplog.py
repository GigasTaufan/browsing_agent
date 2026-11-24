"""
Log operasional terstruktur: satu baris JSON per event ke stderr.
stdout tetap bersih untuk UX CLI; stderr ditangkap operator/aggregator.
"""

import json
import sys
from datetime import UTC, datetime


def log_event(event: str, **fields) -> None:
    """Cetak satu event sebagai JSON line: {"ts": ..., "event": ..., **fields}."""
    record = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "event": event,
        **fields,
    }
    print(json.dumps(record, ensure_ascii=False, default=str), file=sys.stderr, flush=True)
