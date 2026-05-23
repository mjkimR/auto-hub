import React, { useState } from 'react';
import { 
  Table, Button, Space, Input, Drawer, Typography, 
  App as AntdApp, Tooltip, Popconfirm, Select, Divider 
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getScheduleJobsApiV1ScheduleJobsGet,
  deleteScheduleJobApiV1ScheduleJobsScheduleJobIdDelete
} from '../generated/api/sdk.gen';
import { 
  Search, Trash2, AlertTriangle, RefreshCw, Clock, 
  Terminal, Eye, ShieldAlert 
} from 'lucide-react';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';

dayjs.extend(duration);
const { Title, Text } = Typography;
const { Option } = Select;

export const ScheduleJobs: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [isDrawerVisible, setIsDrawerVisible] = useState(false);

  // 1. Fetch Execution Jobs
  const { data: jobsData, isLoading, refetch } = useQuery({
    queryKey: ['scheduleJobs'],
    queryFn: () => getScheduleJobsApiV1ScheduleJobsGet({ throwOnError: true }),
  });

  // 2. Delete Job Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => 
      deleteScheduleJobApiV1ScheduleJobsScheduleJobIdDelete({ 
        path: { schedule_job_id: id }, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('Job log deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] });
      if (selectedJob && selectedJob.id) {
        setIsDrawerVisible(false);
      }
    },
    onError: (err: any) => {
      message.error(`Delete failed: ${err.message}`);
    }
  });

  const handleOpenDetail = (record: any) => {
    setSelectedJob(record);
    setIsDrawerVisible(true);
  };

  const jobs = jobsData?.data?.items || [];
  
  // Filter jobs based on search term & status select
  const filteredJobs = jobs.filter((job: any) => {
    const matchesSearch = job.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (job.error_message && job.error_message.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesStatus = statusFilter === 'all' ? true : job.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const columns = [
    {
      title: 'Job Name / ID',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Space direction="vertical" size={2}>
          <Text strong style={{ fontSize: '14px' }}>{text}</Text>
          <Text type="secondary" style={{ fontSize: '10px', fontFamily: 'monospace' }}>ID: {record.id}</Text>
        </Space>
      ),
    },
    {
      title: 'Execution Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        let badgeClass = 'pending';
        let displayText = 'Pending';
        if (status === 'success') {
          badgeClass = 'success';
          displayText = 'Success';
        } else if (status === 'failure') {
          badgeClass = 'failure';
          displayText = 'Failure';
        }
        return (
          <span className={`premium-status-badge ${badgeClass}`}>
            {displayText}
          </span>
        );
      },
    },
    {
      title: 'Triggered At',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (dateStr: string) => dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: any, record: any) => {
        if (!record.finished_at) return <Text type="secondary">Processing...</Text>;
        const start = dayjs(record.started_at);
        const end = dayjs(record.finished_at);
        const diffMs = end.diff(start);
        if (diffMs < 1000) {
          return `${diffMs}ms`;
        }
        const seconds = (diffMs / 1000).toFixed(2);
        return `${seconds}s`;
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space size="middle">
          <Tooltip title="View Detailed Log Console">
            <Button 
              size="small" 
              type="text" 
              icon={<Eye size={14} />} 
              onClick={() => handleOpenDetail(record)} 
            />
          </Tooltip>

          <Popconfirm
            title="Delete this execution log?"
            description="This will wipe the execution history from the database permanently."
            icon={<AlertTriangle style={{ color: '#ff4d4f' }} size={16} />}
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="Yes, Wipe"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="Wipe Log">
              <Button 
                size="small" 
                type="text" 
                danger 
                icon={<Trash2 size={14} />} 
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Filters and Actions Bar */}
      <div 
        className="glass-panel" 
        style={{ 
          padding: '24px', 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          flexWrap: 'wrap', 
          gap: '16px' 
        }}
      >
        <Space size="middle" style={{ flexWrap: 'wrap' }}>
          <Input
            prefix={<Search size={16} style={{ color: 'var(--text-muted)' }} />}
            placeholder="Search executions by job name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '280px',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              background: 'rgba(0,0,0,0.01)'
            }}
          />

          <Select
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
            style={{ width: '150px' }}
            dropdownStyle={{ backdropFilter: 'blur(10px)' }}
          >
            <Option value="all">All Statuses</Option>
            <Option value="success">Success Only</Option>
            <Option value="failure">Failure Only</Option>
            <Option value="pending">Pending Only</Option>
          </Select>
        </Space>

        <Button icon={<RefreshCw size={14} />} onClick={() => refetch()}>
          Refresh Log Feed
        </Button>
      </div>

      {/* Execution Jobs Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <Table 
          columns={columns} 
          dataSource={filteredJobs} 
          rowKey="id" 
          loading={isLoading} 
          className="premium-table"
        />
      </div>

      {/* Detailed Log Console Drawer */}
      <Drawer
        title="Execution Diagnostics Terminal"
        width={600}
        onClose={() => setIsDrawerVisible(false)}
        open={isDrawerVisible}
        style={{ backdropFilter: 'blur(10px)' }}
      >
        {selectedJob && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* Header info */}
            <div>
              <Title level={4} style={{ margin: 0 }} className="font-outfit">
                {selectedJob.name}
              </Title>
              <Text type="secondary" style={{ fontSize: '12px', fontFamily: 'monospace' }}>
                Job ID: {selectedJob.id}
              </Text>
            </div>

            {/* Status indicators */}
            <div 
              style={{ 
                display: 'flex', 
                gap: '12px', 
                flexWrap: 'wrap',
                padding: '16px',
                background: 'rgba(0,0,0,0.02)',
                border: '1px solid var(--border-color)',
                borderRadius: '12px'
              }}
            >
              <div>
                <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>STATUS</Text>
                <span className={`premium-status-badge ${selectedJob.status === 'success' ? 'success' : selectedJob.status === 'failure' ? 'failure' : 'pending'}`} style={{ marginTop: '4px' }}>
                  {selectedJob.status.toUpperCase()}
                </span>
              </div>
              <Divider type="vertical" style={{ height: '40px' }} />
              <div>
                <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>TRIGGERED TIME</Text>
                <Text strong style={{ fontSize: '13px' }}>
                  {dayjs(selectedJob.started_at).format('YYYY-MM-DD HH:mm:ss')}
                </Text>
              </div>
              <Divider type="vertical" style={{ height: '40px' }} />
              <div>
                <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>FINISHED TIME</Text>
                <Text strong style={{ fontSize: '13px' }}>
                  {selectedJob.finished_at ? dayjs(selectedJob.finished_at).format('YYYY-MM-DD HH:mm:ss') : 'Processing'}
                </Text>
              </div>
            </div>

            {/* Error Message Traceback Box */}
            {selectedJob.status === 'failure' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <ShieldAlert size={16} color="#ff4d4f" />
                  <Text strong style={{ color: '#ff4d4f' }}>Diagnostics & Traceback Exception</Text>
                </div>
                {/* Visual Terminal Block */}
                <div 
                  style={{ 
                    background: '#0d1117', 
                    borderRadius: '10px', 
                    border: '1px solid rgba(255, 77, 79, 0.2)', 
                    padding: '20px', 
                    fontFamily: 'monospace',
                    color: '#ff7b72',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    boxShadow: 'inset 0 0 10px rgba(0,0,0,0.8)'
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', color: '#8b949e', marginBottom: '12px', borderBottom: '1px solid #21262d', paddingBottom: '8px' }}>
                    <Terminal size={14} />
                    <span>stderr Exception Log</span>
                  </div>
                  {selectedJob.error_message || 'Backend exception was triggered, but failed to pipe stdout error messages.'}
                </div>
              </div>
            )}

            {/* Input payload snapshot explorer */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Clock size={16} style={{ color: 'var(--accent-primary)' }} />
                <Text strong>Task Payload Snapshot Arguments</Text>
              </div>
              <pre 
                style={{ 
                  background: 'rgba(0,0,0,0.03)', 
                  border: '1px solid var(--border-color)', 
                  borderRadius: '10px', 
                  padding: '16px', 
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  overflowX: 'auto'
                }}
              >
                {selectedJob.payload ? JSON.stringify(selectedJob.payload, null, 2) : 'No payload arguments were passed to this run.'}
              </pre>
            </div>

            {/* Dangerous Area */}
            <Divider style={{ margin: '16px 0' }} />
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Popconfirm
                title="Wipe this individual record?"
                onConfirm={() => deleteMutation.mutate(selectedJob.id)}
                okText="Yes, Wipe"
                cancelText="Cancel"
                okButtonProps={{ danger: true }}
              >
                <Button danger type="dashed" icon={<Trash2 size={14} />}>
                  Wipe Execution Log File
                </Button>
              </Popconfirm>
            </div>
          </Space>
        )}
      </Drawer>
    </Space>
  );
};
