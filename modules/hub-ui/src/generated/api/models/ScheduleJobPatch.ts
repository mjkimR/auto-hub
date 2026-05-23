/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ScheduleJobStatus } from './ScheduleJobStatus';
export type ScheduleJobPatch = {
    /**
     * The name of the schedule job.
     */
    name?: (string | null);
    /**
     * Reference to the schedule config.
     */
    schedule_config_id?: (string | null);
    /**
     * Reference to the dispatcher run.
     */
    dispatcher_run_id?: (string | null);
    /**
     * Execution status of the schedule.
     */
    status?: (ScheduleJobStatus | null);
    /**
     * Timestamp when the task execution started.
     */
    started_at?: (string | null);
    /**
     * Timestamp when the task execution finished.
     */
    finished_at?: (string | null);
    /**
     * Snapshot of the payload used during execution.
     */
    payload?: (Record<string, any> | null);
    /**
     * Error message if the task execution failed.
     */
    error_message?: (string | null);
};

