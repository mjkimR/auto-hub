import React, { useState } from 'react';
import { Space, App as AntdApp } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSystemConfigsApiV1SystemConfigsGet,
  createSystemConfigApiV1SystemConfigsPost,
  deleteSystemConfigApiV1SystemConfigsSystemConfigIdDelete,
  patchSystemConfigApiV1SystemConfigsSystemConfigIdPatch
} from '../../generated/api/sdk.gen';

import { ConfigHeader } from './components/ConfigHeader';
import { ConfigCardGrid } from './components/ConfigCardGrid';
import type { SystemConfigRecord } from './components/ConfigCardGrid';
import { SystemConfigDrawer } from './components/SystemConfigDrawer';
import type { SystemConfigCreate, SystemConfigPatch } from '../../generated/api/types.gen';

export const SystemConfigs: React.FC = () => {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const [currentInput, setCurrentInput] = useState('');
  const [confirmedFilter, setConfirmedFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(6);

  const [isDrawerVisible, setIsDrawerVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState<SystemConfigRecord | null>(null);

  // 1. Fetch System Configs
  const { data: systemConfigsData, isLoading, refetch } = useQuery({
    queryKey: ['systemConfigs', confirmedFilter, page, pageSize],
    queryFn: () => getSystemConfigsApiV1SystemConfigsGet({
      query: {
        name: confirmedFilter || undefined,
        offset: (page - 1) * pageSize,
        limit: pageSize,
        order_by: '-created_at'
      },
      throwOnError: true
    }),
  });

  // 2. Create Mutation
  const createMutation = useMutation({
    mutationFn: (newConfig: unknown) => createSystemConfigApiV1SystemConfigsPost({ body: newConfig as SystemConfigCreate, throwOnError: true }),
    onSuccess: () => {
      message.success('System Configuration registered successfully!');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
      setIsDrawerVisible(false);
    },
    onError: (err: unknown) => {
      message.error(`Create failed: ${(err as { message?: string }).message}`);
    }
  });

  // 3. Update Mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: unknown }) => 
      patchSystemConfigApiV1SystemConfigsSystemConfigIdPatch({ 
        path: { system_config_id: id }, 
        body: data as SystemConfigPatch, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('System Configuration saved successfully!');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
      setIsDrawerVisible(false);
      setEditingConfig(null);
    },
    onError: (err: unknown) => {
      message.error(`Save failed: ${(err as { message?: string }).message}`);
    }
  });

  // 4. Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => 
      deleteSystemConfigApiV1SystemConfigsSystemConfigIdDelete({ 
        path: { system_config_id: id }, 
        throwOnError: true 
      }),
    onSuccess: () => {
      message.success('Configuration deleted');
      queryClient.invalidateQueries({ queryKey: ['systemConfigs'] });
    },
    onError: (err: unknown) => {
      message.error(`Delete failed: ${(err as { message?: string }).message}`);
    }
  });

  const handleOpenCreate = () => {
    setEditingConfig(null);
    setIsDrawerVisible(true);
  };

  const handleOpenEdit = (record: SystemConfigRecord) => {
    setEditingConfig(record);
    setIsDrawerVisible(true);
  };

  const handleFormSubmit = (values: Record<string, unknown>) => {
    let data = {};
    if (values.data) {
      try {
        data = JSON.parse(values.data as string);
      } catch {
        message.error('Data must be a valid JSON string!');
        return;
      }
    }

    const payload: Record<string, unknown> = {
      name: values.name as string,
      data
    };

    if (editingConfig) {
      updateMutation.mutate({ id: editingConfig.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const configs = (systemConfigsData?.data?.items || []) as SystemConfigRecord[];
  const totalCount = systemConfigsData?.data?.total_count || 0;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <ConfigHeader
        currentInput={currentInput}
        setCurrentInput={setCurrentInput}
        setConfirmedFilter={setConfirmedFilter}
        setPage={setPage}
        refetch={refetch}
        handleOpenCreate={handleOpenCreate}
      />

      <ConfigCardGrid
        configs={configs}
        isLoading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={totalCount}
        setPage={setPage}
        setPageSize={setPageSize}
        confirmedFilter={confirmedFilter}
        setCurrentInput={setCurrentInput}
        onOpenEdit={handleOpenEdit}
        onDelete={(id) => deleteMutation.mutate(id)}
      />

      <SystemConfigDrawer
        isDrawerVisible={isDrawerVisible}
        onClose={() => {
          setIsDrawerVisible(false);
          setEditingConfig(null);
        }}
        editingConfig={editingConfig}
        onSubmit={handleFormSubmit}
        isPending={createMutation.isPending || updateMutation.isPending}
      />
    </Space>
  );
};
