import React from 'react';
import { Button, Typography, Tooltip } from 'antd';
import { HelpCircle, Play, RefreshCw } from 'lucide-react';

const { Title, Text, Paragraph } = Typography;

interface DispatcherConsoleProps {
  triggerLoading: boolean;
  onTrigger: () => void;
}

export const DispatcherConsole: React.FC<DispatcherConsoleProps> = ({
  triggerLoading,
  onTrigger,
}) => {
  return (
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
          gap: '16px',
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
        onClick={onTrigger}
        style={{
          width: '100%',
          height: '48px',
          borderRadius: '10px',
          fontWeight: 600,
          fontSize: '15px',
          background: 'var(--accent-gradient)',
          border: 0,
          boxShadow: '0 4px 14px var(--accent-glow)',
        }}
        className="hover-glow"
      >
        {triggerLoading ? 'Processing Dispatch...' : 'Trigger Dispatcher Now'}
      </Button>
    </div>
  );
};
