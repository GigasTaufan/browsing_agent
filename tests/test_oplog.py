"""Unit test oplog.log_event: format JSON line ke stderr."""

import json

from oplog import log_event


def test_log_event_writes_json_line_to_stderr(capsys):
    log_event("test.event", status="ok", count=3)

    captured = capsys.readouterr()
    assert captured.out == ""
    record = json.loads(captured.err)

    assert record["event"] == "test.event"
    assert record["status"] == "ok"
    assert record["count"] == 3
    assert "ts" in record and record["ts"].endswith(("Z", "+00:00"))


def test_log_event_handles_non_serializable_values(capsys):
    log_event("test.event", error=ValueError("boom"))

    record = json.loads(capsys.readouterr().err)
    assert "boom" in record["error"]
