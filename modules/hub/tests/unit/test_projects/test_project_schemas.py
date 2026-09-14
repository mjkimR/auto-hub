from uuid import uuid4

import pytest
from app.features.projects.schemas import ProjectObservationPayload, ProjectUpdate, ProjectWrite
from app.features.projects.templates import TEMPLATE_PROFILES, list_templates
from pydantic import ValidationError

pytestmark = pytest.mark.unit

VERIFICATION = {"workflow": "ci.yml", "required_jobs": ["lint", "test"]}


def make_write(**overrides) -> dict:
    return {
        "name": "My application",
        "github": {
            "repository": "Owner/App",
            "github_connector_id": str(uuid4()),
            "verification": VERIFICATION,
        },
        **overrides,
    }


class TestProjectWrite:
    def test_repository_is_normalized_before_the_pattern_is_applied(self):
        data = make_write()
        data["github"]["repository"] = "  Owner/App  "
        project = ProjectWrite.model_validate(data)
        assert project.github is not None
        assert project.github.repository == "owner/app"

    @pytest.mark.parametrize("repository", ["owner", "owner/", "/app", "owner/app/extra", "-owner/app", "own er/app"])
    def test_malformed_repositories_are_rejected(self, repository):
        with pytest.raises(ValidationError):
            data = make_write()
            data["github"]["repository"] = repository
            ProjectWrite.model_validate(data)

    @pytest.mark.parametrize("name", ["", "   "])
    def test_blank_names_are_rejected(self, name):
        with pytest.raises(ValidationError):
            ProjectWrite.model_validate(make_write(name=name))

    def test_unknown_fields_are_rejected_so_stale_payloads_fail_loudly(self):
        with pytest.raises(ValidationError):
            ProjectWrite.model_validate(make_write(revision=2))

    def test_unknown_template_ids_are_rejected(self):
        with pytest.raises(ValidationError):
            ProjectWrite.model_validate(make_write(template_id="python-poetry"))

    def test_observation_config_carries_the_saved_connection(self):
        data = ProjectWrite.model_validate(make_write())
        assert data.github is not None
        config = data.observation_config([7, 9])
        assert (config.repository, config.pull_numbers) == ("owner/app", [7, 9])
        assert config.github_connector_id == data.github.github_connector_id
        assert config.verification == data.github.verification

    def test_project_can_be_created_without_any_provider_connection(self):
        project = ProjectWrite.model_validate({"name": "Planning"})
        assert project.github is None
        with pytest.raises(ValueError, match="GitHub connection"):
            project.observation_config([7])

    def test_updates_require_the_revision_the_editor_started_from(self):
        with pytest.raises(ValidationError):
            ProjectUpdate.model_validate(make_write())
        assert ProjectUpdate.model_validate(make_write(expected_revision=3)).expected_revision == 3


class TestProjectObservationPayload:
    @pytest.mark.parametrize("pull_numbers", [[], [0], [-1], [1, 1], list(range(1, 12))])
    def test_invalid_pull_selections_are_rejected(self, pull_numbers):
        with pytest.raises(ValidationError):
            ProjectObservationPayload(project_id=uuid4(), pull_numbers=pull_numbers)

    def test_payload_only_references_the_project_so_edits_are_never_stale(self):
        payload = ProjectObservationPayload(project_id=uuid4(), pull_numbers=[42])
        assert set(payload.model_dump()) == {"project_id", "pull_numbers"}


class TestTemplates:
    def test_every_profile_ships_a_readable_workflow_with_its_required_jobs(self):
        templates = list_templates()
        assert [template.id for template in templates] == [profile[0] for profile in TEMPLATE_PROFILES]
        for template in templates:
            assert template.filename == "ci.yml"
            assert template.version and template.changelog
            assert "pull_request" in template.content
            for job in template.required_jobs:
                assert f"{job}:" in template.content
