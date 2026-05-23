/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DeleteResponse = {
    success?: boolean;
    message?: (string | null);
    /**
     * The identity of the deleted object.
     */
    identity?: (string | number | null);
    /**
     * The string representation of the deleted object.
     */
    representation?: (string | null);
    /**
     * Additional metadata about the delete operation.
     */
    meta?: Record<string, any>;
};

