import React, { useState, useEffect } from 'react';
import { Space, App as AntdApp } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import {
  getScheduleConfigsApiV1ScheduleConfigsGet,
  createScheduleConfigApiV1ScheduleConfigsPost,
  deleteScheduleConfigApiV1ScheduleConfigsScheduleConfigIdDelete,
  patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch,
  getTaskSpecsApiV1TasksSpecsGet
} from '../../generated/api/sdk.gen';
import { useThemeStore } from '../../stores/themeStore';

import { ScheduleFilterBar } from './components/ScheduleFilterBar';
import { ScheduleTable } from './components/ScheduleTable';
import type { ScheduleConfigRecord } from './components/ScheduleTable';
import { ScheduleConfigDrawer } from './components/ScheduleConfigDrawer';
import type { ScheduleConfigCreate, ScheduleConfigPatch } from '../../generated/api/types.gen';

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

  const [isDrawerVisible, setIsDrawerVisible] = useState(() => !!preselectedTask);
  const [editingConfig, setEditingConfig] = useState<ScheduleConfigRecord | null>(null);

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
    mutationFn: (newConfig: unknown) => createScheduleConfigApiV1ScheduleConfigsPost({ body: newConfig as ScheduleConfigCreate, throwOnError: true }),
    onSuccess: () => {
      message.success('Schedule Configuration created successfully!');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
      setIsDrawerVisible(false);
    },
    onError: (err: unknown) => {
      message.error(`Create failed: ${(err as { message?: string }).message || 'Check validation constraints'}`);
    }
  });

  // 4. Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: unknown }) =>
      patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch({
        path: { schedule_config_id: id },
        body: data as ScheduleConfigPatch,
        throwOnError: true
      }),
    onSuccess: () => {
      message.success('Schedule Configuration updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['scheduleConfigs'] });
      setIsDrawerVisible(false);
      setEditingConfig(null);
    },
    onError: (err: unknown) => {
      message.error(`Update failed: ${(err as { message?: string }).message}`);
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
    onError: (err: unknown) => {
      message.error(`Delete failed: ${(err as { message?: string }).message}`);
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
    onError: (err: unknown) => {
      message.error(`Toggle failed: ${(err as { message?: string }).message}`);
    }
  });

  // Auto-fill drawer form when redirected from Task Specs
  useEffect(() => {
    if (preselectedTask) {
      // Consume the preselected task spec selection asynchronously to avoid synchronous cascading renders
      const timer = setTimeout(() => {
        setIsDrawerVisible(true);
        setPreselectedTask(null);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [preselectedTask, setPreselectedTask]);

  // Open creation drawer
  const handleOpenCreate = () => {
    setEditingConfig(null);
    setIsDrawerVisible(true);
  };

  // Open edit drawer
  const handleOpenEdit = (record: ScheduleConfigRecord) => {
    setEditingConfig(record);
    setIsDrawerVisible(true);
  };

  // Drawer Form submission handler
  const handleDrawerSubmit = (values: Record<string, unknown>, isRawJsonMode: boolean, payloadObject: Record<string, unknown>) => {
    // Format date payloads to ISO strings
    const start_at = dayjs.isDayjs(values.start_at) ? values.start_at.toISOString() : null;
    const end_at = dayjs.isDayjs(values.end_at) ? values.end_at.toISOString() : null;

    // Parse payload safely
    let payload = {};
    if (isRawJsonMode) {
      if (values.payload) {
        try {
          payload = JSON.parse(values.payload as string);
        } catch {
          message.error('Payload must be a valid JSON string!');
          return;
        }
      }
    } else {
      payload = payloadObject;
    }

    const payloadBody: Record<string, unknown> = {
      name: values.name,
      description: values.description,
      task_func: values.task_func,
      cron_expression: values.cron_expression || null,
      interval_seconds: values.interval_seconds || null,
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
  const filteredConfigs = (configsData?.data?.items || []) as ScheduleConfigRecord[];
  const totalCount = configsData?.data?.total_count || 0;

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <ScheduleFilterBar
        currentInput={currentInput}
        setCurrentInput={setCurrentInput}
        confirmedFilter={confirmedFilter}
        setConfirmedFilter={setConfirmedFilter}
        taskFilter={taskFilter}
        setTaskFilter={setTaskFilter}
        enabledFilter={enabledFilter}
        setEnabledFilter={setEnabledFilter}
        setPage={setPage}
        tasksList={tasksList}
        refetch={refetch}
        handleOpenCreate={handleOpenCreate}
      />

      <ScheduleTable
        filteredConfigs={filteredConfigs}
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
        toggleEnabled={(id, enabled) => toggleEnabledMutation.mutate({ id, enabled })}
        deleteConfig={(id) => deleteMutation.mutate(id)}
        handleOpenEdit={handleOpenEdit}
      />

      <ScheduleConfigDrawer
        isDrawerVisible={isDrawerVisible}
        onClose={() => {
          setIsDrawerVisible(false);
          setEditingConfig(null);
        }}
        editingConfig={editingConfig}
        tasksList={tasksList}
        onSubmit={handleDrawerSubmit}
        isPending={createMutation.isPending || updateMutation.isPending}
      />
    </Space>
  );
};
