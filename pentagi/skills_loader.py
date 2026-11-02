"""Skill loader — loads curated skill packets for agent roles."""

import json
import os
from typing import Dict, List


SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def load_skills(role: str) -> List[Dict]:
    """Load skill packets for a given agent role."""
    role_dir = os.path.join(SKILLS_DIR, role.replace("_agent", "").replace("webapp", "web-app"))
    if not os.path.exists(role_dir):
        return []
    skills = []
    for fname in os.listdir(role_dir):
        if fname.endswith(".json"):
            with open(os.path.join(role_dir, fname), "r", encoding="utf-8") as f:
                skills.append(json.load(f))
    return skills


def get_skill_context(role: str) -> str:
    """Build a system-prompt context string from skill packets."""
    skills = load_skills(role)
    if not skills:
        return ""
    lines = [f"## Skill Packets for {role}"]
    for skill in skills:
        lines.append(f"\n### {skill.get('name', 'Unknown')}")
        lines.append(f"MITRE: {skill.get('mitre_id', 'N/A')} — {skill.get('mitre_name', 'N/A')}")
        lines.append(f"Description: {skill.get('description', '')}")
        if skill.get("techniques"):
            lines.append("Techniques:")
            for t in skill["techniques"]:
                lines.append(f"  - {t}")
        if skill.get("detection"):
            lines.append(f"Detection: {skill['detection']}")
    return "\n".join(lines)
