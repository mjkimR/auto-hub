import React, { useEffect } from 'react';
import { Drawer, Form, Input, Button, Space } from 'antd';
import type { SystemConfigRecord } from './ConfigCardGrid';

interface SystemConfigDrawerProps {
  isDrawerVisible: boolean;
  onClose: () => void;
  editingConfig: SystemConfigRecord | null;
  onSubmit: (values: Record<string, unknown>) => void;
  isPending: boolean;
}

export const SystemConfigDrawer: React.FC<SystemConfigDrawerProps> = ({
  isDrawerVisible,
  onClose,
  editingConfig,
  onSubmit,
  isPending,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (isDrawerVisible) {
      const timer = setTimeout(() => {
        if (editingConfig) {
          const dataStr = editingConfig.data ? JSON.stringify(editingConfig.data, null, 2) : '{}';
          form.setFieldsValue({
            name: editingConfig.name,
            data: dataStr,
          });
        } else {
          form.resetFields();
        }
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [isDrawerVisible, editingConfig, form]);

  return (
    <Drawer
      title={editingConfig ? 'Update System Config' : 'Register New System Configuration'}
      size={460}
      onClose={onClose}
      open={isDrawerVisible}
      styles={{ body: { paddingBottom: 80 } }}
      style={{ backdropFilter: 'blur(10px)' }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onSubmit}
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
            zIndex: 1,
          }}
        >
          <Space>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="primary" htmlType="submit" loading={isPending}>
              {editingConfig ? 'Save Properties' : 'Add Property'}
            </Button>
          </Space>
        </div>
      </Form>
    </Drawer>
  );
};
