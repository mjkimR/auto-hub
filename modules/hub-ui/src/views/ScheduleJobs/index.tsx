import React, { useState } from 'react';
import { Space, App as AntdApp } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getScheduleJobsApiV1ScheduleJobsGet,
  deleteScheduleJobApiV1ScheduleJobsScheduleJobIdDelete
} from '../../generated/api/sdk.gen';

import { JobFilterBar } from './components/JobFilterBar';
import { JobTable } from './components/JobTable';
import type { ScheduleJobRecord } from './components/JobTable';
import { JobDiagnosticsDrawer } from './components/JobDiagnosticsDrawer';
import type { ScheduleJobStatus } from '../../generated/api/types.gen';

export const ScheduleJobs: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const [currentInput, setCurrentInput] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortField, setSortField] = useState<string>('started_at');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');

  const [selectedJob, setSelectedJob] = useState<ScheduleJobRecord | null>(null);
  const [isDrawerVisible, setIsDrawerVisible] = useState(false);

  // 1. Fetch Execution Jobs
  const { data: jobsData, isLoading, refetch } = useQuery({
    queryKey: ['scheduleJobs', confirmedFilter, statusFilter, page, pageSize, sortField, sortOrder],
    queryFn: () => getScheduleJobsApiV1ScheduleJobsGet({
      query: {
        name: confirmedFilter || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter as ScheduleJobStatus,
        offset: (page - 1) * pageSize,
        limit: pageSize,
        order_by: `${sortOrder === 'descend' ? '-' : ''}${sortField}`
      },
      throwOnError: true
    }),
  });

  // 2. Delete Job Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      deleteScheduleJobApiV1ScheduleJobsScheduleJobIdDelete({
        path: { schedule_job_id: id },
        throwOnError: true
      }),
    onSuccess: () => {
      message.success('Job log deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['scheduleJobs'] });
      setIsDrawerVisible(false);
      setSelectedJob(null);
    },
    onError: (err: unknown) => {
      message.error(`Delete failed: ${(err as { message?: string }).message}`);
    }
  });

  const handleOpenDetail = (record: ScheduleJobRecord) => {
    setSelectedJob(record);
    setIsDrawerVisible(true);
  };

  const filteredJobs = (jobsData?.data?.items || []) as ScheduleJobRecord[];
  const totalCount = jobsData?.data?.total_count || 0;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <JobFilterBar
        currentInput={currentInput}
        setCurrentInput={setCurrentInput}
        confirmedFilter={confirmedFilter}
        setConfirmedFilter={setConfirmedFilter}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        setPage={setPage}
        refetch={refetch}
      />

      <JobTable
        filteredJobs={filteredJobs}
        isLoading={isLoading}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        sortField={sortField}
        sortOrder={sortOrder}
        setPage={setPage}
        setPageSize={setPageSize}
        setSortField={setSortField}
        setSortOrder={setSortOrder}
        confirmedFilter={confirmedFilter}
        setCurrentInput={setCurrentInput}
        onOpenDetail={handleOpenDetail}
        onDelete={(id) => deleteMutation.mutate(id)}
      />

      <JobDiagnosticsDrawer
        isDrawerVisible={isDrawerVisible}
        onClose={() => {
          setIsDrawerVisible(false);
          setSelectedJob(null);
        }}
        selectedJob={selectedJob}
        onDelete={(id) => deleteMutation.mutate(id)}
      />
    </Space>
  );
};
