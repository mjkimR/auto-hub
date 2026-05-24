import React from 'react';
import { Row, Col, Space, Typography, Tooltip, Popconfirm, Empty, Pagination, Button } from 'antd';
import { Database, Edit3, Trash2, AlertTriangle, Code, RefreshCw } from 'lucide-react';
import dayjs from 'dayjs';

const { Text } = Typography;

export interface SystemConfigRecord {
  id: string;
  name: string;
  data?: Record<string, unknown> | null;
  created_at: string;
}

interface ConfigCardGridProps {
  configs: SystemConfigRecord[];
  isLoading: boolean;
  page: number;
  pageSize: number;
  totalCount: number;
  setPage: (val: number) => void;
  setPageSize: (val: number) => void;
  confirmedFilter: string;
  setCurrentInput: (val: string) => void;
  onOpenEdit: (record: SystemConfigRecord) => void;
  onDelete: (id: string) => void;
}

export const ConfigCardGrid: React.FC<ConfigCardGridProps> = ({
  configs,
  isLoading,
  page,
  pageSize,
  totalCount,
  setPage,
  setPageSize,
  confirmedFilter,
  setCurrentInput,
  onOpenEdit,
  onDelete,
}) => {
  if (isLoading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center' }}>
        <RefreshCw className="glow-active" style={{ animation: 'spin 1.5s linear infinite' }} />
        <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Retrieving system defaults...</p>
      </div>
    );
  }

  if (configs.length === 0) {
    return <Empty description="No system configuration rules registered" />;
  }

  return (
    <>
      <Row gutter={[24, 24]}>
        {configs.map((config, idx) => (
          <Col xs={24} md={12} xl={8} key={idx}>
            <div
              className="glass-panel glass-panel-hover"
              style={{
                padding: '24px',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                position: 'relative',
              }}
            >
              <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ background: 'var(--accent-glow)', padding: '6px', borderRadius: '6px' }}>
                      <Database size={16} color="var(--accent-primary)" />
                    </div>
                    <Text strong className="font-outfit" style={{ fontSize: '15px' }}>
                      {config.name}
                    </Text>
                  </div>

                  <Space>
                    <Tooltip title="Edit Properties">
                      <Button
                        size="small"
                        type="text"
                        icon={<Edit3 size={14} />}
                        onClick={() => onOpenEdit(config)}
                        style={{ padding: 0, width: '24px', height: '24px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                      />
                    </Tooltip>

                    <Popconfirm
                      title="Delete system config?"
                      description="Deleting core orchestration variables might affect schedule execution logic."
                      icon={<AlertTriangle style={{ color: '#ff4d4f' }} size={16} />}
                      onConfirm={() => onDelete(config.id)}
                      okText="Delete"
                      cancelText="Cancel"
                      okButtonProps={{ danger: true }}
                    >
                      <Tooltip title="Delete Property">
                        <Button
                          size="small"
                          type="text"
                          danger
                          icon={<Trash2 size={14} />}
                          style={{ padding: 0, width: '24px', height: '24px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
                        />
                      </Tooltip>
                    </Popconfirm>
                  </Space>
                </div>

                {/* JSON Code block representation */}
                <div style={{ marginTop: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '6px', color: 'var(--text-muted)' }}>
                    <Code size={12} />
                    <span style={{ fontSize: '11px', fontWeight: 600 }}>Configuration properties</span>
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      background: 'rgba(0,0,0,0.02)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '12px',
                      fontFamily: 'monospace',
                      fontSize: '12px',
                      overflowX: 'auto',
                    }}
                  >
                    {config.data ? JSON.stringify(config.data, null, 2) : '{}'}
                  </pre>
                </div>
              </Space>

              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text type="secondary" style={{ fontSize: '11px' }}>
                  Registered: {dayjs(config.created_at).format('YYYY-MM-DD')}
                </Text>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      {totalCount > 0 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '24px' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={totalCount}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
              setCurrentInput(confirmedFilter);
            }}
            showSizeChanger
            pageSizeOptions={['6', '12', '24']}
          />
        </div>
      )}
    </>
  );
};
