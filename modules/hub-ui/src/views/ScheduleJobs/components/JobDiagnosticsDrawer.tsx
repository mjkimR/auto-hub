import React from 'react';
import { Drawer, Space, Typography, Divider, Popconfirm, Button } from 'antd';
import { Clock, ShieldAlert, Terminal, Trash2 } from 'lucide-react';
import dayjs from 'dayjs';
import type { ScheduleJobRecord } from './JobTable';

const { Title, Text } = Typography;

interface JobDiagnosticsDrawerProps {
  isDrawerVisible: boolean;
  onClose: () => void;
  selectedJob: ScheduleJobRecord | null;
  onDelete: (id: string) => void;
}

export const JobDiagnosticsDrawer: React.FC<JobDiagnosticsDrawerProps> = ({
  isDrawerVisible,
  onClose,
  selectedJob,
  onDelete,
}) => {
  return (
    <Drawer
      title="Execution Diagnostics Terminal"
      width={600}
      onClose={onClose}
      open={isDrawerVisible}
      style={{ backdropFilter: 'blur(10px)' }}
    >
      {selectedJob && (
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Header info */}
          <div>
            <Title level={4} style={{ margin: 0 }} className="font-outfit">
              {selectedJob.name}
            </Title>
            <Text type="secondary" style={{ fontSize: '12px', fontFamily: 'monospace' }}>
              Job ID: {selectedJob.id}
            </Text>
          </div>

          {/* Status indicators */}
          <div
            style={{
              display: 'flex',
              gap: '12px',
              flexWrap: 'wrap',
              padding: '16px',
              background: 'rgba(0,0,0,0.02)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
            }}
          >
            <div>
              <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>STATUS</Text>
              <span className={`glass-status-badge ${selectedJob.status === 'success' ? 'success' : selectedJob.status === 'failure' ? 'failure' : 'pending'}`} style={{ marginTop: '4px' }}>
                {selectedJob.status.toUpperCase()}
              </span>
            </div>
            <Divider type="vertical" style={{ height: '40px' }} />
            <div>
              <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>TRIGGERED TIME</Text>
              <Text strong style={{ fontSize: '13px' }}>
                {dayjs(selectedJob.started_at).format('YYYY-MM-DD HH:mm:ss')}
              </Text>
            </div>
            <Divider type="vertical" style={{ height: '40px' }} />
            <div>
              <Text type="secondary" style={{ fontSize: '11px', display: 'block' }}>FINISHED TIME</Text>
              <Text strong style={{ fontSize: '13px' }}>
                {selectedJob.finished_at ? dayjs(selectedJob.finished_at).format('YYYY-MM-DD HH:mm:ss') : 'Processing'}
              </Text>
            </div>
          </div>

          {/* Error Message Traceback Box */}
          {selectedJob.status === 'failure' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <ShieldAlert size={16} color="#ff4d4f" />
                <Text strong style={{ color: '#ff4d4f' }}>Diagnostics & Traceback Exception</Text>
              </div>
              {/* Visual Terminal Block */}
              <div
                style={{
                  background: '#0d1117',
                  borderRadius: '10px',
                  border: '1px solid rgba(255, 77, 79, 0.2)',
                  padding: '20px',
                  fontFamily: 'monospace',
                  color: '#ff7b72',
                  fontSize: '13px',
                  lineHeight: '1.6',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  boxShadow: 'inset 0 0 10px rgba(0,0,0,0.8)',
                }}
              >
                <div style={{ display: 'flex', gap: '8px', color: '#8b949e', marginBottom: '12px', borderBottom: '1px solid #21262d', paddingBottom: '8px' }}>
                  <Terminal size={14} />
                  <span>stderr Exception Log</span>
                </div>
                {selectedJob.error_message || 'Backend exception was triggered, but failed to pipe stdout error messages.'}
              </div>
            </div>
          )}

          {/* Input payload snapshot explorer */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Clock size={16} style={{ color: 'var(--accent-primary)' }} />
              <Text strong>Task Payload Snapshot Arguments</Text>
            </div>
            <pre
              style={{
                background: 'rgba(0,0,0,0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                padding: '16px',
                fontFamily: 'monospace',
                fontSize: '12px',
                overflowX: 'auto',
              }}
            >
              {selectedJob.payload ? JSON.stringify(selectedJob.payload, null, 2) : 'No payload arguments were passed to this run.'}
            </pre>
          </div>

          {/* Dangerous Area */}
          <Divider style={{ margin: '16px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Popconfirm
              title="Wipe this individual record?"
              onConfirm={() => onDelete(selectedJob.id)}
              okText="Yes, Wipe"
              cancelText="Cancel"
              okButtonProps={{ danger: true }}
            >
              <Button danger type="dashed" icon={<Trash2 size={14} />}>
                Wipe Execution Log File
              </Button>
            </Popconfirm>
          </div>
        </Space>
      )}
    </Drawer>
  );
};
