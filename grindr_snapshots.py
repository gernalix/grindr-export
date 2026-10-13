"""Ordered overlap reconciliation, not global text deduplication."""
import json


def signature(child):
    # Geometry changes as scrolling proceeds; event text/media/order do not.
    bubble = child.get("bubble") or {}
    return json.dumps({
        "nativeId": child.get("nativeId"),
        "text": child.get("text") or child.get("innerText") or "",
        "bubbleText": bubble.get("text") or bubble.get("innerText") or "",
        "bubbleAria": bubble.get("aria"),
        "media": [(field, x.get("src") or x.get("urlRedacted"), x.get("alt"))
                  for field in ("images", "videos", "audios") for x in child.get(field, [])],
    }, sort_keys=True, ensure_ascii=False)


def reconcile(data):
    snapshots = data.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("raw/dom_snapshots.json must contain at least one snapshot")
    assembled, keys = [], []
    for snapshot in snapshots:
        page = list(reversed(snapshot["children"]))
        # Empty sentinel nodes are not messages and have no overlap identity.
        page = [c for c in page if (c.get("text") or c.get("innerText") or
                any(c.get(f) for f in ("images", "videos", "audios")))]
        incoming = [signature(c) for c in page]
        if not incoming:
            continue
        if not keys:
            assembled, keys = page, incoming
            continue
        matches = [i for i in range(len(keys) - len(incoming) + 1)
                   if keys[i:i + len(incoming)] == incoming]
        if matches:
            if len(matches) != 1 or (len(incoming) > 1 and len(set(incoming)) == 1):
                raise ValueError("Ambiguous repeated-event overlap; completion cannot be inferred")
            continue
        overlap = next((n for n in range(min(len(keys), len(incoming)), 0, -1)
                        if keys[-n:] == incoming[:n]), 0)
        if not overlap:
            raise ValueError("Gap or out-of-order snapshot sequence; do not discard pages")
        if overlap == 1 and not page[0].get("nativeId"):
            raise ValueError("Single unidentifiable overlap is insufficient for complete reconciliation")
        if len(set(incoming[:overlap])) == 1 and not all(c.get("nativeId") for c in page[:overlap]):
            raise ValueError("Repeated identical events cannot identify an overlap")
        assembled.extend(page[overlap:])
        keys.extend(incoming[overlap:])
    result = dict(snapshots[0])
    result.update(children=list(reversed(assembled)), childCount=len(assembled),
                  startMarkerPresent=any(s.get("startMarkerPresent") for s in snapshots),
                  reconciledSnapshotCount=len(snapshots), snapshotContinuityVerified=True)
    return result
