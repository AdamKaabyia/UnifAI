import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FaExclamationCircle } from "react-icons/fa";
import { cn } from "@/lib/utils";

interface ErrorDisplayProps {
  /** The error message to display */
  errorMessage: string;
  /** Optional title for the error (defaults to "Error") */
  title?: string;
  /** Optional retry callback function */
  onRetry?: () => void;
  /** Optional retry button label (defaults to "Retry") */
  retryLabel?: string;
  /** Optional: when true, disables retry button and shows loading state */
  isRetrying?: boolean;
  /** Optional custom className for the container */
  className?: string;
  /** Optional custom className for the card */
  cardClassName?: string;
  /** Optional custom className for the title */
  titleClassName?: string;
  /** Optional custom className for the message */
  messageClassName?: string;
  /** Optional custom className for the retry button */
  buttonClassName?: string;
  /** Variant: 'full-page' centers content, 'inline' for inline display */
  variant?: 'full-page' | 'inline';
}

/**
 * Generic ErrorDisplay component for visualizing errors across the app.
 * Supports dynamic CSS styling to align with different page designs.
 * 
 * @example
 * ```tsx
 * <ErrorDisplay 
 *   errorMessage="Failed to load data"
 *   title="Error Loading Data"
 *   onRetry={refetch}
 *   className="my-custom-class"
 * />
 * ```
 */
export function ErrorDisplay({ 
  errorMessage,
  title = "Error",
  onRetry,
  retryLabel = "Retry",
  isRetrying = false,
  className,
  cardClassName,
  titleClassName,
  messageClassName,
  buttonClassName,
  variant = 'full-page',
}: ErrorDisplayProps) {
  const containerClasses = cn(
    variant === 'full-page' && "p-6 flex items-center justify-center h-full",
    variant === 'inline' && "w-full",
    className
  );

  const cardClasses = cn(
    "bg-background-card shadow-card border-gray-800",
    variant === 'full-page' && "p-6 max-w-md",
    variant === 'inline' && "p-4",
    cardClassName
  );

  return (
    <div className={containerClasses}>
      <Card className={cardClasses}>
        <div className="text-center">
          <FaExclamationCircle className="text-4xl text-error mx-auto mb-4" />
          <h3 className={cn(
            "font-heading font-semibold mb-2",
            variant === 'full-page' ? "text-lg" : "text-base",
            titleClassName
          )}>
            {title}
          </h3>
          <p className={cn(
            "text-sm text-gray-400 mb-4",
            messageClassName
          )}>
            {errorMessage}
          </p>
          {onRetry && (
            <Button 
              onClick={onRetry} 
              disabled={isRetrying}
              className={cn(
                "px-4 py-2 bg-primary hover:bg-opacity-80 rounded-md text-sm font-medium transition-colors",
                buttonClassName
              )}
            >
              {isRetrying ? "Checking..." : retryLabel}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

