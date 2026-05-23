/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeleteResponse } from '../models/DeleteResponse';
import type { PaginatedList_ScheduleConfigRead_ } from '../models/PaginatedList_ScheduleConfigRead_';
import type { ScheduleConfigCreate } from '../models/ScheduleConfigCreate';
import type { ScheduleConfigPatch } from '../models/ScheduleConfigPatch';
import type { ScheduleConfigPut } from '../models/ScheduleConfigPut';
import type { ScheduleConfigRead } from '../models/ScheduleConfigRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ScheduleConfigService {
    /**
     * Create Schedule Config
     * @param requestBody
     * @returns ScheduleConfigRead Successful Response
     * @throws ApiError
     */
    public static createScheduleConfigApiV1ScheduleConfigsPost(
        requestBody: ScheduleConfigCreate,
    ): CancelablePromise<ScheduleConfigRead> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/schedule_configs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Schedule Configs
     * @param offset offset for pagination
     * @param limit limit for pagination
     * @returns PaginatedList_ScheduleConfigRead_ Successful Response
     * @throws ApiError
     */
    public static getScheduleConfigsApiV1ScheduleConfigsGet(
        offset?: number,
        limit: number = 100,
    ): CancelablePromise<PaginatedList_ScheduleConfigRead_> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/schedule_configs',
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
     * Get Schedule Config
     * @param scheduleConfigId
     * @returns ScheduleConfigRead Successful Response
     * @throws ApiError
     */
    public static getScheduleConfigApiV1ScheduleConfigsScheduleConfigIdGet(
        scheduleConfigId: string,
    ): CancelablePromise<ScheduleConfigRead> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/schedule_configs/{schedule_config_id}',
            path: {
                'schedule_config_id': scheduleConfigId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Patch Schedule Config
     * @param scheduleConfigId
     * @param requestBody
     * @returns ScheduleConfigRead Successful Response
     * @throws ApiError
     */
    public static patchScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPatch(
        scheduleConfigId: string,
        requestBody: ScheduleConfigPatch,
    ): CancelablePromise<ScheduleConfigRead> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/schedule_configs/{schedule_config_id}',
            path: {
                'schedule_config_id': scheduleConfigId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Put Schedule Config
     * @param scheduleConfigId
     * @param requestBody
     * @returns ScheduleConfigRead Successful Response
     * @throws ApiError
     */
    public static putScheduleConfigApiV1ScheduleConfigsScheduleConfigIdPut(
        scheduleConfigId: string,
        requestBody: ScheduleConfigPut,
    ): CancelablePromise<ScheduleConfigRead> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/schedule_configs/{schedule_config_id}',
            path: {
                'schedule_config_id': scheduleConfigId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Schedule Config
     * @param scheduleConfigId
     * @returns DeleteResponse Successful Response
     * @throws ApiError
     */
    public static deleteScheduleConfigApiV1ScheduleConfigsScheduleConfigIdDelete(
        scheduleConfigId: string,
    ): CancelablePromise<DeleteResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/schedule_configs/{schedule_config_id}',
            path: {
                'schedule_config_id': scheduleConfigId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
