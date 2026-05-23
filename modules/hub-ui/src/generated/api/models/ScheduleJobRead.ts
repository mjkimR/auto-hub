/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ScheduleJobStatus } from './ScheduleJobStatus';
export type ScheduleJobRead = {
    /**
     * The name of the schedule job.
     */
    name: string;
    /**
     * Reference to the schedule config that triggered this job execution.
     */
    schedule_config_id?: (string | null);
    /**
     * Reference to the dispatcher run that executed this job. Allows grouping multiple schedule jobs under a single dispatcher run for better traceability.
     */
    dispatcher_run_id?: (string | null);
    /**
     * Execution status of the schedule.
     */
    status: ScheduleJobStatus;
    /**
     * Timestamp when the task execution started.
     */
    started_at: string;
    /**
     * Timestamp when the task execution finished.
     */
    finished_at?: (string | null);
    /**
     * Snapshot of the payload used during execution.
     */
    payload?: Record<string, any>;
    /**
     * Error message if the task execution failed.
     */
    error_message?: (string | null);
    created_at: string;
    updated_at: string;
    id: string;
};

