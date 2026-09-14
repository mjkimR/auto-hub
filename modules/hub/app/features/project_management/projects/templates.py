from pathlib import Path

from app.features.project_management.projects.schemas import TemplateId, TemplateRead

TEMPLATE_VERSION = "1.0.0"
TEMPLATE_ROOT = Path(__file__).resolve().parents[6] / "templates" / "github-actions"
TEMPLATE_PROFILES: list[tuple[TemplateId, str, list[str]]] = [
    ("python-uv", "Python + uv", ["lint", "test"]),
    ("node-npm", "Node + npm", ["lint", "test", "build"]),
]


def list_templates() -> list[TemplateRead]:
    return [
        TemplateRead(
            id=template_id,
            name=name,
            version=TEMPLATE_VERSION,
            changelog="Initial PR-only workflow with read-only lint/test commands and bounded execution.",
            required_jobs=jobs,
            filename="ci.yml",
            content=(TEMPLATE_ROOT / f"{template_id}.yml").read_text(encoding="utf-8"),
        )
        for template_id, name, jobs in TEMPLATE_PROFILES
    ]
