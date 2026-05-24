import React from 'react';
import { Space, Input, Button, Typography } from 'antd';
import { RefreshCw, Plus } from 'lucide-react';

const { Title, Text } = Typography;

interface ConfigHeaderProps {
  currentInput: string;
  setCurrentInput: (val: string) => void;
  setConfirmedFilter: (val: string) => void;
  setPage: (val: number) => void;
  refetch: () => void;
  handleOpenCreate: () => void;
}

export const ConfigHeader: React.FC<ConfigHeaderProps> = ({
  currentInput,
  setCurrentInput,
  setConfirmedFilter,
  setPage,
  refetch,
  handleOpenCreate,
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap', flex: 1, justifyContent: 'space-between' }}>
        <div>
          <Title level={4} style={{ margin: 0 }} className="font-outfit">
            System Meta Parameters
          </Title>
          <Text type="secondary">
            Manage global schedule engine properties, timeouts, and orchestrator boundaries.
          </Text>
        </div>

        <Input.Search
          placeholder="Search parameters by name (Press Enter)..."
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          onSearch={(value) => {
            setConfirmedFilter(value);
            setPage(1);
          }}
          className="glass-search-input"
          style={{ maxWidth: '320px' }}
          allowClear
        />
      </div>

      <Space>
        <Button icon={<RefreshCw size={14} />} onClick={refetch}>
          Refresh
        </Button>
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
          Add System Config
        </Button>
      </Space>
    </div>
  );
};
