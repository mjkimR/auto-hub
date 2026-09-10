import React, { useEffect } from 'react';
import { ConfigProvider, theme, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { client } from './generated/api/client.gen';
import { useThemeStore } from './stores/themeStore';
import { useAuthStore } from './stores/authStore';
import { Layout } from './components/Layout';
import { Login } from './views/Login';
import { Dashboard } from './views/Dashboard';
import { ScheduleConfigs } from './views/ScheduleConfigs';
import { ScheduleJobs } from './views/ScheduleJobs';
import { SystemConfigs } from './views/SystemConfigs';
import { TaskSpecs } from './views/TaskSpecs';
import { Projects } from './views/Projects';

// Set up the generated OpenAPI Client Base URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8389';
client.setConfig({
  baseUrl: apiBaseUrl,
});

// Configure React Query Client with sensible caching settings
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const ContentSwitcher: React.FC = () => {
  const { activeTab } = useThemeStore();

  switch (activeTab) {
    case 'projects':
      return <Projects />;
    case 'configs':
      return <ScheduleConfigs />;
    case 'jobs':
      return <ScheduleJobs />;
    case 'system':
      return <SystemConfigs />;
    case 'specs':
      return <TaskSpecs />;
    case 'dashboard':
    default:
      return <Dashboard />;
  }
};

export default function App() {
  const { isDarkMode } = useThemeStore();
  const { isAuthenticated, initializeAuth } = useAuthStore();

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: isDarkMode ? '#00f2fe' : '#1677ff',
            borderRadius: 12,
            fontFamily: 'Inter, Outfit, -apple-system, BlinkMacSystemFont, sans-serif',
          },
          algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
        }}
      >
        <AntdApp>
          {isAuthenticated ? (
            <Layout>
              <ContentSwitcher />
            </Layout>
          ) : (
            <Login />
          )}
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
