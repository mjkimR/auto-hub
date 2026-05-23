import React, { useState } from 'react';
import { 
  Row, Col, Typography, Button, Drawer, Form, Input, 
  App as AntdApp, Space, Popconfirm, Empty, Tooltip, Pagination 
} from 'antd';
import dayjs from 'dayjs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getSystemConfigsApiV1SystemConfigsGet,
  createSystemConfigApiV1SystemConfigsPost,
  deleteSystemConfigApiV1SystemConfigsSystemConfigIdDelete,
  patchSystemConfigApiV1SystemConfigsSystemConfigIdPatch
} from '../generated/api/sdk.gen';
import { 
  Plus, Trash2, Edit3, AlertTriangle, 
  RefreshCw, Database, Code 
} from 'lucide-react';

const { Title, Text } = Typography;

export const SystemConfigs: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const [currentInput, setCurrentInput] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(6);

  const [form] = Form.useForm();

  // 1. Fetch System Configs
  const { data: systemConfigsData, isLoading, refetch } = useQuery({
    queryKey: ['systemConfigs', confirmedFilter, page, pageSize],
    queryFn: () => getSystemConfigsApiV1SystemConfigsGet({ 
      query: {
        name: confirmedFilter || undefined,
        offset: (page - 1) * pageSize,
        limit: pageSize,
        order_by: '-created_at'
      },
      throwOnError: true 
    }),
  });

  // 2. Create Mutation
  const createMutation = useMutation({
    mutationFn: (newConfig: any) => createSystemConfigApiV1SystemConfigsPost({ body: newConfig, throwOnError: true }),
    onSuccess: () => {
      message.success('System Configuration registered successfully!');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
      setIsDrawerVisible(false);
      form.resetFields();
    },
    onError: (err: any) => {
      message.error(`Create failed: ${err.message}`);
    }
  });

  // 3. Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => 
      patchSystemConfigApiV1SystemConfigsSystemConfigIdPatch({ 
        path: { system_config_id: id }, 
        body: data, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('System Configuration saved successfully!');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
      setIsDrawerVisible(false);
      setEditingConfig(null);
      form.resetFields();
    },
    onError: (err: any) => {
      message.error(`Save failed: ${err.message}`);
    }
  });

  // 4. Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => 
      deleteSystemConfigApiV1SystemConfigsSystemConfigIdDelete({ 
        path: { system_config_id: id }, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('Configuration deleted');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
    },
    onError: (err: any) => {
      message.error(`Delete failed: ${err.message}`);
    }
  });

  const [isDrawerVisible, setIsDrawerVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState<any>(null);

  const handleOpenCreate = () => {
    setEditingConfig(null);
    form.resetFields();
    setIsDrawerVisible(true);
  };

  const handleOpenEdit = (record: any) => {
    setEditingConfig(record);
    setIsDrawerVisible(true);

    const dataStr = record.data ? JSON.stringify(record.data, null, 2) : '{}';

    form.setFieldsValue({
      name: record.name,
      data: dataStr
    });
  };

  const handleFormSubmit = (values: any) => {
    let data = {};
    if (values.data) {
      try {
        data = JSON.parse(values.data);
      } catch {
        message.error('Data must be a valid JSON string!');
        return;
      }
    }

    const payload: any = {
      name: values.name,
      data
    };

    if (editingConfig) {
      updateMutation.mutate({ id: editingConfig.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const configs = systemConfigsData?.data?.items || [];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Top action header */}
      <div 
        className="glass-panel" 
        style={{ 
          padding: '24px', 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          flexWrap: 'wrap', 
          gap: '16px' 
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
          <Button icon={<RefreshCw size={14} />} onClick={() => refetch()}>
            Refresh
          </Button>
          <Button 
            type="primary" 
            icon={<Plus size={16} />} 
            onClick={handleOpenCreate}
            style={{ 
              background: 'var(--accent-gradient)', 
              border: 0,
              boxShadow: '0 4px 12px var(--accent-glow)' 
            }}
            className="hover-glow"
          >
            Add System Config
          </Button>
        </Space>
      </div>

      {isLoading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <RefreshCw className="glow-active" style={{ animation: 'spin 1.5s linear infinite' }} />
          <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Retrieving system defaults...</p>
        </div>
      ) : configs.length === 0 ? (
        <Empty description="No system configuration rules registered" />
      ) : (
        <Row gutter={[24, 24]}>
          {configs.map((config: any, idx: number) => (
            <Col xs={24} md={12} xl={8} key={idx}>
              <div 
                className="glass-panel glass-panel-hover" 
                style={{ 
                  padding: '24px', 
                  height: '100%', 
                  display: 'flex', 
                  flexDirection: 'column', 
                  justifyContent: 'space-between',
                  position: 'relative'
                }}
              >
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
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
                          onClick={() => handleOpenEdit(config)} 
                        />
                      </Tooltip>

                      <Popconfirm
                        title="Delete system config?"
                        description="Deleting core orchestration variables might affect schedule execution logic."
                        icon={<AlertTriangle style={{ color: '#ff4d4f' }} size={16} />}
                        onConfirm={() => deleteMutation.mutate(config.id)}
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
                        overflowX: 'auto' 
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
      )}

      {systemConfigsData?.data?.total_count && systemConfigsData.data.total_count > 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '24px' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={systemConfigsData.data.total_count}
            onChange={(p, ps) => {
              setPage(p);
              setPageSize(ps);
              setCurrentInput(confirmedFilter);
            }}
            showSizeChanger
            pageSizeOptions={['6', '12', '24']}
          />
        </div>
      ) : null}

      {/* Slide-out Drawer Panel Form */}
      <Drawer
        title={editingConfig ? 'Update System Config' : 'Register New System Configuration'}
        width={460}
        onClose={() => setIsDrawerVisible(false)}
        open={isDrawerVisible}
        bodyStyle={{ paddingBottom: 80 }}
        style={{ backdropFilter: 'blur(10px)' }}
      >
        <Form 
          form={form} 
          layout="vertical" 
          onFinish={handleFormSubmit}
          requiredMark="optional"
        >
          <Form.Item
            name="name"
            label="Property Key Name"
            rules={[{ required: true, message: 'Please specify the system property key name' }]}
          >
            <Input placeholder="e.g. GLOBAL_TIMEOUT_SECONDS" disabled={!!editingConfig} />
          </Form.Item>

          <Form.Item
            name="data"
            label="JSON Data Properties"
            rules={[{ required: true, message: 'Please specify properties data map' }]}
          >
            <Input.TextArea 
              rows={12} 
              placeholder={`{\n  "value": 30,\n  "buffer": 5\n}`} 
              style={{ fontFamily: 'monospace' }} 
            />
          </Form.Item>

          <div 
            style={{
              position: 'absolute',
              right: 0,
              bottom: 0,
              width: '100%',
              borderTop: '1px solid var(--border-color)',
              padding: '16px 24px',
              background: 'var(--bg-card)',
              textAlign: 'right',
              zIndex: 1
            }}
          >
            <Space>
              <Button onClick={() => setIsDrawerVisible(false)}>Cancel</Button>
              <Button type="primary" htmlType="submit" loading={createMutation.isPending || updateMutation.isPending}>
                {editingConfig ? 'Save Properties' : 'Add Property'}
              </Button>
            </Space>
          </div>
        </Form>
      </Drawer>
    </Space>
  );
};
