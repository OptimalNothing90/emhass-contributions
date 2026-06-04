import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "board"))
import lib  # noqa: E402


def test_update_draft_title_body_sends_both(monkeypatch):
    captured = {}

    def fake_gh(args, stdin=None):
        captured["args"] = args
        return json.dumps(
            {
                "data": {
                    "updateProjectV2DraftIssue": {
                        "draftIssue": {"id": "DI_x", "title": "New"}
                    }
                }
            }
        )

    monkeypatch.setattr(lib, "gh", fake_gh)
    title = lib.update_draft_title_body("DI_x", "New", "Body text")
    assert title == "New"
    joined = " ".join(captured["args"])
    assert "title=New" in joined
    assert "body=Body text" in joined
    assert "DI_x" in joined
