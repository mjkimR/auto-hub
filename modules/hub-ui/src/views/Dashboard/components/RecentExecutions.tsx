import React from 'react';
import { Button, Table, Typography, Tooltip, Empty } from 'antd';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { formatDistanceToNow, parseISO } from 'date-fns';
import type { ScheduleJobRead } from '../../../generated/api/types.gen';

const { Title, Text } = Typography;

interface RecentExecutionsProps {
  jobs: ScheduleJobRead[];
  jobsLoading: boolean;
  onRefresh: () => void;
}

export const RecentExecutions: React.FC<RecentExecutionsProps> = ({
  jobs,
  jobsLoading,
  onRefresh,
}) => {
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
      render: (_: unknown, record: ScheduleJobRead) => {
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
      },
    },
  ];

  return (
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
          onClick={onRefresh}
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
  );
};
