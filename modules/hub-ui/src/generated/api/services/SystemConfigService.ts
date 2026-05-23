/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeleteResponse } from '../models/DeleteResponse';
import type { PaginatedList_SystemConfigRead_ } from '../models/PaginatedList_SystemConfigRead_';
import type { SystemConfigCreate } from '../models/SystemConfigCreate';
import type { SystemConfigPatch } from '../models/SystemConfigPatch';
import type { SystemConfigPut } from '../models/SystemConfigPut';
import type { SystemConfigRead } from '../models/SystemConfigRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SystemConfigService {
    /**
     * Create System Config
     * @param requestBody
     * @returns SystemConfigRead Successful Response
     * @throws ApiError
     */
    public static createSystemConfigApiV1SystemConfigsPost(
        requestBody: SystemConfigCreate,
    ): CancelablePromise<SystemConfigRead> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/system_configs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get System Configs
     * @param offset offset for pagination
     * @param limit limit for pagination
     * @returns PaginatedList_SystemConfigRead_ Successful Response
     * @throws ApiError
     */
    public static getSystemConfigsApiV1SystemConfigsGet(
        offset?: number,
        limit: number = 100,
    ): CancelablePromise<PaginatedList_SystemConfigRead_> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/system_configs',
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
     * Get System Config
     * @param systemConfigId
     * @returns SystemConfigRead Successful Response
     * @throws ApiError
     */
    public static getSystemConfigApiV1SystemConfigsSystemConfigIdGet(
        systemConfigId: string,
    ): CancelablePromise<SystemConfigRead> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/system_configs/{system_config_id}',
            path: {
                'system_config_id': systemConfigId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Patch System Config
     * @param systemConfigId
     * @param requestBody
     * @returns SystemConfigRead Successful Response
     * @throws ApiError
     */
    public static patchSystemConfigApiV1SystemConfigsSystemConfigIdPatch(
        systemConfigId: string,
        requestBody: SystemConfigPatch,
    ): CancelablePromise<SystemConfigRead> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/system_configs/{system_config_id}',
            path: {
                'system_config_id': systemConfigId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Put System Config
     * @param systemConfigId
     * @param requestBody
     * @returns SystemConfigRead Successful Response
     * @throws ApiError
     */
    public static putSystemConfigApiV1SystemConfigsSystemConfigIdPut(
        systemConfigId: string,
        requestBody: SystemConfigPut,
    ): CancelablePromise<SystemConfigRead> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/system_configs/{system_config_id}',
            path: {
                'system_config_id': systemConfigId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete System Config
     * @param systemConfigId
     * @returns DeleteResponse Successful Response
     * @throws ApiError
     */
    public static deleteSystemConfigApiV1SystemConfigsSystemConfigIdDelete(
        systemConfigId: string,
    ): CancelablePromise<DeleteResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/system_configs/{system_config_id}',
            path: {
                'system_config_id': systemConfigId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
