/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ScheduleConfigCreate = {
    /**
     * Human-readable name of the schedule.
     */
    name: string;
    /**
     * Optional description of what this schedule does.
     */
    description?: (string | null);
    /**
     * Dotted path to the task function to execute (e.g. 'tasks.send_report').
     */
    task_func: string;
    /**
     * Cron expression for time-based scheduling (e.g. '0 9 * * 1-5'). Mutually exclusive with interval_seconds.
     */
    cron_expression?: (string | null);
    /**
     * Fixed interval in seconds between executions. Mutually exclusive with cron_expression.
     */
    interval_seconds?: (number | null);
    /**
     * Arbitrary JSON payload passed to the task function as kwargs.
     */
    payload?: Record<string, any>;
    /**
     * Whether this schedule is active and should be picked up by the dispatcher.
     */
    enabled?: boolean;
    /**
     * Optional datetime after which the schedule becomes active.
     */
    start_at?: (string | null);
    /**
     * Optional datetime after which the schedule is no longer executed.
     */
    end_at?: (string | null);
};

