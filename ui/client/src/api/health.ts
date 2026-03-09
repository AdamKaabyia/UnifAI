import { api } from '@/http/queryClient';

/**
 * Health status for a single service
 */
export interface ServiceHealth {
    status: 'healthy' | 'unhealthy' | 'local';
    mode: 'remote' | 'local';
    message: string;
}

/**
 * Response from the service readiness endpoint
 */
export interface ServicesHealthResponse {
    docling: ServiceHealth;
    embedding: ServiceHealth;
    upload_enabled: boolean;
}

/**
 * Check health of Docling and Embedding services.
 * 
 * Returns the health status of each service separately,
 * plus a combined `upload_enabled` flag indicating if
 * document upload should be allowed.
 * 
 * @returns Promise with services health status
 */
export async function checkServicesHealth(): Promise<ServicesHealthResponse> {
    const response = await api.get<ServicesHealthResponse>('health/service.readiness.get');
    return response.data;
}
