import React from 'react';
import { Row, Col, Typography, Button, Badge, Space, Empty, Spin, Input, Tooltip } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getTaskSpecsApiV1TasksSpecsGet } from '../generated/api/sdk.gen';
import type { TaskSpecResponse } from '../generated/api/types.gen';
import { useThemeStore } from '../stores/themeStore';
import { Cpu, Plus, FileJson } from 'lucide-react';

const { Title, Text, Paragraph } = Typography;

export const TaskSpecs: React.FC = () => {
  const { setActiveTab, setPreselectedTask } = useThemeStore();
  const [currentInput, setCurrentInput] = React.useState('');
  const [confirmedFilter, setConfirmedFilter] = React.useState('');

  const { data: specsData, isLoading } = useQuery({
    queryKey: ['taskSpecs', confirmedFilter],
    queryFn: () => getTaskSpecsApiV1TasksSpecsGet({
      query: { name: confirmedFilter || undefined },
      throwOnError: true
    }),
  });

  const handleScheduleTask = (taskName: string) => {
    setPreselectedTask(taskName);
    setActiveTab('configs');
  };

  const specs = specsData?.data || [];
  const filteredSpecs = specs;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Search Header */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          background: 'var(--bg-card)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <Title level={4} style={{ margin: 0 }} className="font-outfit">
              Discovered Backend Tasks
            </Title>
            <Text type="secondary">
              Browse registered Python task specifications autodiscovered inside the Scheduler Hub module.
            </Text>
          </div>
          <Badge count={`${filteredSpecs.length} Active`} style={{ backgroundColor: 'var(--accent-primary)', fontSize: '13px', fontWeight: 600, padding: '0 8px' }} />
        </div>

        <Input.Search
          placeholder="Search tasks by dotted path name (Press Enter)..."
          size="large"
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          onSearch={(value) => setConfirmedFilter(value)}
          className="glass-search-input"
          allowClear
          enterButton
        />
      </div>

      {isLoading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <Spin size="large" />
          <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Discovered task specifications...</p>
        </div>
      ) : filteredSpecs.length === 0 ? (
        <Empty description="No tasks discovered matching query" />
      ) : (
        <Row gutter={[24, 24]}>
          {filteredSpecs.map((spec: TaskSpecResponse, idx: number) => (
            <Col xs={24} md={12} key={idx}>
              <div
                className="glass-panel glass-panel-hover"
                style={{
                  padding: '28px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  height: '100%',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                {/* Visual backglow decoration */}
                <div
                  style={{
                    position: 'absolute',
                    top: '-30px',
                    right: '-30px',
                    width: '100px',
                    height: '100px',
                    borderRadius: '50%',
                    background: 'var(--accent-glow)',
                    filter: 'blur(40px)'
                  }}
                />

                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div
                        style={{
                          background: 'var(--accent-glow)',
                          padding: '8px',
                          borderRadius: '8px',
                          border: '1px solid var(--border-color)'
                        }}
                      >
                        <Cpu size={20} color="var(--accent-primary)" />
                      </div>
                      <Text strong className="font-outfit" style={{ fontSize: '16px', letterSpacing: '-0.01em' }}>
                        {spec.name}
                      </Text>
                    </div>
                    <Badge status="processing" />
                  </div>

                  <Paragraph style={{ color: 'var(--text-secondary)', margin: 0, minHeight: '44px' }}>
                    {spec.description || 'No description provided by backend task developer.'}
                  </Paragraph>

                  {/* Schema Info */}
                  <div
                    style={{
                      background: 'rgba(0,0,0,0.02)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '12px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                      <FileJson size={14} style={{ color: 'var(--text-muted)' }} />
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Payload Spec Schema</span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {spec.payload_schema && typeof spec.payload_schema === 'object' && 'properties' in spec.payload_schema ? (
                        (() => {
                          const properties = (spec.payload_schema as { properties?: Record<string, { title?: string; type?: string }> }).properties || {};
                          return Object.keys(properties).map((prop, pIdx) => {
                            const pDetails = properties[prop] || {};
                            return (
                              <Tooltip key={pIdx} title={`${pDetails.title || prop} (${pDetails.type || 'any'})`}>
                                <Badge
                                  count={prop}
                                  style={{
                                    backgroundColor: 'rgba(0,0,0,0.04)',
                                    color: 'var(--text-secondary)',
                                    boxShadow: 'none',
                                    border: '1px solid var(--border-color)',
                                    fontSize: '11px',
                                    padding: '0 6px',
                                    borderRadius: '4px'
                                  }}
                                />
                              </Tooltip>
                            );
                          });
                        })()
                      ) : (
                        <Text type="secondary" style={{ fontSize: '11px' }}>No properties required (No payload task)</Text>
                      )}
                    </div>
                  </div>
                </Space>

                <Button
                  type="link"
                  icon={<Plus size={16} />}
                  onClick={() => handleScheduleTask(spec.name)}
                  style={{
                    alignSelf: 'flex-start',
                    paddingLeft: 0,
                    marginTop: '20px',
                    fontWeight: 600,
                    color: 'var(--accent-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  Create Schedule Config
                </Button>
              </div>
            </Col>
          ))}
        </Row>
      )}
    </Space>
  );
};
