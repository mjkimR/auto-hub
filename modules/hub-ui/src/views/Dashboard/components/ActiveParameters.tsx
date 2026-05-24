import React from 'react';
import { List, Typography, Empty } from 'antd';
import { Settings } from 'lucide-react';
import type { SystemConfigRead } from '../../../generated/api/types.gen';

const { Title, Text } = Typography;

interface ActiveParametersProps {
  systemConfigs: SystemConfigRead[];
}

export const ActiveParameters: React.FC<ActiveParametersProps> = ({
  systemConfigs,
}) => {
  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
        <Settings size={18} style={{ color: 'var(--accent-primary)' }} />
        <Title level={5} style={{ margin: 0 }} className="font-outfit">Active System Parameters</Title>
      </div>
      <List
        size="small"
        dataSource={systemConfigs.slice(0, 3)}
        renderItem={(item) => (
          <List.Item style={{ borderBottom: '1px solid var(--border-color)' }}>
            <Text strong>{item.name}</Text>
            <Text code>{JSON.stringify(item.data)}</Text>
          </List.Item>
        )}
        locale={{ emptyText: <Empty description="No system configs registered" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
      />
    </div>
  );
};
