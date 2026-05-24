import React from 'react';
import { Row, Col, Space, App as AntdApp } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getScheduleConfigsApiV1ScheduleConfigsGet,
  getScheduleJobsApiV1ScheduleJobsGet,
  triggerDispatchApiV1DispatchersTriggerPost,
  getSystemConfigsApiV1SystemConfigsGet
} from '../../generated/api/sdk.gen';
import type { ScheduleConfigRead, ScheduleJobRead, SystemConfigRead, DispatchResponse } from '../../generated/api/types.gen';
import { useThemeStore } from '../../stores/themeStore';
import { formatDistanceToNow, parseISO } from 'date-fns';

import { DashboardMetrics } from './components/DashboardMetrics';
import { DispatcherConsole } from './components/DispatcherConsole';
import { ActiveParameters } from './components/ActiveParameters';
import { RecentExecutions } from './components/RecentExecutions';

export const Dashboard: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const { triggerLoading, setTriggerLoading } = useThemeStore();

  // 1. Fetch Schedule Configs
  const { data: configsData, isLoading: configsLoading } = useQuery({
    queryKey: ['scheduleConfigs'],
    queryFn: () => getScheduleConfigsApiV1ScheduleConfigsGet({ throwOnError: true }),
  });

  // 2. Fetch Recent Schedule Jobs
  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ['scheduleJobs'],
    queryFn: () => getScheduleJobsApiV1ScheduleJobsGet({ throwOnError: true }),
  });

  // 3. Fetch System Configs
  const { data: systemConfigsData } = useQuery({
    queryKey: ['systemConfigs'],
    queryFn: () => getSystemConfigsApiV1SystemConfigsGet({ throwOnError: true }),
  });

  // 4. Manual Trigger Dispatch Mutation
  const triggerMutation = useMutation<
    { data?: DispatchResponse },
    unknown
  >({
    mutationFn: () => triggerDispatchApiV1DispatchersTriggerPost({ throwOnError: true }),
    onMutate: () => {
      setTriggerLoading(true);
    },
    onSuccess: (res) => {
      const dispatchedCount = res.data?.dispatched ?? 0;
      message.success(`Dispatcher triggered successfully! Dispatched ${dispatchedCount} jobs.`);
      queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] });
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
    },
    onError: (err: unknown) => {
      const errMsg = err && typeof err === 'object' && 'message' in err ? (err as { message: string }).message : 'Unknown error';
      message.error(`Trigger failed: ${errMsg}`);
    },
    onSettled: () => {
      setTriggerLoading(false);
    }
  });

  // Compute Metrics
  const schedules = (configsData?.data?.items || []) as ScheduleConfigRead[];
  const totalSchedules = schedules.length;
  const activeSchedules = schedules.filter((s) => s.enabled).length;

  const jobs = (jobsData?.data?.items || []) as ScheduleJobRead[];
  const totalJobsRun = jobs.length;
  const successfulJobs = jobs.filter((j) => j.status === 'success').length;
  const failedJobs = jobs.filter((j) => j.status === 'failure').length;
  const successRate = totalJobsRun > 0 ? Math.round((successfulJobs / totalJobsRun) * 100) : 100;

  const lastJob = jobs[0];
  const lastDispatchedStr = lastJob?.started_at
    ? `${formatDistanceToNow(parseISO(lastJob.started_at), { addSuffix: true })}`
    : 'No runs yet';

  const systemConfigs = (systemConfigsData?.data?.items || []) as SystemConfigRead[];

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      {/* 1. KPIs Metrics Row */}
      <DashboardMetrics
        configsLoading={configsLoading}
        jobsLoading={jobsLoading}
        totalSchedules={totalSchedules}
        activeSchedules={activeSchedules}
        successRate={successRate}
        failedJobs={failedJobs}
        lastJob={lastJob}
        lastDispatchedStr={lastDispatchedStr}
      />

      {/* 2. Dispatcher Console & Recent Runs */}
      <Row gutter={[24, 24]}>
        {/* Left Side: Dispatcher Control Board */}
        <Col xs={24} lg={10}>
          <Space orientation="vertical" size="large" style={{ width: '100%' }}>
            <DispatcherConsole
              triggerLoading={triggerLoading}
              onTrigger={() => triggerMutation.mutate()}
            />

            <ActiveParameters
              systemConfigs={systemConfigs}
            />
          </Space>
        </Col>

        {/* Right Side: Recent Execution Histories */}
        <Col xs={24} lg={14}>
          <RecentExecutions
            jobs={jobs}
            jobsLoading={jobsLoading}
            onRefresh={() => queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] })}
          />
        </Col>
      </Row>
    </Space>
  );
};
