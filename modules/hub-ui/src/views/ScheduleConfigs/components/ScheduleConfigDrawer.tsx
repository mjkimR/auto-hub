import React, { useState, useEffect } from 'react';
import {
  Drawer, Form, Input, Select, Radio, InputNumber, Segmented,
  DatePicker, Switch, Button, Space, Typography, App as AntdApp
} from 'antd';
import RJSFForm from '@rjsf/antd';
import validator from '@rjsf/validator-ajv8';
import { Calendar, Clock } from 'lucide-react';
import dayjs from 'dayjs';
import type { ScheduleConfigRecord } from './ScheduleTable';

const { Text } = Typography;
const { Option } = Select;

interface TaskSpec {
  name: string;
  payload_schema?: Record<string, unknown> | null;
}

interface ScheduleConfigDrawerProps {
  isDrawerVisible: boolean;
  onClose: () => void;
  editingConfig: ScheduleConfigRecord | null;
  tasksList: TaskSpec[];
  onSubmit: (values: Record<string, unknown>, isRawJsonMode: boolean, payloadObject: Record<string, unknown>) => void;
  isPending: boolean;
}

export const ScheduleConfigDrawer: React.FC<ScheduleConfigDrawerProps> = ({
  isDrawerVisible,
  onClose,
  editingConfig,
  tasksList,
  onSubmit,
  isPending,
}) => {
  const { message } = AntdApp.useApp();
  const [form] = Form.useForm();

  const [scheduleType, setScheduleType] = useState<'cron' | 'interval'>('cron');
  const [isRawJsonMode, setIsRawJsonMode] = useState<boolean>(false);
  const [payloadObject, setPayloadObject] = useState<Record<string, unknown>>({});

  // Resolve payload schema based on selected task func
  const selectedTaskFunc = Form.useWatch('task_func', form);
  const selectedTaskSpec = tasksList.find((t) => t.name === selectedTaskFunc);
  const selectedTaskSchema = selectedTaskSpec?.payload_schema;

  // Adjust isRawJsonMode state during rendering when selectedTaskFunc changes
  const [prevSelectedTaskFunc, setPrevSelectedTaskFunc] = useState<string | undefined>(undefined);
  if (selectedTaskFunc !== prevSelectedTaskFunc) {
    setPrevSelectedTaskFunc(selectedTaskFunc);
    if (selectedTaskFunc) {
      setIsRawJsonMode(false);
    }
  }

  // Handle drawer open / mode set
  useEffect(() => {
    if (isDrawerVisible) {
      const timer = setTimeout(() => {
        if (editingConfig) {
          setScheduleType(editingConfig.interval_seconds ? 'interval' : 'cron');

          // Parse times
          const startAt = editingConfig.start_at ? dayjs(editingConfig.start_at) : null;
          const endAt = editingConfig.end_at ? dayjs(editingConfig.end_at) : null;

          // Format payload back to string representation
          const payloadStr = editingConfig.payload ? JSON.stringify(editingConfig.payload, null, 2) : '{}';
          setPayloadObject(editingConfig.payload || {});

          // Set initial editing mode
          if (editingConfig.task_func) {
            const spec = tasksList.find((t) => t.name === editingConfig.task_func);
            setIsRawJsonMode(!spec?.payload_schema);
          }

          form.setFieldsValue({
            name: editingConfig.name,
            description: editingConfig.description,
            task_func: editingConfig.task_func,
            cron_expression: editingConfig.cron_expression,
            interval_seconds: editingConfig.interval_seconds,
            enabled: editingConfig.enabled,
            start_at: startAt,
            end_at: endAt,
            payload: payloadStr,
          });
        } else {
          form.resetFields();
          form.setFieldsValue({ enabled: true });
          setScheduleType('cron');
          setPayloadObject({});
          setIsRawJsonMode(false);
        }
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [isDrawerVisible, editingConfig, form, tasksList]);

  const handleFormFinish = (values: Record<string, unknown>) => {
    onSubmit(values, isRawJsonMode, payloadObject);
  };

  return (
    <Drawer
      title={editingConfig ? 'Update Schedule Config' : 'Register New Schedule Config'}
      width={560}
      onClose={onClose}
      open={isDrawerVisible}
      bodyStyle={{ paddingBottom: 80 }}
      style={{ backdropFilter: 'blur(10px)' }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFormFinish}
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
            {tasksList.map((t, idx) => (
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

        <div style={{ marginBottom: '24px' }}>
          <span style={{ display: 'block', marginBottom: '8px', color: 'var(--text-primary)', fontWeight: 500 }}>
            Task Payload Arguments
          </span>

          <Segmented
            options={[
              { label: 'Visual Form Editor', value: 'visual' },
              { label: 'Raw JSON Editor', value: 'json' }
            ]}
            value={isRawJsonMode ? 'json' : 'visual'}
            onChange={(value) => {
              if (value === 'visual') {
                const rawText = form.getFieldValue('payload');
                if (rawText) {
                  try {
                    const parsed = JSON.parse(rawText);
                    setPayloadObject(parsed);
                    setIsRawJsonMode(false);
                  } catch {
                    message.error('Cannot switch to Visual Form: Current input is not a valid JSON string.');
                  }
                } else {
                  setIsRawJsonMode(false);
                }
              } else {
                form.setFieldsValue({ payload: JSON.stringify(payloadObject, null, 2) });
                setIsRawJsonMode(true);
              }
            }}
            style={{ marginBottom: '12px', width: '100%' }}
          />

          {isRawJsonMode ? (
            <Form.Item name="payload" noStyle>
              <Input.TextArea
                rows={5}
                placeholder={`{\n  "message": "hello"\n}`}
                style={{ fontFamily: 'monospace' }}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    setPayloadObject(parsed);
                  } catch {
                    // ignore intermediate invalid states
                  }
                }}
              />
            </Form.Item>
          ) : (
            !selectedTaskFunc ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '24px',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  background: 'rgba(0,0,0,0.01)'
                }}
              >
                <Text type="secondary">Please select a backend task above to load its payload form.</Text>
              </div>
            ) : (!selectedTaskSchema || !selectedTaskSchema.properties || Object.keys(selectedTaskSchema.properties).length === 0) ? (
              <div
                style={{
                  textAlign: 'center',
                  padding: '24px',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  background: 'rgba(0,0,0,0.01)'
                }}
              >
                <Text type="secondary">No payload parameters are required for this task.</Text>
              </div>
            ) : (
              <div
                className="rjsf-container"
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  padding: '16px',
                  background: 'rgba(0,0,0,0.01)'
                }}
              >
                <RJSFForm
                  schema={selectedTaskSchema}
                  formData={payloadObject}
                  onChange={(e) => setPayloadObject(e.formData)}
                  validator={validator}
                  showErrorList={false}
                >
                  <></>
                </RJSFForm>
              </div>
            )
          )}
        </div>

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
            <Button onClick={onClose}>Cancel</Button>
            <Button type="primary" htmlType="submit" loading={isPending}>
              {editingConfig ? 'Save Changes' : 'Schedule Configuration'}
            </Button>
          </Space>
        </div>
      </Form>
    </Drawer>
  );
};
