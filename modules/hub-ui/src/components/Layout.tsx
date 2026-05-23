import React from 'react';
import { Layout as AntdLayout, Menu, Button, Space, Badge, Tooltip } from 'antd';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import {
  LayoutDashboard,
  Clock,
  Activity,
  Sliders,
  Cpu,
  Sun,
  Moon,
  Server,
  RefreshCw,
  LogOut
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { healthApiHealthGet } from '../generated/api/sdk.gen';

const { Sider, Content, Header } = AntdLayout;

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isDarkMode, activeTab, toggleDarkMode, setActiveTab } = useThemeStore();
  const { logout } = useAuthStore();

  // Live polling for API Health
  const { data: healthData, isError, refetch, isFetching } = useQuery({
    queryKey: ['apiHealth'],
    queryFn: () => healthApiHealthGet({ throwOnError: true }),
    refetchInterval: 5000, // Poll every 5s
    retry: 1,
  });

  const getHealthStatus = () => {
    if (isError) return { status: 'error' as const, text: 'Offline' };
    if (!healthData) return { status: 'warning' as const, text: 'Connecting' };
    // backend response is expected to have success: true or status: 'ok'
    const res = healthData.data as any;
    if (res?.status === 'healthy' || res?.success || res?.status === 'ok') {
      return { status: 'success' as const, text: 'Online' };
    }
    return { status: 'warning' as const, text: 'Degraded' };
  };

  const health = getHealthStatus();

  const menuItems = [
    {
      key: 'dashboard',
      icon: <LayoutDashboard size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Dashboard</span>,
    },
    {
      key: 'configs',
      icon: <Clock size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Schedules</span>,
    },
    {
      key: 'jobs',
      icon: <Activity size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Executions</span>,
    },
    {
      key: 'system',
      icon: <Sliders size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>System Configs</span>,
    },
    {
      key: 'specs',
      icon: <Cpu size={18} />,
      label: <span className="font-outfit" style={{ fontSize: '15px', fontWeight: 500 }}>Task Specs</span>,
    },
  ];

  return (
    <AntdLayout style={{ minHeight: '100vh', background: 'var(--bg-app)' }}>
      {/* Glass Sidebar */}
      <Sider
        breakpoint="lg"
        collapsedWidth="0"
        width={260}
        className="glass-sidebar"
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          height: '100vh',
          borderRight: '1px solid var(--border-color)',
          background: 'var(--bg-sidebar)',
        }}
      >
        {/* Brand Logo */}
        <div style={{ padding: '24px 20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div 
            style={{ 
              background: 'var(--accent-gradient)', 
              width: 38, 
              height: 38, 
              borderRadius: '10px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              boxShadow: '0 4px 12px var(--accent-glow)'
            }}
          >
            <Server size={20} color="#fff" />
          </div>
          <div>
            <h1 
              className="gradient-text font-outfit" 
              style={{ 
                margin: 0, 
                fontSize: '18px', 
                lineHeight: '1.2', 
                background: 'var(--accent-gradient)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontWeight: 800
              }}
            >
              SCHEDULER
            </h1>
            <p className="font-outfit" style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
              MANAGER HUB
            </p>
          </div>
        </div>

        {/* Sidebar Menu */}
        <Menu
          mode="inline"
          selectedKeys={[activeTab]}
          onClick={({ key }) => setActiveTab(key)}
          items={menuItems}
          style={{
            background: 'transparent',
            borderRight: 0,
            padding: '12px 10px',
          }}
          className="glass-menu"
        />

        {/* System Health Panel at Bottom of Sider */}
        <div 
          style={{ 
            position: 'absolute', 
            bottom: 24, 
            left: 16, 
            right: 16, 
            padding: '16px', 
            borderRadius: '12px', 
            border: '1px solid var(--border-color)',
            background: 'rgba(0,0,0,0.02)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>System API Status</span>
            <Tooltip title="Force Refresh Status">
              <Button 
                type="text" 
                size="small" 
                icon={<RefreshCw size={12} className={isFetching ? 'glow-active' : ''} />} 
                onClick={() => refetch()}
              />
            </Tooltip>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Badge status={health.status} className="glow-active" />
            <span className="font-outfit" style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {health.text}
            </span>
          </div>
        </div>
      </Sider>

      {/* Main Content Area */}
      <AntdLayout style={{ marginLeft: 260, minHeight: '100vh', background: 'transparent' }}>
        {/* Glass Header */}
        <Header 
          className="glass-header"
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 9,
            width: '100%',
            height: '70px',
            padding: '0 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-header)',
            borderBottom: '1px solid var(--border-color)',
          }}
        >
          {/* Header Title based on Active View */}
          <h2 className="font-outfit" style={{ margin: 0, fontSize: '20px', fontWeight: 700, textTransform: 'capitalize' }}>
            {activeTab === 'configs' ? 'Schedule Configurations' : activeTab === 'jobs' ? 'Execution History' : activeTab === 'system' ? 'System Configurations' : activeTab === 'specs' ? 'Task Specifications' : 'Dashboard Summary'}
          </h2>

          <Space size="middle">
            {/* Theme Toggle Button */}
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

            {/* Logout Button */}
            <Tooltip title="Log Out">
              <Button
                type="text"
                shape="circle"
                icon={<LogOut size={20} color="var(--text-secondary)" />}
                onClick={logout}
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
          </Space>
        </Header>

        {/* Content Container */}
        <Content style={{ padding: '32px', minHeight: 280 }}>
          <div style={{ maxWidth: 1400, margin: '0 auto' }}>
            {children}
          </div>
        </Content>
      </AntdLayout>
    </AntdLayout>
  );
};
