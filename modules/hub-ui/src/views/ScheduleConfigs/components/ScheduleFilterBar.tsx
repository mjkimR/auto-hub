import React from 'react';
import { Space, Button, Input, Select, Typography } from 'antd';
import { Plus, RefreshCw } from 'lucide-react';

const { Text, Title } = Typography;
const { Option } = Select;

interface TaskSpec {
  name: string;
  payload_schema?: Record<string, unknown> | null;
}

interface ScheduleFilterBarProps {
  currentInput: string;
  setCurrentInput: (val: string) => void;
  confirmedFilter: string;
  setConfirmedFilter: (val: string) => void;
  taskFilter: string;
  setTaskFilter: (val: string) => void;
  enabledFilter: string;
  setEnabledFilter: (val: string) => void;
  setPage: (val: number) => void;
  tasksList: TaskSpec[];
  refetch: () => void;
  handleOpenCreate: () => void;
}

export const ScheduleFilterBar: React.FC<ScheduleFilterBarProps> = ({
  currentInput,
  setCurrentInput,
  confirmedFilter,
  setConfirmedFilter,
  taskFilter,
  setTaskFilter,
  enabledFilter,
  setEnabledFilter,
  setPage,
  tasksList,
  refetch,
  handleOpenCreate,
}) => {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <Title level={4} style={{ margin: 0, background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }} className="font-outfit">
            Schedule Configurations
          </Title>
          <Text type="secondary">
            Configure and orchestrate recurring cloud task schedules.
          </Text>
        </div>

        <Space>
          <Button icon={<RefreshCw size={14} />} onClick={refetch}>Refresh</Button>
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={handleOpenCreate}
            style={{
              background: 'var(--accent-gradient)',
              border: 0,
              boxShadow: '0 4px 12px var(--accent-glow)',
            }}
            className="hover-glow"
          >
            Create Schedule Config
          </Button>
        </Space>
      </div>

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        <Input.Search
          placeholder="Search schedules by name (Press Enter)..."
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          onSearch={(value) => {
            setConfirmedFilter(value);
            setPage(1);
          }}
          className="glass-search-input"
          style={{ maxWidth: '280px' }}
          allowClear
        />

        <Select
          value={taskFilter}
          onChange={(value) => {
            setTaskFilter(value);
            setPage(1);
            setCurrentInput(confirmedFilter);
          }}
          style={{ width: '220px' }}
          dropdownStyle={{ backdropFilter: 'blur(10px)' }}
          placeholder="Filter by Task"
        >
          <Option value="all">All Tasks</Option>
          {tasksList.map((t, idx) => (
            <Option key={idx} value={t.name}>{t.name}</Option>
          ))}
        </Select>

        <Select
          value={enabledFilter}
          onChange={(value) => {
            setEnabledFilter(value);
            setPage(1);
            setCurrentInput(confirmedFilter);
          }}
          style={{ width: '130px' }}
          dropdownStyle={{ backdropFilter: 'blur(10px)' }}
        >
          <Option value="all">All States</Option>
          <Option value="active">Active Only</Option>
          <Option value="inactive">Inactive Only</Option>
        </Select>
      </div>
    </div>
  );
};
