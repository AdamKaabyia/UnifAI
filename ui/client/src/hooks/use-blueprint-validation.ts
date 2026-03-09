import { useState, useCallback, useRef } from 'react';
import { BlueprintValidationResult, ElementValidationResult } from '@/types/validation';
import { useToast } from '@/hooks/use-toast';
import { useAgenticAI } from '@/contexts/AgenticAIContext';

export interface UseBlueprintValidationOptions {
  /** The currently selected blueprint ID. Kept in sync with
   *  latestBlueprintIdRef during render so that stale promise
   *  continuations that resolve between a render and its effects
   *  are immediately rejected. */
  activeBlueprintId?: string | null;
  /** Callback when validation state changes */
  onValidationChange?: (isValid: boolean, validationResult: BlueprintValidationResult | null, isValidating: boolean) => void;
  /** Whether to show toast notifications on validation failure */
  showToastOnFailure?: boolean;
  /** Whether to skip caching and always call the API (useful for force-refresh scenarios) */
  skipCache?: boolean;
}

export interface UseBlueprintValidationResult {
  /** Whether validation is currently in progress */
  isValidating: boolean;
  /** Validation results by element ID */
  validationResults: Record<string, ElementValidationResult>;
  /** Whether the current blueprint is valid */
  isValid: boolean;
  /** Function to validate a blueprint by ID */
  validateBlueprint: (blueprintId: string) => Promise<void>;
  /** Function to clear validation state */
  clearValidation: () => void;
}

/**
 * Hook to manage blueprint validation state and logic.
 * Uses AgenticAIContext for caching - valid blueprints are cached for 60 minutes.
 * Used by components that need to validate blueprints and display validation results.
 */
export function useBlueprintValidation(
  options: UseBlueprintValidationOptions = {}
): UseBlueprintValidationResult {
  const { 
    activeBlueprintId,
    onValidationChange, 
    showToastOnFailure = true,
    skipCache = false,
  } = options;
  
  const { toast } = useToast();
  const { validateBlueprintWithCache, isBlueprintValidationCacheHit } = useAgenticAI();
  
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationResults, setValidationResults] = useState<Record<string, ElementValidationResult>>({});
  const [isValid, setIsValid] = useState<boolean>(true);

  // Track the latest requested blueprintId so stale responses are discarded.
  const latestBlueprintIdRef = useRef<string | null>(null);

  // Synchronize the ref with the caller's active blueprint during render.
  // This is critical: useEffect runs AFTER render, but stale promise
  // continuations can resolve BETWEEN a render and its effects. Without
  // this, a response for the previous blueprint could slip through the
  // latestBlueprintIdRef guard and briefly apply invalid state to the
  // newly-selected blueprint.
  if (activeBlueprintId !== undefined) {
    latestBlueprintIdRef.current = activeBlueprintId;
  }

  const clearValidation = useCallback(() => {
    latestBlueprintIdRef.current = null;
    setValidationResults({});
    setIsValid(true);
    setIsValidating(false);
    onValidationChange?.(true, null, false);
  }, [onValidationChange]);

  const validate = useCallback(async (blueprintId: string) => {
    // Mark this blueprintId as the one we care about; any in-flight request
    // for a different id will be ignored when its response arrives.
    latestBlueprintIdRef.current = blueprintId;

    // Check if we have a cache hit (valid result within TTL)
    const isCacheHit = !skipCache && isBlueprintValidationCacheHit(blueprintId);
    
    // Always clear stale results from the previous flow to prevent them
    // from leaking into the UI while the new result (cached or not) resolves.
    setValidationResults({});
    setIsValid(true);

    if (!isCacheHit) {
      setIsValidating(true);
      onValidationChange?.(true, null, true);
    } else {
      onValidationChange?.(true, null, false);
    }
    
    try {
      // Return cached result if valid and within 60 minutes (unless skipCache is true)
      // validateBlueprintWithCache handles all caching internally (both blueprint-level and element-level)
      const result = await validateBlueprintWithCache({ blueprintId }, skipCache);

      // Discard result if user switched to a different blueprint while we were waiting
      if (latestBlueprintIdRef.current !== blueprintId) return;

      setValidationResults(result.element_results || {});
      setIsValid(result.is_valid);
      
      // Notify parent of validation result
      onValidationChange?.(result.is_valid, result, false);
      
      // Show toast if validation failed
      if (!result.is_valid && showToastOnFailure) {
        const errorCount = Object.values(result.element_results).filter(r => !r.is_valid).length;
        toast({
          title: "Workflow Validation Failed",
          description: `${errorCount} element${errorCount !== 1 ? 's' : ''} failed validation.`,
          variant: "destructive",
        });
      }
    } catch (error) {
      // Discard error if user already moved on to a different blueprint
      if (latestBlueprintIdRef.current !== blueprintId) return;

      console.error("Error validating blueprint:", error);
      setIsValid(false);
      
      // Notify parent that validation failed
      onValidationChange?.(false, null, false);
      
      if (showToastOnFailure) {
        toast({
          title: "Validation Error",
          description: "Failed to validate the workflow. Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      // Only clear the loading spinner if this is still the active request
      if (latestBlueprintIdRef.current === blueprintId) {
        setIsValidating(false);
      }
    }
  }, [
    skipCache,
    isBlueprintValidationCacheHit,
    validateBlueprintWithCache,
    onValidationChange, 
    showToastOnFailure, 
    toast,
  ]);

  return {
    isValidating,
    validationResults,
    isValid,
    validateBlueprint: validate,
    clearValidation,
  };
}

