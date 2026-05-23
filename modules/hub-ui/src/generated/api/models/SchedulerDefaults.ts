/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SchedulerDefaults = {
    /**
     * Default global timeout for scheduled tasks in seconds
     */
    GLOBAL_TIMEOUT_SECONDS?: number;
    /**
     * Buffer time to subtract from the global timeout to ensure tasks complete within limits in seconds
     */
    GLOBAL_TIMEOUT_BUFFER?: number;
    /**
     * Maximum number of concurrent tasks that can be scheduled
     */
    MAX_CONCURRENT_TASKS?: number;
    /**
     * Maximum number of retry attempts for failed tasks
     */
    MAX_RETRY_ATTEMPTS?: number;
    /**
     * Maximum number of schedules or retry jobs to fetch in a single tick
     */
    MAX_DISPATCH_LIMIT?: number;
};

