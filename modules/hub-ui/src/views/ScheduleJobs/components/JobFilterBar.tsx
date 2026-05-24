import React from 'react';
import { Space, Input, Select, Button } from 'antd';
import { RefreshCw } from 'lucide-react';



interface JobFilterBarProps {
  currentInput: string;
  setCurrentInput: (val: string) => void;
  confirmedFilter: string;
  setConfirmedFilter: (val: string) => void;
  statusFilter: string;
  setStatusFilter: (val: string) => void;
  setPage: (val: number) => void;
  refetch: () => void;
}

export const JobFilterBar: React.FC<JobFilterBarProps> = ({
  currentInput,
  setCurrentInput,
  confirmedFilter,
  setConfirmedFilter,
  statusFilter,
  setStatusFilter,
  setPage,
  refetch,
}) => {
  return (
    <div
      className="glass-panel"
      style={{
        padding: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px',
      }}
    >
      <Space size="middle" style={{ flexWrap: 'wrap' }}>
        <Input.Search
          placeholder="Search executions by job name (Press Enter)..."
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          onSearch={(value) => {
            setConfirmedFilter(value);
            setPage(1);
          }}
          className="glass-search-input"
          style={{ width: '320px' }}
          allowClear
        />

        <Select
          value={statusFilter}
          onChange={(value) => {
            setStatusFilter(value);
            setPage(1);
            setCurrentInput(confirmedFilter);
          }}
          style={{ width: '150px' }}
          styles={{ popup: { root: { backdropFilter: 'blur(10px)' } } }}
          options={[
            { label: 'All Statuses', value: 'all' },
            { label: 'Success Only', value: 'success' },
            { label: 'Failure Only', value: 'failure' },
            { label: 'Pending Only', value: 'pending' }
          ]}
        />
      </Space>

      <Button icon={<RefreshCw size={14} />} onClick={refetch}>
        Refresh Log Feed
      </Button>
    </div>
  );
};
