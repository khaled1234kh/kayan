"""Read and verify the pinned Enterprise ATT&CK corpus for offline retrieval."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from zipfile import ZipFile

from ..config import MitreConfig

_TECHNIQUE_ID = re.compile(r"T[0-9]{4}(?:\.[0-9]{3})?\Z")


@dataclass(frozen=True)
class MitreTechnique:
    technique_id: str
    name: str
    description: str
    tactics: tuple[str, ...]
    detection: str
    mitigations: tuple[str, ...]
    url: str
    is_subtechnique: bool = False
    raw_text: str = field(default="", repr=False)
    stix_id: str = ""
    object_version: str = ""
    parent_id: str | None = None
    mitigation_ids: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    detection_strategies: tuple[str, ...] = ()


def _active(obj: dict) -> bool:
    return not (obj.get("revoked") or obj.get("x_mitre_deprecated"))


def _reference(obj: dict) -> dict:
    return next((ref for ref in obj.get("external_references", [])
                 if ref.get("source_name") == "mitre-attack" and ref.get("external_id")), {})


def parse_techniques(document: dict) -> list[MitreTechnique]:
    objects = document["objects"]
    patterns = {}
    mitigations = {}
    strategies = {}
    for obj in objects:
        if not _active(obj):
            continue
        reference = _reference(obj)
        if obj["type"] == "attack-pattern" and _TECHNIQUE_ID.fullmatch(reference.get("external_id", "")):
            patterns[obj["id"]] = (obj, reference)
        if obj["type"] == "x-mitre-detection-strategy":
            strategies[obj["id"]] = obj["name"]
        if obj["type"] == "course-of-action" and reference.get("external_id"):
            mitigations[obj["id"]] = (reference["external_id"], obj["name"])

    linked_mitigations: dict[str, set[tuple[str, str]]] = defaultdict(set)
    parents: dict[str, str] = {}
    detections: dict[str, set[str]] = defaultdict(set)
    for obj in objects:
        if obj["type"] != "relationship" or not _active(obj):
            continue
        source, target = obj["source_ref"], obj["target_ref"]
        if obj["relationship_type"] == "mitigates" and source in mitigations and target in patterns:
            linked_mitigations[target].add(mitigations[source])
        if obj["relationship_type"] == "detects" and source in strategies and target in patterns:
            detections[target].add(strategies[source])
        if obj["relationship_type"] == "subtechnique-of" and source in patterns and target in patterns:
            parents[source] = patterns[target][1]["external_id"]

    techniques = []
    for stix_id, (obj, reference) in patterns.items():
        tid = reference["external_id"]
        name = obj["name"]
        tactics = tuple(sorted({phase["phase_name"] for phase in obj.get("kill_chain_phases", [])
                                if phase.get("kill_chain_name") == "mitre-attack"}))
        description = " ".join(obj.get("description", "").split())
        detection = " ".join(obj.get("x_mitre_detection", "").split())
        links = sorted(linked_mitigations[stix_id])
        names = tuple(name for _, name in links)
        raw = " ".join((tid, name, " ".join(tactics), description, detection, " ".join(names)))
        techniques.append(MitreTechnique(
            technique_id=tid, name=name, description=description, tactics=tactics,
            detection=detection, mitigations=names, url=reference.get("url", ""),
            is_subtechnique=bool(obj.get("x_mitre_is_subtechnique")),
            raw_text=raw, stix_id=stix_id, object_version=obj.get("x_mitre_version", ""),
            parent_id=parents.get(stix_id), mitigation_ids=tuple(mid for mid, _ in links),
            platforms=tuple(sorted(obj.get("x_mitre_platforms", []))),
            aliases=tuple(sorted(obj.get("x_mitre_aliases", []))),
            detection_strategies=tuple(sorted(detections[stix_id])),
        ))
    if not techniques or len({item.technique_id for item in techniques}) != len(techniques):
        raise ValueError("Invalid ATT&CK technique catalogue")
    return sorted(techniques, key=lambda item: item.technique_id)


def load_techniques(config: MitreConfig) -> list[MitreTechnique]:
    with ZipFile(config.archive_path) as archive:
        raw = archive.read(config.archive_member)
    if sha256(raw).hexdigest() != config.sha256:
        raise ValueError("ATT&CK archive member SHA-256 mismatch")
    document = json.loads(raw)
    collections = [obj.get("x_mitre_version") for obj in document["objects"]
                   if obj["type"] == "x-mitre-collection" and obj.get("name") == "Enterprise ATT&CK"]
    if document.get("type") != "bundle" or collections != [config.version]:
        raise ValueError("ATT&CK Enterprise collection version mismatch")
    return parse_techniques(document)
