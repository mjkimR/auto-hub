import { Row, Col, Space, Button, Table, Typography, App as AntdApp, Tooltip, Empty, List } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getScheduleConfigsApiV1ScheduleConfigsGet,
  getScheduleJobsApiV1ScheduleJobsGet,
  triggerDispatchApiV1DispatchersTriggerPost,
  getSystemConfigsApiV1SystemConfigsGet
} from '../generated/api/sdk.gen';
import { useThemeStore } from '../store/themeStore';
import { 
  Calendar, 
  Activity, 
  CheckCircle2, 
  AlertCircle, 
  Play, 
  RefreshCw,
  Clock,
  Settings,
  HelpCircle
} from 'lucide-react';
import { formatDistanceToNow, parseISO } from 'date-fns';

const { Title, Text, Paragraph } = Typography;

export const Dashboard: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const { triggerLoading, setTriggerLoading } = useThemeStore();

  // 1. Fetch Schedule Configs
  const { data: configsData, isLoading: configsLoading } = useQuery({
    queryKey: ['scheduleConfigs'],
    queryFn: () => getScheduleConfigsApiV1ScheduleConfigsGet({ throwOnError: true }),
  });

  // 2. Fetch Recent Schedule Jobs
  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['scheduleJobs'],
    queryFn: () => getScheduleJobsApiV1ScheduleJobsGet({ throwOnError: true }),
  });

  // 3. Fetch System Configs
  const { data: systemConfigsData } = useQuery({
    queryKey: ['systemConfigs'],
    queryFn: () => getSystemConfigsApiV1SystemConfigsGet({ throwOnError: true }),
  });

  // 4. Manual Trigger Dispatch Mutation
  const triggerMutation = useMutation({
    mutationFn: () => triggerDispatchApiV1DispatchersTriggerPost({ throwOnError: true }),
    onMutate: () => {
      setTriggerLoading(true);
    },
    onSuccess: (res: any) => {
      const dispatchedCount = res.data?.dispatched ?? 0;
      message.success(`Dispatcher triggered successfully! Dispatched ${dispatchedCount} jobs.`);
      queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] });
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
    },
    onError: (err: any) => {
      message.error(`Trigger failed: ${err.message || 'Unknown error'}`);
    },
    onSettled: () => {
      setTriggerLoading(false);
    }
  });

  // Compute Metrics
  const schedules = configsData?.data?.items || [];
  const totalSchedules = schedules.length;
  const activeSchedules = schedules.filter((s: any) => s.enabled).length;

  const jobs = jobsData?.data?.items || [];
  const totalJobsRun = jobs.length;
  const successfulJobs = jobs.filter((j: any) => j.status === 'success').length;
  const failedJobs = jobs.filter((j: any) => j.status === 'failure').length;
  const successRate = totalJobsRun > 0 ? Math.round((successfulJobs / totalJobsRun) * 100) : 100;

  const lastJob = jobs[0];
  const lastDispatchedStr = lastJob?.started_at 
    ? `${formatDistanceToNow(parseISO(lastJob.started_at), { addSuffix: true })}` 
    : 'No runs yet';

  // KPI cards schema
  const metrics = [
    {
      title: 'Total Schedule Configs',
      value: configsLoading ? '...' : totalSchedules,
      desc: `${activeSchedules} Active schedules`,
      icon: <Calendar size={24} color="#1677ff" />,
      glowColor: 'rgba(22, 119, 255, 0.15)'
    },
    {
      title: 'Active Runs Rate',
      value: configsLoading ? '...' : `${totalSchedules > 0 ? Math.round((activeSchedules / totalSchedules) * 100) : 0}%`,
      desc: 'Schedules currently online',
      icon: <Clock size={24} color="#52c41a" />,
      glowColor: 'rgba(82, 196, 26, 0.15)'
    },
    {
      title: 'Execution Success Rate',
      value: jobsLoading ? '...' : `${successRate}%`,
      desc: `${failedJobs} Failures recorded`,
      icon: <CheckCircle2 size={24} color="#eb2f96" />,
      glowColor: 'rgba(235, 47, 150, 0.15)'
    },
    {
      title: 'Last Dispatch Occurred',
      value: jobsLoading ? '...' : lastJob ? 'Active' : 'Idle',
      desc: lastDispatchedStr,
      icon: <Activity size={24} color="#faad14" />,
      glowColor: 'rgba(250, 173, 20, 0.15)'
    }
  ];

  // Jobs table columns for recent runs
  const jobColumns = [
    {
      title: 'Job Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Text style={{ fontWeight: 600 }}>{text}</Text>,
    },
    {
      title: 'Status',
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
          <span className={`glass-status-badge ${badgeClass}`}>
            {displayText}
          </span>
        );
      },
    },
    {
      title: 'Executed At',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (dateStr: string) => {
        try {
          return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
        } catch {
          return dateStr;
        }
      },
    },
    {
      title: 'Details',
      key: 'details',
      render: (_: any, record: any) => {
        if (record.status === 'failure') {
          return (
            <Tooltip title={record.error_message || 'Unknown failure error'}>
              <span style={{ color: '#ff4d4f', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertCircle size={14} /> Error Info
              </span>
            </Tooltip>
          );
        }
        return <span style={{ color: 'var(--text-muted)' }}>-</span>;
      }
    }
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 1. KPIs Row */}
      <Row gutter={[24, 24]}>
        {metrics.map((m, idx) => (
          <Col xs={24} sm={12} xl={6} key={idx}>
            <div 
              className="glass-panel glass-panel-hover" 
              style={{ 
                padding: '24px', 
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              {/* Backglow element */}
              <div 
                style={{ 
                  position: 'absolute', 
                  right: '-10px', 
                  bottom: '-10px', 
                  width: '60px', 
                  height: '60px', 
                  borderRadius: '50%',
                  background: m.glowColor, 
                  filter: 'blur(30px)' 
                }} 
              />
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <Space direction="vertical" size={2}>
                  <Text className="font-outfit" style={{ color: 'var(--text-muted)', fontSize: '13px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {m.title}
                  </Text>
                  <Title className="font-outfit" level={2} style={{ margin: 0, fontWeight: 800, fontSize: '32px' }}>
                    {m.value}
                  </Title>
                </Space>
                <div 
                  style={{ 
                    padding: '12px', 
                    borderRadius: '12px', 
                    background: 'rgba(0,0,0,0.02)',
                    border: '1px solid var(--border-color)' 
                  }}
                >
                  {m.icon}
                </div>
              </div>
              <div style={{ marginTop: '16px' }}>
                <Text style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  {m.desc}
                </Text>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      {/* 2. Dispatcher Console & Recent Runs */}
      <Row gutter={[24, 24]}>
        {/* Left Side: Dispatcher Control Board */}
        <Col xs={24} lg={10}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* Control panel card */}
            <div className="glass-panel" style={{ padding: '28px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <Title level={4} style={{ margin: 0 }} className="font-outfit">
                  Manual Dispatch Console
                </Title>
                <Tooltip title="This manual trigger scans all schedule configs, checks their execution windows, and dispatches due jobs using safe FOR UPDATE SKIP LOCKED concurrency.">
                  <HelpCircle size={16} style={{ color: 'var(--text-muted)', cursor: 'pointer' }} />
                </Tooltip>
              </div>
              
              <Paragraph style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
                Manually wake up the backend dispatcher scheduler to execute any pending schedules immediately. Perfect for local debugging or forcing ad-hoc runs.
              </Paragraph>
              
              <div 
                style={{ 
                  background: 'rgba(0,0,0,0.02)', 
                  border: '1px solid var(--border-color)', 
                  borderRadius: '12px', 
                  padding: '20px', 
                  marginBottom: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px'
                }}
              >
                <div style={{ background: 'var(--accent-glow)', padding: '10px', borderRadius: '10px' }}>
                  <Play size={20} color="var(--accent-primary)" />
                </div>
                <div>
                  <Text strong style={{ fontSize: '14px', display: 'block' }}>Trigger Dispatched Schedules</Text>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    Process pending configurations concurrently.
                  </Text>
                </div>
              </div>

              <Button
                type="primary"
                size="large"
                icon={<RefreshCw size={16} className={triggerLoading ? 'glow-active' : ''} />}
                loading={triggerLoading}
                onClick={() => triggerMutation.mutate()}
                style={{
                  width: '100%',
                  height: '48px',
                  borderRadius: '10px',
                  fontWeight: 600,
                  fontSize: '15px',
                  background: 'var(--accent-gradient)',
                  border: 0,
                  boxShadow: '0 4px 14px var(--accent-glow)'
                }}
                className="hover-glow"
              >
                {triggerLoading ? 'Processing Dispatch...' : 'Trigger Dispatcher Now'}
              </Button>
            </div>

            {/* Quick System Summary Card */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Settings size={18} style={{ color: 'var(--accent-primary)' }} />
                <Title level={5} style={{ margin: 0 }} className="font-outfit">Active System Parameters</Title>
              </div>
              <List
                size="small"
                dataSource={systemConfigsData?.data?.items?.slice(0, 3) || []}
                renderItem={(item: any) => (
                  <List.Item style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <Text strong>{item.name}</Text>
                    <Text code>{JSON.stringify(item.data)}</Text>
                  </List.Item>
                )}
                locale={{ emptyText: <Empty description="No system configs registered" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
              />
            </div>
          </Space>
        </Col>

        {/* Right Side: Recent Execution Histories */}
        <Col xs={24} lg={14}>
          <div className="glass-panel" style={{ padding: '28px', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <Title level={4} style={{ margin: 0 }} className="font-outfit">
                  Recent Executions Log
                </Title>
                <Text type="secondary" style={{ fontSize: '13px' }}>
                  Latest dispatcher execution runs and outputs.
                </Text>
              </div>
              <Button 
                size="small" 
                icon={<RefreshCw size={14} />} 
                onClick={() => queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] })}
              >
                Refresh
              </Button>
            </div>
            
            <Table
              columns={jobColumns}
              dataSource={jobs.slice(0, 6)}
              rowKey="id"
              pagination={false}
              loading={jobsLoading}
              locale={{ emptyText: <Empty description="No executions recorded yet" /> }}
              className="glass-table"
              style={{ background: 'transparent' }}
            />
          </div>
        </Col>
      </Row>
    </Space>
  );
};
