/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SystemConfigRead } from './SystemConfigRead';
export type PaginatedList_SystemConfigRead_ = {
    items: Array<SystemConfigRead>;
    total_count?: (number | null);
    offset?: number;
    limit?: (number | null);
    /**
     * Check if the current page is the last page
     */
    readonly last: (boolean | null);
    readonly first: boolean;
};

