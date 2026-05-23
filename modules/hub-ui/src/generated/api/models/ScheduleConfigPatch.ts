/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScheduleConfigPatch = {
    /**
     * Human-readable name of the schedule.
     */
    name?: (string | null);
    /**
     * Optional description of what this schedule does.
     */
    description?: (string | null);
    /**
     * Dotted path to the task function to execute.
     */
    task_func?: (string | null);
    /**
     * Cron expression for time-based scheduling.
     */
    cron_expression?: (string | null);
    /**
     * Fixed interval in seconds between executions.
     */
    interval_seconds?: (number | null);
    /**
     * Arbitrary JSON payload passed to the task function as kwargs.
     */
    payload?: (Record<string, any> | null);
    /**
     * Whether this schedule is active.
     */
    enabled?: (boolean | null);
    /**
     * Optional datetime after which the schedule becomes active.
     */
    start_at?: (string | null);
    /**
     * Optional datetime after which the schedule is no longer executed.
     */
    end_at?: (string | null);
};

