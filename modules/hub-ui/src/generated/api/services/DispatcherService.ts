/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DispatchResponse } from '../models/DispatchResponse';
import type { SchedulerDefaults } from '../models/SchedulerDefaults';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DispatcherService {
    /**
     * Trigger Dispatch
     * Called by an external trigger such as Google Cloud Scheduler.
     * Processes due schedules using FOR UPDATE SKIP LOCKED to prevent duplicate execution.
     * @param requestBody
     * @returns DispatchResponse Successful Response
     * @throws ApiError
     */
    public static triggerDispatchApiV1DispatchersTriggerPost(
        requestBody?: (SchedulerDefaults | null),
    ): CancelablePromise<DispatchResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/dispatchers/trigger',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
