"""Board bookkeeping: flexd operational-acceptance batch merged (2026-10-17).

Run from board/ as OptimalNothing90 after `python fetch.py` showed 0 drift.
Idempotent body append on FLEXD-1 and EPIC-EVCC (marker guard).
"""

from lib import append_to_body_idempotent, find_item, load_items, save_items

MARK = "## Status 2026-10-17"

data = load_items()


def note(card_id: str, text: str) -> None:
    card = find_item(data, card_id)
    changed, body = append_to_body_idempotent(card["draft_id"], MARK, f"\n\n{MARK}\n{text}")
    card["body"] = body
    print(f"{card_id}: {'appended' if changed else 'unchanged (marker present)'}")


note(
    "FLEXD-1",
    "Second batch on main (33a1048..f91ac67, suite 173 -> 226) after an adversarial Codex review of the HIGH fixes: "
    "ttl validates with a persistence context and the registry loader keeps valid entries (Medium 1 closed); "
    "refresh rejects expired demands; query floats bounded and 422 body lean; withdrawn/expired demands read OFF "
    "immediately on HTTP and get an explicit retained 0 on MQTT (Medium 11 partly); accrual runs to the real "
    "adoption instant; Demand.modulating drives per-slot semi-continuous flags with whole operating_timesteps for "
    "non-modulating loads (Medium 5 closed), grid anchored like EMHASS method_ts_round. "
    "Open: Mediums 2, 3, 7, 8, 9, 10, 12 and Lows; compose e2e smoke against v0.18.6 before the shadow run "
    "(compose pulls emhass:latest).",
)
note(
    "EPIC-EVCC",
    "flexd acceptance batch merged 2026-10-17 (see FLEXD-1). Shadow run with LesIT1 waits for the compose e2e smoke "
    "against v0.18.6.",
)

save_items(data)
print("items.json saved")
