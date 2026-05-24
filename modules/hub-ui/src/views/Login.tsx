import React, { useState } from 'react';
import { Card, Form, Input, Button, Alert, Typography, Tooltip } from 'antd';
import { Server, KeyRound, Lock, Sun, Moon, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';

const { Title, Text } = Typography;

export const Login: React.FC = () => {
  const { login, isValidating } = useAuthStore();
  const { isDarkMode, toggleDarkMode } = useThemeStore();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onFinish = async (values: { apiKey: string }) => {
    setErrorMsg(null);
    const success = await login(values.apiKey);
    if (!success) {
      setErrorMsg('Authentication failed. Please verify your API Key.');
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-app)',
        padding: '24px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Decorative background glows */}
      <div
        style={{
          position: 'absolute',
          top: '20%',
          left: '30%',
          width: '400px',
          height: '400px',
          background: 'var(--accent-gradient)',
          opacity: isDarkMode ? 0.08 : 0.04,
          filter: 'blur(100px)',
          borderRadius: '50%',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '20%',
          right: '30%',
          width: '350px',
          height: '350px',
          background: 'var(--accent-gradient)',
          opacity: isDarkMode ? 0.08 : 0.04,
          filter: 'blur(80px)',
          borderRadius: '50%',
          pointerEvents: 'none',
        }}
      />

      {/* Theme toggle in top right corner */}
      <div style={{ position: 'absolute', top: 24, right: 24 }}>
        <Tooltip title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
          <Button
            type="text"
            shape="circle"
            icon={isDarkMode ? <Sun size={20} color="#eab308" /> : <Moon size={20} color="#4f46e5" />}
            onClick={toggleDarkMode}
            style={{
              width: 42,
              height: 42,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
            }}
          />
        </Tooltip>
      </div>

      {/* Glassmorphic Login Card */}
      <Card
        className="glass-panel hover-glow"
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '28px 12px 12px 12px',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--box-shadow-glass)',
          background: 'var(--bg-card)',
          zIndex: 1,
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              display: 'inline-flex',
              background: 'var(--accent-gradient)',
              width: 54,
              height: 54,
              borderRadius: '14px',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
              boxShadow: '0 8px 24px var(--accent-glow)',
            }}
          >
            <Server size={28} color="#fff" />
          </div>
          <Title
            level={3}
            className="font-outfit"
            style={{ margin: '0 0 4px 0', fontWeight: 800, color: 'var(--text-primary)' }}
          >
            Scheduler Manager
          </Title>
          <Text
            className="font-outfit"
            style={{
              color: 'var(--text-secondary)',
              fontSize: '14px',
              fontWeight: 500,
              display: 'block',
            }}
          >
            Enter your API Key to access the dashboard
          </Text>
        </div>

        {/* Form and errors */}
        {errorMsg && (
          <Alert
            title={
              <span className="font-outfit" style={{ fontSize: '13px', fontWeight: 500 }}>
                {errorMsg}
              </span>
            }
            type="error"
            showIcon
            icon={<AlertCircle size={16} />}
            style={{
              marginBottom: 20,
              borderRadius: '10px',
              background: 'rgba(255, 77, 79, 0.08)',
              border: '1px solid rgba(255, 77, 79, 0.2)',
              color: '#ff4d4f',
            }}
          />
        )}

        <Form layout="vertical" onFinish={onFinish} size="large">
          <Form.Item
            name="apiKey"
            rules={[{ required: true, message: 'API key is required' }]}
            style={{ marginBottom: 24 }}
          >
            <Input.Password
              prefix={<KeyRound size={18} style={{ color: 'var(--text-muted)', marginRight: 6 }} />}
              placeholder="Enter your API Key"
              style={{
                borderRadius: '10px',
                background: 'rgba(0,0,0,0.02)',
                border: '1px solid var(--border-color)',
                height: '48px',
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={isValidating}
              block
              className="font-outfit glow-active"
              style={{
                background: 'var(--accent-gradient)',
                border: 0,
                height: '48px',
                borderRadius: '10px',
                fontSize: '15px',
                fontWeight: 700,
                boxShadow: '0 4px 12px var(--accent-glow)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
              }}
            >
              <Lock size={16} />
              Authenticate
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Footer Info */}
      <Text
        className="font-outfit"
        style={{
          marginTop: 24,
          fontSize: '11px',
          color: 'var(--text-muted)',
          fontWeight: 600,
          letterSpacing: '0.05em',
          textAlign: 'center',
          textTransform: 'uppercase',
          zIndex: 1,
        }}
      >
        Scheduler Manager Hub • Secure Admin Console
      </Text>
    </div>
  );
};
