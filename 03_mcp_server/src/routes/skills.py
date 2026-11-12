from mcp.server.fastmcp import FastMCP

from src.repositories.skills_repository import SkillFile, discover_skills, read_skill_content


def register_skill_resources(mcp: FastMCP) -> None:
    """Expone cada skill descubierta en skills/*/SKILL.md como un recurso MCP
    (esquema skill://) en vez de como una tool: una skill es contenido de lectura
    que la app decide exponer (primitiva Resources), no una acción que el modelo
    ejecuta (primitiva Tools). El cliente puede listar todos los recursos (obtiene
    name/description de cada skill sin costo) y leer solo la que necesite."""
    for skill in discover_skills():
        _register_one(mcp, skill)


def _register_one(mcp: FastMCP, skill: SkillFile) -> None:
    def _load_skill_content() -> str:
        return read_skill_content(skill["path"])

    mcp.resource(
        f"skill://{skill['name']}/SKILL.md",
        name=skill["name"],
        description=skill["description"],
        mime_type="text/markdown",
    )(_load_skill_content)
