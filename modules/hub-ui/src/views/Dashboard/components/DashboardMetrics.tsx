import React from 'react';
import { Row, Col, Space, Typography } from 'antd';
import { Calendar, Clock, CheckCircle2, Activity } from 'lucide-react';
import type { ScheduleJobRead } from '../../../generated/api/types.gen';

const { Title, Text } = Typography;

interface DashboardMetricsProps {
  configsLoading: boolean;
  jobsLoading: boolean;
  totalSchedules: number;
  activeSchedules: number;
  successRate: number;
  failedJobs: number;
  lastJob: ScheduleJobRead | undefined;
  lastDispatchedStr: string;
}

export const DashboardMetrics: React.FC<DashboardMetricsProps> = ({
  configsLoading,
  jobsLoading,
  totalSchedules,
  activeSchedules,
  successRate,
  failedJobs,
  lastJob,
  lastDispatchedStr,
}) => {
  const metrics = [
    {
      title: 'Total Schedule Configs',
      value: configsLoading ? '...' : totalSchedules,
      desc: `${activeSchedules} Active schedules`,
      icon: <Calendar size={24} color="#1677ff" />,
      glowColor: 'rgba(22, 119, 255, 0.15)',
    },
    {
      title: 'Active Runs Rate',
      value: configsLoading ? '...' : `${totalSchedules > 0 ? Math.round((activeSchedules / totalSchedules) * 100) : 0}%`,
      desc: 'Schedules currently online',
      icon: <Clock size={24} color="#52c41a" />,
      glowColor: 'rgba(82, 196, 26, 0.15)',
    },
    {
      title: 'Execution Success Rate',
      value: jobsLoading ? '...' : `${successRate}%`,
      desc: `${failedJobs} Failures recorded`,
      icon: <CheckCircle2 size={24} color="#eb2f96" />,
      glowColor: 'rgba(235, 47, 150, 0.15)',
    },
    {
      title: 'Last Dispatch Occurred',
      value: jobsLoading ? '...' : lastJob ? 'Active' : 'Idle',
      desc: lastDispatchedStr,
      icon: <Activity size={24} color="#faad14" />,
      glowColor: 'rgba(250, 173, 20, 0.15)',
    },
  ];

  return (
    <Row gutter={[24, 24]}>
      {metrics.map((m, idx) => (
        <Col xs={24} sm={12} xl={6} key={idx}>
          <div
            className="glass-panel glass-panel-hover"
            style={{
              padding: '24px',
              position: 'relative',
              overflow: 'hidden',
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
                filter: 'blur(30px)',
              }}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Space orientation="vertical" size={2}>
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
                  border: '1px solid var(--border-color)',
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
  );
};
