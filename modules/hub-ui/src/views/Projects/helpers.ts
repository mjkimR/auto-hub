import type { ProjectRead, ProjectWrite } from '../../generated/api/types.gen';

export function errorText(error: unknown): string {
  if (error && typeof error === 'object') {
    const value = error as { detail?: unknown; message?: string };
    if (typeof value.detail === 'string') return value.detail;
    if (Array.isArray(value.detail)) return value.detail.map((item: { msg?: string }) => item.msg || 'Invalid value').join('; ');
    if (value.message) return value.message;
  }
  return 'Request failed. Check the connection and try again.';
}

export function projectWrite(project: ProjectRead): ProjectWrite {
  return {
    name: project.name, repository: project.repository, linear_project_id: project.linear_project_id,
    github_connector_id: project.github_connector_id, linear_connector_id: project.linear_connector_id,
    verification: project.verification, enabled: project.enabled, template_id: project.template_id,
  };
}
