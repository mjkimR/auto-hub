import React from 'react';
import { Table, Button, Space, Typography, Tooltip, Popconfirm } from 'antd';
import { Trash2, AlertTriangle, Eye } from 'lucide-react';
import dayjs from 'dayjs';

const { Text } = Typography;

export interface ScheduleJobRecord {
  id: string;
  name: string;
  status: 'success' | 'failure' | 'pending';
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
  payload?: Record<string, unknown> | null;
}

interface JobTableProps {
  filteredJobs: ScheduleJobRecord[];
  isLoading: boolean;
  totalCount: number;
  page: number;
  pageSize: number;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  setPage: (val: number) => void;
  setPageSize: (val: number) => void;
  setSortField: (val: string) => void;
  setSortOrder: (val: 'ascend' | 'descend') => void;
  confirmedFilter: string;
  setCurrentInput: (val: string) => void;
  onOpenDetail: (record: ScheduleJobRecord) => void;
  onDelete: (id: string) => void;
}

export const JobTable: React.FC<JobTableProps> = ({
  filteredJobs,
  isLoading,
  totalCount,
  page,
  pageSize,
  sortField,
  sortOrder,
  setPage,
  setPageSize,
  setSortField,
  setSortOrder,
  confirmedFilter,
  setCurrentInput,
  onOpenDetail,
  onDelete,
}) => {
  const columns = [
    {
      title: 'Job Name / ID',
      dataIndex: 'name',
      key: 'name',
      sorter: true,
      sortOrder: sortField === 'name' ? sortOrder : undefined,
      render: (text: string, record: ScheduleJobRecord) => (
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
      sorter: true,
      sortOrder: sortField === 'status' ? sortOrder : undefined,
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
      title: 'Triggered At',
      dataIndex: 'started_at',
      key: 'started_at',
      sorter: true,
      sortOrder: sortField === 'started_at' ? sortOrder : undefined,
      render: (dateStr: string) => dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: 'Duration',
      key: 'duration',
      render: (_: unknown, record: ScheduleJobRecord) => {
        if (!record.finished_at) return <Text type="secondary">Processing...</Text>;
        const start = dayjs(record.started_at);
        const end = dayjs(record.finished_at);
        const diffMs = end.diff(start);
        if (diffMs < 1000) {
          return `${diffMs}ms`;
        }
        const seconds = (diffMs / 1000).toFixed(2);
        return `${seconds}s`;
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ScheduleJobRecord) => (
        <Space size="middle">
          <Tooltip title="View Detailed Log Console">
            <Button
              size="small"
              type="text"
              icon={<Eye size={14} />}
              onClick={() => onOpenDetail(record)}
            />
          </Tooltip>

          <Popconfirm
            title="Delete this execution log?"
            description="This will wipe the execution history from the database permanently."
            icon={<AlertTriangle style={{ color: '#ff4d4f' }} size={16} />}
            onConfirm={() => onDelete(record.id)}
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
    <div className="glass-panel" style={{ padding: '24px' }}>
      <Table
        columns={columns}
        dataSource={filteredJobs}
        rowKey="id"
        loading={isLoading}
        className="glass-table"
        onChange={(pagination, _filters, sorter: unknown) => {
          setCurrentInput(confirmedFilter);
          if (pagination) {
            setPage(pagination.current || 1);
            setPageSize(pagination.pageSize || 10);
          }
          const s = sorter as { field?: string; order?: 'ascend' | 'descend' };
          if (s && s.field) {
            setSortField(s.field);
            setSortOrder(s.order || 'descend');
          }
        }}
        pagination={{
          current: page,
          pageSize: pageSize,
          total: totalCount,
          showSizeChanger: true,
        }}
      />
    </div>
  );
};
