/**
 * Analytics Helper Utilities
 * 
 * Shared functions for analytics data transformations and calculations.
 * Note: The backend now handles all time-range filtering, so client-side
 * recomputation is no longer needed.
 */

import type { TimeRange } from "@/types/systemStats";

/**
 * Truncate user ID for display
 */
export function truncateUserId(userId: string, maxLength: number = 12): string {
  return userId.length > maxLength ? userId.substring(0, maxLength) + '...' : userId;
}

/**
 * Format duration in seconds to human-readable string (e.g., "45s", "2m 30s")
 */
export function formatDuration(seconds?: number): string {
  if (seconds === undefined || seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

/**
 * Get CSS class for success rate color coding
 */
export function getSuccessRateColor(rate: number): string {
  if (rate >= 90) return "text-green-500";
  if (rate >= 70) return "text-yellow-500";
  return "text-red-500";
}

/**
 * Shared Recharts tooltip styles for all analytics charts.
 * Keeps chart styling consistent across StatusBreakdown, TopUsers, and WorkflowExecution charts.
 */
export const CHART_TOOLTIP_CONTENT_STYLE = {
  backgroundColor: '#374151',
  border: '1px solid #6B7280',
  borderRadius: '0.375rem',
};

export const CHART_TOOLTIP_LABEL_STYLE = {
  color: '#F9FAFB',
};

/**
 * Return a human-readable suffix for the given time range.
 * Compose with a prefix like "Workflow Executions" or "Other Statistic" to build titles.
 */
export function getTimeRangeSuffix(range: TimeRange): string {
  switch (range) {
    case 'today':
      return 'Today (by Hour)';
    case '7days':
      return '(Last 7 Days)';
    case '30days':
      return '(Last 30 Days)';
    case 'all':
      return '(All Time by Month)';
    default:
      return 'Over Time';
  }
}

/**
 * Format an ISO datetime period string into a display-friendly label
 * based on the active time range.
 *
 * The backend sends ISO datetime strings (e.g., "2024-01-15T14:00:00Z")
 * truncated to the appropriate granularity bucket.
 *
 * - "today"  : "2024-01-15T14:00:00Z" → "2:00 PM"
 * - "all"    : "2024-01-01T00:00:00Z" → "Jan 2024"
 * - default  : "2024-01-15T00:00:00Z" → "Jan 15"
 */
export function formatPeriodLabel(period: string, range: string): string {
  if (!period) return '';

  try {
    const date = new Date(period);
    if (isNaN(date.getTime())) return period;

    if (range === 'today') {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    } else if (range === 'all') {
      return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  } catch {
    return period;
  }
}

