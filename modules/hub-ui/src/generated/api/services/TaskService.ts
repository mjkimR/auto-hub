/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TaskSpecResponse } from '../models/TaskSpecResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TaskService {
    /**
     * Get Task Specs
     * Retrieve all registered task specifications.
     * @returns TaskSpecResponse Successful Response
     * @throws ApiError
     */
    public static getTaskSpecsApiV1TasksSpecsGet(): CancelablePromise<Array<TaskSpecResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/tasks/specs',
        });
    }
}
