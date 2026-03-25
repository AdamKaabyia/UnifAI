import { useQuery } from '@tanstack/react-query';
import { checkServicesHealth, ServiceHealth } from '@/api/health';

/**
 * Polling interval for health checks in milliseconds.
 * Checks every 60 seconds as requested.
 */
const HEALTH_CHECK_INTERVAL_MS = 60_000;

/**
 * Return type for the useRemoteServicesHealth hook
 */
export interface UseServicesHealthResult {
    /** Health status of the Docling service */
    docling: ServiceHealth | null;
    /** Health status of the Embedding service */
    embedding: ServiceHealth | null;
    /** Whether document upload should be enabled (both services healthy or local) */
    uploadEnabled: boolean;
    /** Whether the initial health check is still loading */
    isLoading: boolean;
    /** Error message if health check failed */
    error: string | null;
    /** Manually trigger a health check refresh */
    refresh: () => Promise<void>;
    /** Whether a health check refresh is in progress */
    isRefetching: boolean;
}

/**
 * Hook to poll for service health status using React Query.
 * 
 * Polls every 10 seconds while the component is mounted.
 * Automatically stops polling when the component unmounts.
 * Preserves last known state on transient fetch errors to avoid
 * false-negative disabling of uploads when only the backend is briefly unreachable.
 * 
 * @example
 * ```tsx
 * function DocumentsPage() {
 *     const { uploadEnabled, docling, embedding } = useRemoteServicesHealth();
 *     
 *     return (
 *         <Button disabled={!uploadEnabled}>
 *             Upload Document
 *         </Button>
 *     );
 * }
 * ```
 * 
 * @returns UseServicesHealthResult with health status and controls
 */
export function useRemoteServicesHealth(): UseServicesHealthResult {
    const { data, isLoading, isFetching, error, refetch } = useQuery({
        queryKey: ['services-health'],
        queryFn: checkServicesHealth,
        refetchInterval: HEALTH_CHECK_INTERVAL_MS,
        // Keep previous data while refetching — prevents flicker and avoids
        // false-negative when backend is briefly unreachable
        placeholderData: (previousData) => previousData,
        retry: 2,
        staleTime: HEALTH_CHECK_INTERVAL_MS / 2,
    });

    return {
        docling: data?.docling ?? null,
        embedding: data?.embedding ?? null,
        uploadEnabled: data?.upload_enabled ?? true,
        isLoading,
        error: error ? 'Failed to check services health' : null,
        refresh: async () => { await refetch(); },
        isRefetching: isFetching,
    };
}
