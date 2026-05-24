import React from 'react';
import { Table, Button, Switch, Space, Typography, Tooltip, Popconfirm } from 'antd';
import type { SorterResult } from 'antd/es/table/interface';
import { Calendar, Clock, Edit3, Trash2, AlertTriangle } from 'lucide-react';
import dayjs from 'dayjs';

const { Text } = Typography;

export interface ScheduleConfigRecord {
  id: string;
  name: string;
  description?: string;
  task_func: string;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  enabled: boolean;
  next_run_at?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  payload?: Record<string, unknown> | null;
}

interface ScheduleTableProps {
  filteredConfigs: ScheduleConfigRecord[];
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
  toggleEnabled: (id: string, enabled: boolean) => void;
  deleteConfig: (id: string) => void;
  handleOpenEdit: (record: ScheduleConfigRecord) => void;
}

export const ScheduleTable: React.FC<ScheduleTableProps> = ({
  filteredConfigs,
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
  toggleEnabled,
  deleteConfig,
  handleOpenEdit,
}) => {
  const columns = [
    {
      title: 'Schedule Name',
      dataIndex: 'name',
      key: 'name',
      sorter: true,
      sortOrder: sortField === 'name' ? sortOrder : undefined,
      render: (text: string, record: ScheduleConfigRecord) => (
        <Space orientation="vertical" size={2}>
          <Text strong style={{ fontSize: '14px' }}>{text}</Text>
          <Text type="secondary" style={{ fontSize: '11px' }}>{record.description || 'No description'}</Text>
        </Space>
      ),
    },
    {
      title: 'Task Path',
      dataIndex: 'task_func',
      key: 'task_func',
      sorter: true,
      sortOrder: sortField === 'task_func' ? sortOrder : undefined,
      render: (text: string) => <code style={{ color: 'var(--accent-primary)', fontSize: '12px' }}>{text}</code>,
    },
    {
      title: 'Trigger Rule',
      key: 'rule',
      render: (_: unknown, record: ScheduleConfigRecord) => {
        if (record.cron_expression) {
          return (
            <Space size={4}>
              <Calendar size={14} style={{ color: 'var(--text-secondary)' }} />
              <code style={{ fontSize: '12px' }}>{record.cron_expression}</code>
            </Space>
          );
        }
        return (
          <Space size={4}>
            <Clock size={14} style={{ color: 'var(--text-secondary)' }} />
            <span>Every {record.interval_seconds}s</span>
          </Space>
        );
      },
    },
    {
      title: 'Active State',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean, record: ScheduleConfigRecord) => (
        <Switch
          checked={enabled}
          onChange={(checked) => toggleEnabled(record.id, checked)}
        />
      ),
    },
    {
      title: 'Next Run',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      sorter: true,
      sortOrder: sortField === 'next_run_at' ? sortOrder : undefined,
      render: (dateStr: string | null | undefined) => {
        if (!dateStr) return <Text type="secondary">-</Text>;
        try {
          return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss');
        } catch {
          return dateStr;
        }
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ScheduleConfigRecord) => (
        <Space size="middle">
          <Tooltip title="Edit Schedule Configuration">
            <Button
              size="small"
              type="text"
              icon={<Edit3 size={14} />}
              onClick={() => handleOpenEdit(record)}
            />
          </Tooltip>

          <Popconfirm
            title="Delete this Schedule Configuration?"
            description="All subsequent execution logs and pending timers will be discarded."
            icon={<AlertTriangle style={{ color: '#ff4d4f' }} size={16} />}
            onConfirm={() => deleteConfig(record.id)}
            okText="Yes, Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="Delete Schedule">
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
        dataSource={filteredConfigs}
        rowKey="id"
        loading={isLoading}
        className="glass-table"
        onChange={(pagination, _filters, sorter) => {
          setCurrentInput(confirmedFilter);
          if (pagination) {
            setPage(pagination.current || 1);
            setPageSize(pagination.pageSize || 10);
          }
          const singleSorter = Array.isArray(sorter) ? sorter[0] : (sorter as SorterResult<ScheduleConfigRecord>);
          if (singleSorter && singleSorter.field) {
            setSortField(singleSorter.field as string);
            setSortOrder(singleSorter.order || 'descend');
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
