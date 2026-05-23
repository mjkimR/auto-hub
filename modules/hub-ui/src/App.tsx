import React, { useState } from 'react';
import {
  ConfigProvider,
  theme,
  Layout,
  Typography,
  Space,
  Card,
  Table,
  Badge,
  Button,
  App as AntdApp,
  Row,
  Col,
} from 'antd';
import Form from '@rjsf/antd';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';
import { Play, Pause, Trash2 } from 'lucide-react';

const { Header, Content, Footer } = Layout;
const { Title, Text } = Typography;

// Mock job list
interface Job {
  key: string;
  name: string;
  cronExpression: string;
  enabled: boolean;
  maxRetries: number;
}

const initialJobs: Job[] = [
  { key: '1', name: 'Database Backup', cronExpression: '0 2 * * *', enabled: true, maxRetries: 3 },
  { key: '2', name: 'Telemetry Cleanup', cronExpression: '0 0 * * 0', enabled: false, maxRetries: 1 },
  { key: '3', name: 'Notification Dispatcher', cronExpression: '*/5 * * * *', enabled: true, maxRetries: 5 },
];

// RJSF Form Schema for creating jobs
const schema: RJSFSchema = {
  title: 'Create Scheduled Job',
  type: 'object',
  required: ['name', 'cronExpression'],
  properties: {
    name: {
      type: 'string',
      title: 'Job Name',
      minLength: 3,
    },
    cronExpression: {
      type: 'string',
      title: 'Cron Expression',
      default: '*/5 * * * *',
    },
    enabled: {
      type: 'boolean',
      title: 'Enabled',
      default: true,
    },
    maxRetries: {
      type: 'integer',
      title: 'Max Retries',
      minimum: 0,
      maximum: 10,
      default: 3,
    },
  },
};

const uiSchema: UiSchema = {
  cronExpression: {
    'ui:placeholder': 'e.g. 0 0 * * *',
  },
  maxRetries: {
    'ui:widget': 'updown',
  },
};

const MainDashboard: React.FC = () => {
  const { message } = AntdApp.useApp();
  const [jobs, setJobs] = useState<Job[]>(initialJobs);

  const columns = [
    {
      title: 'Job Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: 'Cron Expression',
      dataIndex: 'cronExpression',
      key: 'cronExpression',
      render: (text: string) => <code style={{ color: '#096dd9' }}>{text}</code>,
    },
    {
      title: 'Status',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => (
        <Badge
          status={enabled ? 'success' : 'default'}
          text={enabled ? 'Active' : 'Paused'}
        />
      ),
    },
    {
      title: 'Max Retries',
      dataIndex: 'maxRetries',
      key: 'maxRetries',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: Job) => (
        <Space size="middle">
          <Button
            size="small"
            icon={record.enabled ? <Pause size={14} /> : <Play size={14} />}
            onClick={() => handleToggle(record.key)}
          >
            {record.enabled ? 'Pause' : 'Resume'}
          </Button>
          <Button
            size="small"
            danger
            icon={<Trash2 size={14} />}
            onClick={() => handleDelete(record.key)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  const handleToggle = (key: string) => {
    setJobs(prev =>
      prev.map(job => (job.key === key ? { ...job, enabled: !job.enabled } : job))
    );
    message.info('Job status updated');
  };

  const handleDelete = (key: string) => {
    setJobs(prev => prev.filter(job => job.key !== key));
    message.success('Job deleted successfully');
  };

  const handleCreateJob = (data: { formData?: { name: string; cronExpression: string; enabled?: boolean; maxRetries?: number } }) => {
    const formData = data.formData;
    if (!formData) return;
    const newJob: Job = {
      key: String(Date.now()),
      name: formData.name,
      cronExpression: formData.cronExpression,
      enabled: formData.enabled ?? true,
      maxRetries: formData.maxRetries ?? 3,
    };
    setJobs(prev => [...prev, newJob]);
    message.success(`Job "${formData.name}" scheduled!`);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <Title level={3} style={{ color: '#fff', margin: 0 }}>
          Scheduler Manager Hub
        </Title>
      </Header>

      <Content style={{ padding: '32px 50px', background: '#f5f7fa' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <Row gutter={[24, 24]}>
            {/* Left side - Jobs list */}
            <Col xs={24} lg={16}>
              <Card title="Active Scheduled Jobs" bordered={false}>
                <Table columns={columns} dataSource={jobs} pagination={false} />
              </Card>
            </Col>

            {/* Right side - Create form */}
            <Col xs={24} lg={8}>
              <Card title="Register New Job" bordered={false}>
                <Form
                  schema={schema}
                  uiSchema={uiSchema}
                  validator={validator}
                  onSubmit={handleCreateJob}
                />
              </Card>
            </Col>
          </Row>
        </div>
      </Content>

      <Footer style={{ textAlign: 'center', color: '#8c8c8c' }}>
        Scheduler Manager Hub ©{new Date().getFullYear()} Created with React & Ant Design v6
      </Footer>
    </Layout>
  );
};

export default function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 6,
          fontFamily: 'Inter, system-ui, sans-serif',
        },
        algorithm: theme.defaultAlgorithm,
      }}
    >
      <AntdApp>
        <MainDashboard />
      </AntdApp>
    </ConfigProvider>
  );
}
