"""Rebuild the offline index from pinned official MITRE/OWASP repository snapshots."""
import hashlib
import json
import re
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "KAYAN-offline-grounding-index"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def plain(markdown):
    markdown = re.sub(r"\(Citation:[^)]+\)", "", markdown)
    markdown = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    markdown = re.sub(r"<[^>]+>", " ", markdown)
    return re.sub(r"\s+", " ", markdown).strip()


def build():
    attack_commit = json.loads(download("https://api.github.com/repos/mitre-attack/attack-stix-data/commits/master"))["sha"]
    owasp_commit = json.loads(download("https://api.github.com/repos/OWASP/Top10/commits/master"))["sha"]
    sources, entries = [], {}

    def attack(domain):
        url = f"https://raw.githubusercontent.com/mitre-attack/attack-stix-data/{attack_commit}/{domain}/{domain}.json"
        raw = download(url)
        objects = json.loads(raw)["objects"]
        result = []
        for obj in objects:
            if obj.get("type") != "attack-pattern":
                continue
            reference = next((r for r in obj.get("external_references", []) if r.get("external_id", "").startswith("T")), None)
            if not reference:
                continue
            tactics = [p["phase_name"] for p in obj.get("kill_chain_phases", [])]
            description = plain(obj.get("description", ""))
            result.append({"id": reference["external_id"], "framework": "mitre-attack", "name": obj["name"],
                           "tactic": ", ".join(tactics), "tactics": tactics, "description": description,
                           "keywords": [obj["name"].lower(), *tactics], "domains": [domain],
                           "revoked": bool(obj.get("revoked")), "deprecated": bool(obj.get("x_mitre_deprecated")),
                           "source_url": reference.get("url", url), "source_modified": obj.get("modified")})
        return result, {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "commit": attack_commit}

    with ThreadPoolExecutor(max_workers=3) as pool:
        for result, source in pool.map(attack, ["enterprise-attack", "mobile-attack", "ics-attack"]):
            sources.append(source)
            for entry in result:
                if entry["id"] in entries:
                    entries[entry["id"]]["domains"] = sorted(set(entries[entry["id"]]["domains"] + entry["domains"]))
                else:
                    entries[entry["id"]] = entry

    for year in (2025, 2021):
        listing = json.loads(download(f"https://api.github.com/repos/OWASP/Top10/contents/{year}/docs/en?ref={owasp_commit}"))
        categories = [item for item in listing if re.match(r"A(?:0[1-9]|10)_", item["name"])]
        if len(categories) != 10:
            raise ValueError(f"Expected all ten OWASP {year} categories, got {len(categories)}")
        def category(item):
            url = f"https://raw.githubusercontent.com/OWASP/Top10/{owasp_commit}/{year}/docs/en/{urllib.parse.quote(item['name'])}"
            raw = download(url)
            text = raw.decode("utf-8-sig")
            identifier = item["name"].split("_")[0] + f":{year}"
            name = item["name"].split("-", 1)[1].removesuffix(".md").replace("_", " ")
            section = re.search(r"(?ims)^##\s+Description\s*\n(.*?)(?=^##\s|\Z)", text)
            description = plain(section.group(1) if section else text)
            entry = {"id": identifier, "framework": "owasp-top10", "version": str(year), "name": name,
                     "tactic": "Application security", "description": description,
                     "keywords": [name.lower(), *sorted(set(re.findall(r"CWE-\d+", text)))],
                     "example_weaknesses": sorted(set(re.findall(r"CWE-\d+", text))),
                     "historical": year == 2021, "source_url": url}
            return entry, {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "commit": owasp_commit}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for entry, source in pool.map(category, categories):
                entries[entry["id"]] = entry
                sources.append(source)

    licenses = {}
    (ROOT / "licenses").mkdir(exist_ok=True)
    for framework, repo, commit, filename, local_name in [
        ("mitre-attack", "mitre-attack/attack-stix-data", attack_commit, "LICENSE.txt", "MITRE_ATTACK_LICENSE.txt"),
        ("owasp-top10", "OWASP/Top10", owasp_commit, "LICENSE", "OWASP_TOP10_LICENSE.txt"),
    ]:
        raw = download(f"https://raw.githubusercontent.com/{repo}/{commit}/{filename}")
        (ROOT / "licenses" / local_name).write_bytes(raw)
        licenses[framework] = f"licenses/{local_name}"
    output = {"schema_version": 1, "built_at": datetime.now(timezone.utc).isoformat(), "license_files": licenses,
              "attribution": "MITRE ATT&CK (MITRE Corporation) and OWASP Top 10; official source URLs, commits and hashes retained.",
              "sources": sources, "entries": sorted(entries.values(), key=lambda e: (e["framework"], e["id"]))}
    (ROOT / "index.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"entries": len(entries), "frameworks": dict(Counter(e["framework"] for e in entries.values())),
                      "attack_commit": attack_commit, "owasp_commit": owasp_commit}), flush=True)


if __name__ == "__main__":
    build()
