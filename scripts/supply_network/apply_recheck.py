"""Apply a link re-check to the supply network.

Reads a re-check log (source-data/supply-network/rechecks/<name>.csv) with columns
supplier,buyer,verdict,evidence_url,evidence_date,note and updates edges.csv:

- confirmed         -> date/source replaced with the newer evidence, status cleared
- open-unconfirmed  -> kept, status = "unconfirmed" (the guide shows it as an older mention)
- buyer-closed, supplier-closed, contradicted
                    -> moved to edges_retired.csv with the reason and evidence

Then recomputes the out/inn counts in nodes.csv.

    python scripts/supply_network/apply_recheck.py rechecks/2026-10-04_pre2020.csv
"""
import csv
import re
import sys
from pathlib import Path

NET = Path(__file__).resolve().parents[2] / "inputs" / "supply-network"
FIELDS = ["supplier", "buyer", "date", "confidence", "source", "note", "status"]
RETIRED_FIELDS = FIELDS[:-1] + ["retired", "reason", "evidence", "evidence_date"]
# Self-published evidence (the farm or restaurant naming the other) is high confidence.
CONFIRMED_CONFIDENCE = {"confirmed": "high", "confirmed-weak": "medium"}


def norm(s):
    s = re.sub(r"\s*\((?!closed)[^)]*\)", "", s)  # "Basta (Boulder)" -> "Basta"; keep "(closed)"
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("é", "e")).strip()


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    # Match the existing files: UTF-8 with BOM, LF line endings.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(log_path):
    log = read(NET / log_path)
    checked_on = re.search(r"\d{4}-\d{2}-\d{2}", log_path).group(0)
    edges = read(NET / "edges.csv")
    for e in edges:
        e.setdefault("status", "")
    retired_path = NET / "edges_retired.csv"
    retired = read(retired_path) if retired_path.exists() else []

    index = {(norm(e["supplier"]), norm(e["buyer"])): e for e in edges}
    keep_ids, missing = {id(e) for e in edges}, []
    added = 0
    for r in log:
        key = (norm(r["supplier"]), norm(r["buyer"]))
        e = index.get(key)
        v = r["verdict"]
        date = checked_on[:7] if r["evidence_date"] == "current" else r["evidence_date"]
        if v == "new-link":
            if e:
                continue
            edges.append({"supplier": r["supplier"], "buyer": r["buyer"], "date": date, "confidence": "high",
                          "source": r["evidence_url"], "note": r.get("edge_note", ""), "status": ""})
            index[key] = edges[-1]
            keep_ids.add(id(edges[-1]))
            added += 1
            continue
        if not e:
            missing.append(f"{r['supplier']} -> {r['buyer']}")
            continue
        if v in CONFIRMED_CONFIDENCE:
            e.update(date=date, source=r["evidence_url"], confidence=CONFIRMED_CONFIDENCE[v], status="")
            if r.get("edge_note"):
                e["note"] = r["edge_note"]
        elif v == "open-unconfirmed":
            e["status"] = "unconfirmed"
        elif v in ("buyer-closed", "supplier-closed", "contradicted"):
            keep_ids.discard(id(e))
            retired.append({**e, "retired": checked_on, "reason": f"{v}: {r['note']}",
                            "evidence": r["evidence_url"], "evidence_date": r["evidence_date"]})
        else:
            sys.exit(f"unknown verdict {v!r} for {r['supplier']} -> {r['buyer']}")

    if missing:
        sys.exit("log rows with no matching edge:\n  " + "\n  ".join(missing))
    edges = [e for e in edges if id(e) in keep_ids]
    write(NET / "edges.csv", edges, FIELDS)
    write(retired_path, retired, RETIRED_FIELDS)

    nodes = read(NET / "nodes.csv")
    out = {n["name"]: 0 for n in nodes}
    inn = dict(out)
    for e in edges:
        out[e["supplier"]] = out.get(e["supplier"], 0) + 1
        inn[e["buyer"]] = inn.get(e["buyer"], 0) + 1
    unknown = sorted(({e["supplier"] for e in edges} | {e["buyer"] for e in edges}) - {n["name"] for n in nodes})
    if unknown:
        sys.exit(f"edges name businesses missing from nodes.csv: {unknown}")
    for n in nodes:
        n["out"], n["inn"] = out[n["name"]], inn[n["name"]]
    write(NET / "nodes.csv", nodes, list(nodes[0].keys()))

    counts = {}
    for r in log:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"applied {len(log)} rows {counts}; {added} new links; edges now {len(edges)}, retired {len(retired)}")


if __name__ == "__main__":
    main(sys.argv[1])
