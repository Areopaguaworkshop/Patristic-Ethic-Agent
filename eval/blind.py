"""Export comparison responses without revealing their conditions."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    args = parser.parse_args()

    paths = [args.report, args.cases, args.packet, args.key]
    if len({p.resolve() for p in paths}) != 4 or any(p.exists() for p in paths[2:]):
        parser.error("inputs and outputs must be distinct, and both outputs must be new")

    report = args.report.read_bytes()
    report_hash = hashlib.sha256(report).hexdigest()
    comparison = json.loads(report)
    case_bytes = args.cases.read_bytes()
    if comparison.get("cases_sha256") != hashlib.sha256(case_bytes).hexdigest():
        parser.error("scenario file digest does not match the comparison report")
    cases = {}
    for line in case_bytes.decode("utf-8").splitlines():
        if line.strip():
            case = json.loads(line)
            if case["id"] in cases:
                parser.error("scenario IDs must be unique")
            cases[case["id"]] = [
                {"role": turn["role"], "text": turn["text"]} for turn in case["turns"]
            ]

    rows = comparison["cases"]
    if not rows:
        parser.error("comparison report contains no responses")
    packet, key = [], []
    for row in rows:
        review_id = secrets.token_hex(16)
        response = row["response"]
        packet.append(dict(review_id=review_id, turns=cases[row["id"]], response=response))
        key.append(dict(
            review_id=review_id,
            id=row["id"],
            repeat=row["repeat"],
            condition=row["condition"],
            report_sha256=report_hash,
            response_sha256=hashlib.sha256(response.encode("utf-8")).hexdigest(),
        ))

    secrets.SystemRandom().shuffle(packet)
    for path, records in ((args.key, key), (args.packet, packet)):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
