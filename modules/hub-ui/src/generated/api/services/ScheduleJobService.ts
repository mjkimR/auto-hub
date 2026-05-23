/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeleteResponse } from '../models/DeleteResponse';
import type { PaginatedList_ScheduleJobRead_ } from '../models/PaginatedList_ScheduleJobRead_';
import type { ScheduleJobCreate } from '../models/ScheduleJobCreate';
import type { ScheduleJobPatch } from '../models/ScheduleJobPatch';
import type { ScheduleJobPut } from '../models/ScheduleJobPut';
import type { ScheduleJobRead } from '../models/ScheduleJobRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ScheduleJobService {
    /**
     * Create Schedule Job
     * @param requestBody
     * @returns ScheduleJobRead Successful Response
     * @throws ApiError
     */
    public static createScheduleJobApiV1ScheduleJobsPost(
        requestBody: ScheduleJobCreate,
    ): CancelablePromise<ScheduleJobRead> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/schedule_jobs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Schedule Jobs
     * @param offset offset for pagination
     * @param limit limit for pagination
     * @returns PaginatedList_ScheduleJobRead_ Successful Response
     * @throws ApiError
     */
    public static getScheduleJobsApiV1ScheduleJobsGet(
        offset?: number,
        limit: number = 100,
    ): CancelablePromise<PaginatedList_ScheduleJobRead_> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/schedule_jobs',
            query: {
                'offset': offset,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Schedule Job
     * @param scheduleJobId
     * @returns ScheduleJobRead Successful Response
     * @throws ApiError
     */
    public static getScheduleJobApiV1ScheduleJobsScheduleJobIdGet(
        scheduleJobId: string,
    ): CancelablePromise<ScheduleJobRead> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/schedule_jobs/{schedule_job_id}',
            path: {
                'schedule_job_id': scheduleJobId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Patch Schedule Job
     * @param scheduleJobId
     * @param requestBody
     * @returns ScheduleJobRead Successful Response
     * @throws ApiError
     */
    public static patchScheduleJobApiV1ScheduleJobsScheduleJobIdPatch(
        scheduleJobId: string,
        requestBody: ScheduleJobPatch,
    ): CancelablePromise<ScheduleJobRead> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/schedule_jobs/{schedule_job_id}',
            path: {
                'schedule_job_id': scheduleJobId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Put Schedule Job
     * @param scheduleJobId
     * @param requestBody
     * @returns ScheduleJobRead Successful Response
     * @throws ApiError
     */
    public static putScheduleJobApiV1ScheduleJobsScheduleJobIdPut(
        scheduleJobId: string,
        requestBody: ScheduleJobPut,
    ): CancelablePromise<ScheduleJobRead> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/schedule_jobs/{schedule_job_id}',
            path: {
                'schedule_job_id': scheduleJobId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Schedule Job
     * @param scheduleJobId
     * @returns DeleteResponse Successful Response
     * @throws ApiError
     */
    public static deleteScheduleJobApiV1ScheduleJobsScheduleJobIdDelete(
        scheduleJobId: string,
    ): CancelablePromise<DeleteResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/schedule_jobs/{schedule_job_id}',
            path: {
                'schedule_job_id': scheduleJobId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
