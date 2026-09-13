<script lang="ts">
	import { session } from '$lib/stores/session.svelte';
	import AppShell from '$lib/components/shared/AppShell.svelte';
	import LoginView from '$lib/components/views/LoginView.svelte';
	import DashboardView from '$lib/components/views/DashboardView.svelte';
	import ProjectsView from '$lib/components/views/ProjectsView.svelte';
	import PipelineRunsView from '$lib/components/views/PipelineRunsView.svelte';
	import ScheduleConfigsView from '$lib/components/views/ScheduleConfigsView.svelte';
	import ScheduleJobsView from '$lib/components/views/ScheduleJobsView.svelte';
	import SystemConfigsView from '$lib/components/views/SystemConfigsView.svelte';
	import TaskSpecsView from '$lib/components/views/TaskSpecsView.svelte';
	import ConnectorsView from '$lib/components/views/ConnectorsView.svelte';
</script>

{#if session.isAuthenticated}
	<AppShell>
		{#if session.activeTab === 'projects'}
			<ProjectsView />
		{:else if session.activeTab === 'connectors'}
			<ConnectorsView />
		{:else if session.activeTab === 'pipeline-runs'}
			<PipelineRunsView />
		{:else if session.activeTab === 'configs'}
			<ScheduleConfigsView />
		{:else if session.activeTab === 'jobs'}
			<ScheduleJobsView />
		{:else if session.activeTab === 'system'}
			<SystemConfigsView />
		{:else if session.activeTab === 'specs'}
			<TaskSpecsView />
		{:else}
			<DashboardView />
		{/if}
	</AppShell>
{:else}
	<LoginView />
{/if}
