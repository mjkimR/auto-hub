import { useState } from 'react';
import { Alert, App, Button, Divider, Drawer, Form, Input, Modal, Select, Space, Switch, Typography } from 'antd';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createConnectorApiV1ConnectorsPost } from '../../../generated/api/sdk.gen';
import type { ConnectorRead, ProjectRead, ProjectWrite, TemplateRead } from '../../../generated/api/types.gen';
import { errorText, projectWrite } from '../helpers';

type EditorProps = {
  project: ProjectRead | null;
  connectors: ConnectorRead[];
  templates: TemplateRead[];
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onSave: (data: ProjectWrite) => void;
};

export function ProjectEditor({ project, connectors, templates, pending, error, onClose, onSave }: EditorProps) {
  const [form] = Form.useForm<ProjectWrite>();
  const [connectorForm] = Form.useForm<{ name: string; token: string }>();
  const [addConnector, setAddConnector] = useState(false);
  const templateId = Form.useWatch('template_id', form);
  const selectedTemplate = templates.find((template) => template.id === templateId);
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const connectorMutation = useMutation({
    mutationFn: (values: { name: string; token: string }) => createConnectorApiV1ConnectorsPost({
      body: { name: values.name, provider: 'github', credentials: { token: values.token } }, throwOnError: true,
    }),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries({ queryKey: ['projectConnectors'] });
      if (data) form.setFieldValue('github_connector_id', data.id);
      connectorForm.resetFields();
      setAddConnector(false);
      message.success('Connector saved');
    },
  });

  const downloadTemplate = () => {
    if (!selectedTemplate) return;
    const url = URL.createObjectURL(new Blob([selectedTemplate.content], { type: 'text/yaml' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = selectedTemplate.filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <Drawer title={project ? 'Edit project connection' : 'Connect a project'} open onClose={onClose} size={600}
      footer={<Space><Button onClick={onClose}>Cancel</Button><Button type="primary" loading={pending} onClick={() => form.submit()}>Save project</Button></Space>}>
      <Form form={form} layout="vertical" onFinish={onSave} initialValues={project ? projectWrite(project) : {
        enabled: true, verification: { workflow: 'ci.yml', required_jobs: ['lint', 'test'], event: 'pull_request' },
      }}>
        {error ? <Alert type="error" showIcon title={errorText(error)} style={{ marginBottom: 16 }} /> : null}
        <Typography.Paragraph type="secondary">Connect one GitHub repository. Run a connection check after saving.</Typography.Paragraph>
        <Form.Item name="name" label="Project name" rules={[{ required: true, whitespace: true }]}><Input placeholder="My application" /></Form.Item>
        <Form.Item name="repository" label="GitHub repository" rules={[{ required: true }, { pattern: /^[\w.-]+\/[\w.-]+$/, message: 'Use owner/repository' }]}><Input placeholder="owner/my-app" /></Form.Item>
        <Form.Item name="github_connector_id" label="GitHub connector" rules={[{ required: true }]}
          extra="Codex mentions are posted as this token's GitHub account, which must be linked to Codex.">
          <Select placeholder="Select a GitHub connector" options={connectors.filter((c) => c.provider === 'github' && c.enabled).map((c) => ({ value: c.id, label: c.name }))} />
        </Form.Item>
        <Button onClick={() => { connectorMutation.reset(); setAddConnector(true); }}>Add connector</Button>
        <Divider>CI setup</Divider>
        <Form.Item name="template_id" label="Starting point">
          <Select allowClear placeholder="Use existing CI" options={templates.map((t) => ({ value: t.id, label: `${t.name} · v${t.version}` }))}
            onChange={(id) => {
              const template = templates.find((t) => t.id === id);
              if (template) form.setFieldValue('verification', { workflow: template.filename, required_jobs: template.required_jobs, event: 'pull_request' });
            }} />
        </Form.Item>
        {selectedTemplate && <Alert type="info" showIcon style={{ marginBottom: 16 }} title={`${selectedTemplate.name} v${selectedTemplate.version}`}
          description={<Space orientation="vertical"><span>{selectedTemplate.changelog}</span><span>Download to .github/workflows/ci.yml, adapt the commands to your repository, then open a PR. Existing CI is not overwritten.</span><Button onClick={downloadTemplate}>Download ci.yml</Button></Space>} />}
        {selectedTemplate && project?.template_version && project.template_version !== selectedTemplate.version &&
          <Alert type="warning" title={`Saved template: v${project.template_version}. Saving selects v${selectedTemplate.version}; review the downloaded file before replacing your workflow.`} />}
        <Form.Item name={['verification', 'workflow']} label="Workflow filename" rules={[{ required: true }, { pattern: /^[\w-]+\.ya?ml$/, message: 'Use a YAML filename such as ci.yml' }]}>
          <Input placeholder="ci.yml" />
        </Form.Item>
        <Form.Item name={['verification', 'required_jobs']} label="Required job names" rules={[{ required: true, type: 'array', min: 1 }]}
          extra="Use the exact names shown in GitHub Actions. Missing or skipped jobs do not pass.">
          <Select mode="tags" tokenSeparators={[',']} placeholder="lint, test, build" />
        </Form.Item>
        <Form.Item name="enabled" label="Scheduled observation enabled" valuePropName="checked"><Switch /></Form.Item>
      </Form>
      <Modal title="Add GitHub connector" open={addConnector} onCancel={() => { setAddConnector(false); connectorForm.resetFields(); }}
        confirmLoading={connectorMutation.isPending} onOk={() => connectorForm.submit()} destroyOnHidden>
        <Form form={connectorForm} layout="vertical" onFinish={(values) => connectorMutation.mutate(values)}>
          {connectorMutation.error && <Alert type="error" title={errorText(connectorMutation.error)} />}
          <Form.Item name="name" label="Connector name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="token" label="Fine-grained personal access token" rules={[{ required: true }]}
            extra="Use the GitHub account linked to Codex. Repository access: Actions read, Contents read, Issues read, Pull requests read and write."><Input.Password autoComplete="new-password" /></Form.Item>
        </Form>
      </Modal>
    </Drawer>
  );
}
