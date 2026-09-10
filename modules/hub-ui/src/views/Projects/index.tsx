import { useState } from 'react';
import { Alert, App, Button, Card, Drawer, Empty, Form, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Typography } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FolderGit2, Plus, RefreshCw } from 'lucide-react';
import {
  checkProjectApiV1ProjectsProjectIdCheckPost, createProjectApiV1ProjectsPost,
  createScheduleConfigApiV1ScheduleConfigsPost, deleteProjectApiV1ProjectsProjectIdDelete,
  getConnectorsApiV1ConnectorsGet, getProjectTemplatesApiV1ProjectsTemplatesGet,
  getScheduleConfigsApiV1ScheduleConfigsGet, importProjectScheduleApiV1ProjectsImportSchedulePost,
  listProjectsApiV1ProjectsGet, updateProjectApiV1ProjectsProjectIdPut,
} from '../../generated/api/sdk.gen';
import type { ProjectRead, ProjectWrite } from '../../generated/api/types.gen';
import { ProjectEditor } from './components/ProjectEditor';
import { errorText } from './helpers';

export function Projects() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ project: ProjectRead | null } | null>(null);
  const [inspecting, setInspecting] = useState<ProjectRead | null>(null);
  const [pullNumber, setPullNumber] = useState<number | null>(null);
  const [importing, setImporting] = useState(false);
  const [legacyId, setLegacyId] = useState<string>();
  const [scheduling, setScheduling] = useState<ProjectRead | null>(null);
  const [scheduleForm] = Form.useForm<{ pull_numbers: string[]; interval_minutes: number }>();

  const projects = useQuery({ queryKey: ['projects', page], queryFn: () => listProjectsApiV1ProjectsGet({ query: { offset: (page - 1) * 20, limit: 20 }, throwOnError: true }) });
  const connectors = useQuery({ queryKey: ['projectConnectors'], queryFn: () => getConnectorsApiV1ConnectorsGet({ query: { limit: 100 }, throwOnError: true }) });
  const templates = useQuery({ queryKey: ['projectTemplates'], queryFn: () => getProjectTemplatesApiV1ProjectsTemplatesGet({ throwOnError: true }) });
  const legacy = useQuery({ queryKey: ['legacyObservations'], enabled: importing,
    queryFn: () => getScheduleConfigsApiV1ScheduleConfigsGet({ query: { task_func: 'pipeline.observe', limit: 100 }, throwOnError: true }) });

  const save = useMutation({
    mutationFn: (data: ProjectWrite) => editor?.project
      ? updateProjectApiV1ProjectsProjectIdPut({ path: { project_id: editor.project.id }, body: { ...data, expected_revision: editor.project.revision }, throwOnError: true })
      : createProjectApiV1ProjectsPost({ body: data, throwOnError: true }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['projects'] }); setEditor(null); message.success('Project connection saved'); },
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteProjectApiV1ProjectsProjectIdDelete({ path: { project_id: id }, throwOnError: true }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['projects'] }); message.success('Project connection deleted'); },
    onError: (error) => message.error(errorText(error)),
  });
  const check = useMutation({
    mutationFn: ({ id, pull }: { id: string; pull: number }) => checkProjectApiV1ProjectsProjectIdCheckPost({ path: { project_id: id }, body: { pull_number: pull }, throwOnError: true }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });
  const importSchedule = useMutation({
    mutationFn: (schedule_id: string) => importProjectScheduleApiV1ProjectsImportSchedulePost({ body: { schedule_id }, throwOnError: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({ queryKey: ['legacyObservations'] });
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
      setImporting(false); message.success('Schedule now uses its saved project connection');
    },
  });
  const createSchedule = useMutation({
    mutationFn: (values: { pull_numbers: string[]; interval_minutes: number }) => createScheduleConfigApiV1ScheduleConfigsPost({ body: {
      name: `${scheduling!.name} · CI observation`, task_func: 'pipeline.observe_project',
      interval_seconds: values.interval_minutes * 60,
      payload: { project_id: scheduling!.id, pull_numbers: values.pull_numbers.map(Number) }, enabled: true,
    }, throwOnError: true }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] }); setScheduling(null); message.success('Observation schedule created'); },
  });

  const report = check.data?.data ?? inspecting?.last_check;
  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div><Typography.Title level={3} style={{ margin: 0 }}><FolderGit2 size={24} /> Project connections</Typography.Title>
          <Typography.Paragraph type="secondary">One repository, one Linear project. Connect CI and verify a PR before scheduling observations.</Typography.Paragraph></div>
        <Space wrap>
          <Button icon={<RefreshCw size={16} />} onClick={() => projects.refetch()}>Refresh</Button>
          <Button onClick={() => { importSchedule.reset(); setLegacyId(undefined); setImporting(true); }}>Import legacy schedule</Button>
          <Button type="primary" icon={<Plus size={16} />} onClick={() => { save.reset(); setEditor({ project: null }); }}>Connect project</Button>
        </Space>
      </div>
      {(projects.error || connectors.error || templates.error) && <Alert type="error" showIcon title={errorText(projects.error || connectors.error || templates.error)} />}
      <Card styles={{ body: { padding: 0 } }}>
        <Table<ProjectRead> rowKey="id" loading={projects.isLoading} dataSource={projects.data?.data?.items || []} scroll={{ x: 900 }}
          locale={{ emptyText: <Empty description="No projects connected yet"><Button onClick={() => { save.reset(); setEditor({ project: null }); }}>Connect your first project</Button></Empty> }}
          pagination={{ current: page, pageSize: 20, total: projects.data?.data?.total_count || 0, showSizeChanger: false, onChange: setPage }} columns={[
            { title: 'Project', key: 'name', render: (_, p) => <Space orientation="vertical" size={0}><Typography.Text strong>{p.name}</Typography.Text><Typography.Link href={`https://github.com/${p.repository}`} target="_blank" rel="noopener noreferrer">{p.repository}</Typography.Link></Space> },
            { title: 'Verification', key: 'ci', render: (_, p) => <Space orientation="vertical" size={2}><span>{p.verification.workflow}</span><Space size={0} wrap>{p.verification.required_jobs.map((j) => <Tag key={j}>{j}</Tag>)}</Space></Space> },
            { title: 'Last connection check', key: 'check', render: (_, p) => <Space orientation="vertical" size={2}><Tag color={p.last_check?.ready ? 'green' : p.last_check ? 'orange' : 'default'}>{p.last_check?.ready ? 'Verified' : p.last_check ? 'Needs attention' : 'Not checked'}</Tag>{p.last_check && <Typography.Text type="secondary">{new Date(p.last_check.checked_at).toLocaleString()}</Typography.Text>}</Space> },
            { title: 'Observation', key: 'enabled', render: (_, p) => <Tag>{p.enabled ? 'Enabled' : 'Paused'}</Tag> },
            { title: 'Actions', key: 'actions', render: (_, p) => <Space wrap>
              <Button size="small" onClick={() => { save.reset(); setEditor({ project: p }); }}>Edit</Button>
              <Button size="small" onClick={() => { check.reset(); setPullNumber(null); setInspecting(p); }}>Check CI</Button>
              <Button size="small" disabled={!p.enabled} onClick={() => { createSchedule.reset(); scheduleForm.resetFields(); setScheduling(p); }}>Schedule</Button>
              <Popconfirm title="Delete this project connection?" description="Remove its observation schedules first. Repository and Linear data are kept." onConfirm={() => remove.mutate(p.id)}><Button size="small" danger loading={remove.isPending && remove.variables === p.id}>Delete</Button></Popconfirm>
            </Space> },
          ]} />
      </Card>
      {editor && <ProjectEditor project={editor.project} connectors={connectors.data?.data?.items || []} templates={templates.data?.data || []}
        pending={save.isPending} error={save.error} onSave={(data) => save.mutate(data)} onClose={() => setEditor(null)} />}
      <Drawer title={`Check connection · ${inspecting?.name || ''}`} size={650} open={!!inspecting} onClose={() => setInspecting(null)} destroyOnHidden>
        <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Paragraph>Choose an open PR in this repository. Hub reads the repository, workflow, required jobs and optional Linear project access.</Typography.Paragraph>
          <Space><InputNumber aria-label="PR number" min={1} precision={0} placeholder="PR number" value={pullNumber} onChange={setPullNumber} />
            <Button type="primary" loading={check.isPending} disabled={!pullNumber} onClick={() => inspecting && pullNumber && check.mutate({ id: inspecting.id, pull: pullNumber })}>Run connection check</Button></Space>
          {check.error && <Alert type="error" showIcon title={errorText(check.error)} />}
          {report && <>
            <Typography.Text type="secondary">Checked {new Date(report.checked_at).toLocaleString()}. This is a snapshot; it does not authorize a merge.</Typography.Text>
            {report.checks.map((item, i) => <Alert key={`${item.name}-${i}`} showIcon type={item.status === 'passed' ? 'success' : item.status === 'skipped' ? 'info' : 'warning'} title={item.name} description={item.detail} />)}
            {report.observation?.pulls.map((pull) => <Card key={pull.number} size="small" title={`PR #${pull.number} · ${pull.result.status}`}>
              <Typography.Paragraph>{pull.result.reason}</Typography.Paragraph>
              {!!pull.result.missing_jobs?.length && <Typography.Paragraph>Missing: {pull.result.missing_jobs.join(', ')}</Typography.Paragraph>}
              {!!pull.result.unsuccessful_jobs?.length && <Typography.Paragraph>Unsuccessful: {pull.result.unsuccessful_jobs.join(', ')}</Typography.Paragraph>}
              {pull.run && <Typography.Link href={pull.run.url} target="_blank" rel="noopener noreferrer">View GitHub Actions run</Typography.Link>}
            </Card>)}
          </>}
        </Space>
      </Drawer>
      <Modal title="Import an observation schedule" open={importing} onCancel={() => setImporting(false)} confirmLoading={importSchedule.isPending}
        okButtonProps={{ disabled: !legacyId }} onOk={() => legacyId && importSchedule.mutate(legacyId)}>
        <Typography.Paragraph>Move the connection settings into a project. The schedule keeps its PRs, timing, enabled state and history. Conflicting settings are left unchanged.</Typography.Paragraph>
        {(legacy.error || importSchedule.error) && <Alert type="error" title={errorText(legacy.error || importSchedule.error)} />}
        <Select style={{ width: '100%' }} placeholder="Select a legacy observation" loading={legacy.isLoading} value={legacyId} onChange={setLegacyId}
          options={(legacy.data?.data?.items || []).filter((s) => s.task_func === 'pipeline.observe').map((s) => ({ label: s.name, value: s.id }))} />
      </Modal>
      <Modal title={`Schedule observations · ${scheduling?.name || ''}`} open={!!scheduling} onCancel={() => setScheduling(null)}
        confirmLoading={createSchedule.isPending} onOk={() => scheduleForm.submit()} destroyOnHidden>
        {createSchedule.error && <Alert type="error" title={errorText(createSchedule.error)} />}
        <Form form={scheduleForm} layout="vertical" initialValues={{ interval_minutes: 5 }} onFinish={(values) => createSchedule.mutate(values)}>
          <Form.Item name="pull_numbers" label="PR numbers" rules={[{ required: true, type: 'array', min: 1, max: 10 }, { validator: (_, values: string[]) => !values || values.every((v) => /^[1-9]\d*$/.test(v)) ? Promise.resolve() : Promise.reject(new Error('Enter positive PR numbers')) }]}><Select mode="tags" tokenSeparators={[',']} /></Form.Item>
          <Form.Item name="interval_minutes" label="Interval (minutes)" rules={[{ required: true }]}><InputNumber min={1} precision={0} /></Form.Item>
          <Typography.Paragraph type="secondary">Observations run when the Hub dispatcher is triggered and the schedule is due. Manage timing in Schedules.</Typography.Paragraph>
        </Form>
      </Modal>
    </Space>
  );
}
