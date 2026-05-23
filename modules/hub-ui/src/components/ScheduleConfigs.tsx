import React, { useState, useEffect } from 'react';
import { 
  Table, Button, Switch, Space, Input, Drawer, Form, 
  InputNumber, DatePicker, Select, App as AntdApp, Tooltip, 
  Popconfirm, Radio, Typography
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getScheduleConfigsApiV1ScheduleConfigsGet,
  createScheduleConfigApiV1ScheduleConfigsPost,
  deleteScheduleConfigApiV1ScheduleConfigsScheduleConfigIdDelete,
  patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch,
  getTaskSpecsApiV1TasksSpecsGet
} from '../generated/api/sdk.gen';
import { useThemeStore } from '../store/themeStore';
import { 
  Plus, Edit3, Trash2, AlertTriangle, 
  Clock, Calendar, RefreshCw
} from 'lucide-react';
import dayjs from 'dayjs';

const { Text, Title } = Typography;
const { Option } = Select;

export const ScheduleConfigs: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const { preselectedTask, setPreselectedTask } = useThemeStore();

  const [currentInput, setCurrentInput] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [taskFilter, setTaskFilter] = useState<string>('all');
  const [enabledFilter, setEnabledFilter] = useState<string>('all');
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');

  const [isDrawerVisible, setIsDrawerVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState<any>(null);
  const [scheduleType, setScheduleType] = useState<'cron' | 'interval'>('cron');

  const [form] = Form.useForm();

  // 1. Fetch Schedule Configs
  const { data: configsData, isLoading, refetch } = useQuery({
    queryKey: ['scheduleConfigs', confirmedFilter, taskFilter, enabledFilter, page, pageSize, sortField, sortOrder],
    queryFn: () => getScheduleConfigsApiV1ScheduleConfigsGet({ 
      query: {
        name: confirmedFilter || undefined,
        task_func: taskFilter === 'all' ? undefined : taskFilter,
        enabled: enabledFilter === 'all' ? undefined : enabledFilter === 'active',
        offset: (page - 1) * pageSize,
        limit: pageSize,
        order_by: `${sortOrder === 'descend' ? '-' : ''}${sortField}`
      },
      throwOnError: true 
    }),
  });

  // 2. Fetch Tasks list for Task dropdown selection
  const { data: specsData } = useQuery({
    queryKey: ['taskSpecs'],
    queryFn: () => getTaskSpecsApiV1TasksSpecsGet({ throwOnError: true }),
  });

  // 3. Create Mutation
  const createMutation = useMutation({
    mutationFn: (newConfig: any) => createScheduleConfigApiV1ScheduleConfigsPost({ body: newConfig, throwOnError: true }),
    onSuccess: () => {
      message.success('Schedule Configuration created successfully!');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
      setIsDrawerVisible(false);
      form.resetFields();
    },
    onError: (err: any) => {
      message.error(`Create failed: ${err.message || 'Check validation constraints'}`);
    }
  });

  // 4. Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => 
      patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch({ 
        path: { schedule_config_id: id }, 
        body: data, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('Schedule Configuration updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
      setIsDrawerVisible(false);
      setEditingConfig(null);
      form.resetFields();
    },
    onError: (err: any) => {
      message.error(`Update failed: ${err.message}`);
    }
  });

  // 5. Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => 
      deleteScheduleConfigApiV1ScheduleConfigsScheduleConfigIdDelete({ 
        path: { schedule_config_id: id }, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('Schedule deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
    },
    onError: (err: any) => {
      message.error(`Delete failed: ${err.message}`);
    }
  });

  // 6. Direct Toggle Switch (PATCH)
  const toggleEnabledMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch({
        path: { schedule_config_id: id },
        body: { enabled },
        throwOnError: true
      }),
    onSuccess: () => {
      message.success('Schedule status toggled');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
    },
    onError: (err: any) => {
      message.error(`Toggle failed: ${err.message}`);
    }
  });

  // Auto-open drawer when redirected from Task Specs
  useEffect(() => {
    if (preselectedTask) {
      setEditingConfig(null);
      form.resetFields();
      form.setFieldsValue({ task_func: preselectedTask });
      setIsDrawerVisible(true);
      // Consume the task spec selection
      setPreselectedTask(null);
    }
  }, [preselectedTask, form, setPreselectedTask]);

  // Open creation drawer
  const handleOpenCreate = () => {
    setEditingConfig(null);
    form.resetFields();
    form.setFieldsValue({ enabled: true });
    setScheduleType('cron');
    setIsDrawerVisible(true);
  };

  // Open edit drawer
  const handleOpenEdit = (record: any) => {
    setEditingConfig(record);
    setIsDrawerVisible(true);
    setScheduleType(record.interval_seconds ? 'interval' : 'cron');
    
    // Parse times
    const startAt = record.start_at ? dayjs(record.start_at) : null;
    const endAt = record.end_at ? dayjs(record.end_at) : null;
    
    // Format payload back to string representation
    const payloadStr = record.payload ? JSON.stringify(record.payload, null, 2) : '{}';

    form.setFieldsValue({
      name: record.name,
      description: record.description,
      task_func: record.task_func,
      cron_expression: record.cron_expression,
      interval_seconds: record.interval_seconds,
      enabled: record.enabled,
      start_at: startAt,
      end_at: endAt,
      payload: payloadStr,
    });
  };

  // Form submission handler
  const handleFormSubmit = (values: any) => {
    // Format date payloads to ISO strings
    const start_at = values.start_at ? values.start_at.toISOString() : null;
    const end_at = values.end_at ? values.end_at.toISOString() : null;

    // Parse payload safely
    let payload = {};
    if (values.payload) {
      try {
        payload = JSON.parse(values.payload);
      } catch {
        message.error('Payload must be a valid JSON string!');
        return;
      }
    }

    const payloadBody: any = {
      name: values.name,
      description: values.description,
      task_func: values.task_func,
      cron_expression: scheduleType === 'cron' ? (values.cron_expression || null) : null,
      interval_seconds: scheduleType === 'interval' ? (values.interval_seconds || null) : null,
      enabled: !!values.enabled,
      start_at,
      end_at,
      payload,
    };

    if (editingConfig) {
      updateMutation.mutate({ id: editingConfig.id, data: payloadBody });
    } else {
      createMutation.mutate(payloadBody);
    }
  };

  const tasksList = specsData?.data || [];
  const filteredConfigs = configsData?.data?.items || [];

  const columns = [
    {
      title: 'Schedule Name',
      dataIndex: 'name',
      key: 'name',
      sorter: true,
      sortOrder: sortField === 'name' ? sortOrder : undefined,
      render: (text: string, record: any) => (
        <Space direction="vertical" size={2}>
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
      render: (_: any, record: any) => {
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
      render: (enabled: boolean, record: any) => (
        <Switch 
          checked={enabled} 
          onChange={(checked) => toggleEnabledMutation.mutate({ id: record.id, enabled: checked })} 
        />
      ),
    },
    {
      title: 'Next Run',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      sorter: true,
      sortOrder: sortField === 'next_run_at' ? sortOrder : undefined,
      render: (dateStr: string) => {
        if (!dateStr) return <Text type="secondary">-</Text>;
        try {
          return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss');
        } catch {
          return dateStr;
        }
      }
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: any) => (
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
            onConfirm={() => deleteMutation.mutate(record.id)}
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
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Search and Action Bar */}
      <div 
        className="glass-panel" 
        style={{ 
          padding: '24px', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '16px'
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
            <Button icon={<RefreshCw size={14} />} onClick={() => refetch()}>Refresh</Button>
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
            {tasksList.map((t: any, idx: number) => (
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

      {/* Main Configurations Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <Table 
          columns={columns} 
          dataSource={filteredConfigs} 
          rowKey="id" 
          loading={isLoading} 
          className="glass-table"
          onChange={(pagination, _filters, sorter: any) => {
            setCurrentInput(confirmedFilter);
            if (pagination) {
              setPage(pagination.current || 1);
              setPageSize(pagination.pageSize || 10);
            }
            if (sorter && sorter.field) {
              setSortField(sorter.field);
              setSortOrder(sorter.order || 'descend');
            }
          }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: configsData?.data?.total_count || 0,
            showSizeChanger: true,
          }}
        />
      </div>

      {/* Slide-out Drawer Panel Form */}
      <Drawer
        title={editingConfig ? 'Update Schedule Config' : 'Register New Schedule Config'}
        width={560}
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
            label="Schedule Name"
            rules={[{ required: true, message: 'Please specify a unique, descriptive schedule name' }]}
          >
            <Input placeholder="e.g., Nightly Database Prune" />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="Explain what tasks are executed under this schedule config" />
          </Form.Item>

          <Form.Item
            name="task_func"
            label="Dotted Task Path"
            rules={[{ required: true, message: 'Please select a backend registered task' }]}
          >
            <Select placeholder="Select which Python task gets executed">
              {tasksList.map((t: any, idx: number) => (
                <Option key={idx} value={t.name}>{t.name}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item label="Execution Rule Configuration">
            <Radio.Group 
              value={scheduleType} 
              onChange={(e) => setScheduleType(e.target.value)}
              style={{ marginBottom: '16px' }}
            >
              <Radio.Button value="cron">Cron Expression</Radio.Button>
              <Radio.Button value="interval">Fixed Interval</Radio.Button>
            </Radio.Group>

            {scheduleType === 'cron' ? (
              <Form.Item
                name="cron_expression"
                rules={[{ required: scheduleType === 'cron', message: 'Cron expression is mandatory' }]}
                noStyle
              >
                <Input placeholder="e.g. 0 0 * * * (Every midnight)" addonBefore={<Calendar size={14} />} />
              </Form.Item>
            ) : (
              <Form.Item
                name="interval_seconds"
                rules={[{ required: scheduleType === 'interval', message: 'Interval is mandatory' }]}
                noStyle
              >
                <InputNumber 
                  min={1} 
                  style={{ width: '100%' }} 
                  placeholder="Interval window in seconds (e.g. 300)" 
                  addonBefore={<Clock size={14} />}
                />
              </Form.Item>
            )}
          </Form.Item>

          <Form.Item name="payload" label="Task Payload Arguments (JSON string)">
            <Input.TextArea 
              rows={5} 
              placeholder={`{\n  "message": "hello"\n}`} 
              style={{ fontFamily: 'monospace' }} 
            />
          </Form.Item>

          <Space size="large" style={{ width: '100%', justifyContent: 'space-between' }}>
            <Form.Item name="start_at" label="Active Period Start">
              <DatePicker showTime style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item name="end_at" label="Active Period End">
              <DatePicker showTime style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Form.Item name="enabled" valuePropName="checked" label="Initial Enabled State">
            <Switch defaultChecked />
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
                {editingConfig ? 'Save Changes' : 'Schedule Configuration'}
              </Button>
            </Space>
          </div>
        </Form>
      </Drawer>
    </Space>
  );
};
