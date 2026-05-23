import React from 'react';
import { ConfigProvider, theme, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { client } from './generated/api/client.gen';
import { useThemeStore } from './store/themeStore';
import { Layout } from './components/Layout';
import { Dashboard } from './components/Dashboard';
import { ScheduleConfigs } from './components/ScheduleConfigs';
import { ScheduleJobs } from './components/ScheduleJobs';
import { SystemConfigs } from './components/SystemConfigs';
import { TaskSpecs } from './components/TaskSpecs';

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
          <Layout>
            <ContentSwitcher />
          </Layout>
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

