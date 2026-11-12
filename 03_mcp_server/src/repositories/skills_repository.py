import re
from pathlib import Path
from typing import List, TypedDict

import yaml

# 03_mcp_server/skills/ — sibling de src/, no dentro del paquete
SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.DOTALL)


class SkillFile(TypedDict):
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str, skill_md: Path) -> dict:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{skill_md} no tiene un frontmatter YAML válido (---...---)")
    meta = yaml.safe_load(match.group(1)) or {}
    if not meta.get("name") or not meta.get("description"):
        raise ValueError(f"{skill_md} debe declarar 'name' y 'description' en el frontmatter")
    return meta


def discover_skills() -> List[SkillFile]:
    """Escanea skills/*/SKILL.md y devuelve su metadata (sin cargar el contenido
    completo — progressive disclosure: el contenido se lee bajo demanda con
    read_skill_content)."""
    if not SKILLS_DIR.is_dir():
        return []

    skills: List[SkillFile] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text, skill_md)
        skills.append({"name": meta["name"], "description": meta["description"], "path": skill_md})
    return skills


def read_skill_content(path: Path) -> str:
    return path.read_text(encoding="utf-8")
