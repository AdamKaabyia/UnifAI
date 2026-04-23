
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Badge } from "@/components/ui/badge";
import { CheckCircle, XCircle, Loader2, Lock, LogIn } from 'lucide-react';
import axios from "../../../http/axiosAgentConfig";
import { useAuth } from "@/contexts/AuthContext";


// Type guard to check if hint is an ApiHint (has endpoint) vs ActionHint (has action_uid)
const isApiHint = (hint: any): boolean => {
  return hint && typeof hint.endpoint === 'string' && hint.endpoint.length > 0;
};

// Per-item validation result for list fields
export interface ItemValidationResult {
  rid: string;
  isValid: boolean;
  message?: string;
}

interface FieldValidationProps {
  fieldName: string;
  fieldValue: any;
  validationHint: any;
  elementActions: any[];
  selectedElementType: any;
  isRequired?: boolean;
  /** All current config field values, used to resolve dependencies for validation actions */
  configValues?: Record<string, any>;
  onValidationChange: (fieldName: string, isValid: boolean, itemResults?: ItemValidationResult[]) => void;
  onInputChange?: (field: string, value: any) => void;
}

// Auth-related response statuses
const AUTH_STATUSES = new Set([
  'authenticated', 'requires_consent', 'expired',
  'not_configured', 'needs_client_registration',
]);

export const FieldValidation: React.FC<FieldValidationProps> = ({
  fieldName,
  fieldValue,
  validationHint,
  elementActions,
  selectedElementType,
  isRequired = false,
  configValues = {},
  onValidationChange,
  onInputChange,
}) => {
  const { user } = useAuth();
  const userId = user?.username || "";

  const [validationState, setValidationState] = useState<{
    isValidating: boolean;
    isValid: boolean | null;
    message: string;
  }>({
    isValidating: false,
    isValid: null,
    message: ''
  });

  // Auth-specific state
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<string | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);

  const validationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastValidatedKeyRef = useRef<string | null>(null);
  const popupRef = useRef<Window | null>(null);

  // Determine if this is an ApiHint or ActionHint
  const useApiHint = isApiHint(validationHint);

  // Find the validation action from elementActions (only needed for ActionHint)
  const validationAction = !useApiHint 
    ? elementActions.find(action => action.uid === validationHint.action_uid)
    : null;

  const validationKey = React.useMemo(() => {
    const dependencyValues: Record<string, any> = {};
    if (validationHint?.dependencies) {
      Object.keys(validationHint.dependencies).forEach((configField) => {
        if (configField !== fieldName) {
          dependencyValues[configField] = configValues[configField];
        }
      });
    }
    
    return JSON.stringify({
      fieldValue,
      dependencies: dependencyValues
    });
  }, [fieldValue, validationHint?.dependencies, fieldName, configValues]);

  const buildInputWithDependencies = (value: any, fieldNameMapping?: string): Record<string, any> => {
    const inputData: Record<string, any> = {};
    
    const targetFieldName = fieldNameMapping || fieldName;
    inputData[targetFieldName] = value;
    
    if (validationHint.dependencies && Object.keys(validationHint.dependencies).length > 0) {
      Object.entries(validationHint.dependencies).forEach(([configField, actionField]) => {
        if (configField === fieldName) {
          return;
        }
        
        const dependencyValue = configValues[configField];
        if (dependencyValue !== undefined) {
          inputData[actionField as string] = dependencyValue;
        }
      });
    }
    
    return inputData;
  };

  const performActionValidation = async (value: any) => {
    if (!validationAction) {
      return { success: false, message: 'Validation action not found' };
    }

    let fieldNameMapping: string | undefined;
    
    if (validationHint.dependencies?.[fieldName]) {
      fieldNameMapping = validationHint.dependencies[fieldName];
    } else if (!validationAction.input_schema?.properties?.[fieldName]) {
      const inputProperties = validationAction.input_schema?.properties || {};
      const inputKeys = Object.keys(inputProperties);
      
      const requiredFields = validationAction.input_schema?.required || [];
      fieldNameMapping = requiredFields.length > 0 ? requiredFields[0] : inputKeys[0];
    }

    const inputData = buildInputWithDependencies(value, fieldNameMapping);

    const response = await axios.post('/actions/action.execute', {
      uid: validationAction.uid,
      inputData,
      userId,
    });

    return response.data;
  };

  const performApiValidation = async (value: any) => {
    const fieldNameMapping = validationHint.dependencies?.[fieldName] || fieldName;
    
    const requestBody = buildInputWithDependencies(value, fieldNameMapping);

    const method = (validationHint.method || 'POST').toUpperCase();
    const endpoint = validationHint.endpoint;

    let response;
    if (method === 'GET') {
      response = await axios.get(endpoint, { params: requestBody });
    } else {
      response = await axios({
        method: method.toLowerCase(),
        url: endpoint,
        data: requestBody
      });
    }

    return response.data;
  };

  const performValidation = async (value: any) => {
    if (!useApiHint && !validationAction) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      onValidationChange(fieldName, false);
      return;
    }

    if (useApiHint && !validationHint.endpoint) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      onValidationChange(fieldName, false);
      return;
    }

    if (!value || value === '' || (Array.isArray(value) && value.length === 0)) {
      setValidationState({ isValidating: false, isValid: null, message: '' });
      setAuthUrl(null);
      setAuthStatus(null);
      onValidationChange(fieldName, !isRequired);
      return;
    }

    if (lastValidatedKeyRef.current === validationKey) {
      return;
    }

    setValidationState(prev => ({ ...prev, isValidating: true }));

    try {
      const responseData = useApiHint 
        ? await performApiValidation(value)
        : await performActionValidation(value);

      const fieldMapping = validationHint.field_mapping || 'success';

      if (onInputChange && responseData.server_identifier) {
        onInputChange('server_identifier', responseData.server_identifier);
      }

      // ── Auth-aware response handling ──
      if (responseData.status && AUTH_STATUSES.has(responseData.status)) {
        lastValidatedKeyRef.current = validationKey;
        handleAuthResponse(responseData);
        return;
      }
      
      // ── Standard validation handling ──
      if (Array.isArray(responseData)) {
        const itemResults: ItemValidationResult[] = responseData.map((item: any) => ({
          rid: item.element_rid || '',
          isValid: item[fieldMapping] === true,
          message: item.messages?.[0]?.message || (item[fieldMapping] ? 'Valid' : 'Invalid')
        }));
        
        const allValid = itemResults.every(item => item.isValid);
        const invalidCount = itemResults.filter(item => !item.isValid).length;
        
        setValidationState({
          isValidating: false,
          isValid: allValid,
          message: allValid 
            ? `All ${itemResults.length} items valid` 
            : `${invalidCount} of ${itemResults.length} items invalid`
        });

        lastValidatedKeyRef.current = validationKey;
        onValidationChange(fieldName, allValid, itemResults);
      } else {
        const isValid = responseData[fieldMapping] === true;
        
        setValidationState({
          isValidating: false,
          isValid,
          message: responseData.message || (isValid ? 'Valid' : 'Invalid')
        });

        lastValidatedKeyRef.current = validationKey;
        onValidationChange(fieldName, isValid);
      }

    } catch (error: any) {
      console.error('Validation error:', error);
      const errorMessage = error.response?.data?.message || 'Validation failed';
      
      setValidationState({ isValidating: false, isValid: false, message: errorMessage });
      onValidationChange(fieldName, false);
    }
  };

  const handleAuthResponse = useCallback((data: any) => {
    const status = data.status;
    const message = data.message || '';

    if (status === 'authenticated') {
      setAuthUrl(null);
      setAuthStatus('authenticated');
      setAuthMessage(message);
      setValidationState({ isValidating: false, isValid: true, message });
      onValidationChange(fieldName, true);
    } else if (status === 'requires_consent' || status === 'expired') {
      setAuthUrl(data.authorization_url || null);
      setAuthStatus(status);
      setAuthMessage(message);
      setValidationState({ isValidating: false, isValid: null, message });
      onValidationChange(fieldName, false);
    } else if (status === 'needs_client_registration') {
      setAuthUrl(null);
      setAuthStatus(status);
      setAuthMessage(data.message || 'OAuth client registration required');
      setValidationState({ isValidating: false, isValid: false, message: data.message || '' });
      onValidationChange(fieldName, false);
    } else {
      setAuthUrl(null);
      setAuthStatus(status);
      setAuthMessage(message);
      setValidationState({ isValidating: false, isValid: false, message });
      onValidationChange(fieldName, false);
    }
  }, [fieldName, onValidationChange]);

  const handleSignIn = useCallback(() => {
    if (!authUrl) return;
    popupRef.current = window.open(authUrl, 'oauth_signin', 'width=600,height=700,scrollbars=yes');
  }, [authUrl]);

  // Listen for OAuth callback postMessage from popup
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === 'credentials_callback') {
        if (popupRef.current) {
          popupRef.current.close();
          popupRef.current = null;
        }
        if (event.data.success) {
          lastValidatedKeyRef.current = null;
          performValidation(fieldValue);
        } else {
          setAuthStatus('error');
          setAuthMessage(event.data.error || 'Authentication failed');
          setValidationState({ isValidating: false, isValid: false, message: event.data.error || 'Authentication failed' });
          onValidationChange(fieldName, false);
        }
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [fieldValue, fieldName]);

  // Debounced validation on field value change OR dependency value change
  useEffect(() => {
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }

    validationTimeoutRef.current = setTimeout(() => {
      performValidation(fieldValue);
    }, 1500);

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [validationKey]);

  useEffect(() => {
    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, []);

  if (!useApiHint && !validationAction) {
    return null;
  }
  if (useApiHint && !validationHint.endpoint) {
    return null;
  }

  // ── Auth-aware rendering ──

  if (authStatus === 'authenticated') {
    return (
      <div className="flex items-center gap-2 mt-1">
        <CheckCircle className="h-4 w-4 text-green-400" />
        <span className="text-xs text-green-400">Authenticated</span>
        {authMessage && <Badge variant="outline" className="text-xs">{authMessage}</Badge>}
      </div>
    );
  }

  if ((authStatus === 'requires_consent' || authStatus === 'expired') && authUrl) {
    return (
      <div className="flex items-center gap-2 mt-1">
        <Lock className="h-4 w-4 text-yellow-400" />
        <span className="text-xs text-yellow-400">
          {authStatus === 'expired' ? 'Session expired' : 'Sign in required'}
        </span>
        <button
          type="button"
          onClick={handleSignIn}
          className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
        >
          <LogIn className="h-3 w-3" />
          {authStatus === 'expired' ? 'Re-authenticate' : 'Sign In'}
        </button>
        {authMessage && <Badge variant="outline" className="text-xs">{authMessage}</Badge>}
      </div>
    );
  }

  if (authStatus === 'needs_client_registration') {
    return (
      <div className="flex items-center gap-2 mt-1">
        <XCircle className="h-4 w-4 text-orange-400" />
        <span className="text-xs text-orange-400">{authMessage || 'Client registration required'}</span>
      </div>
    );
  }

  if (authStatus === 'requires_consent' && !authUrl) {
    return (
      <div className="flex items-center gap-2 mt-1">
        <Lock className="h-4 w-4 text-yellow-400" />
        <span className="text-xs text-yellow-400">{authMessage || 'Sign in required'}</span>
      </div>
    );
  }

  // ── Standard validation rendering ──

  const renderValidationIcon = () => {
    if (validationState.isValidating) {
      return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />;
    }
    if (validationState.isValid === true) {
      return <CheckCircle className="h-4 w-4 text-green-400" />;
    }
    if (validationState.isValid === false) {
      return <XCircle className="h-4 w-4 text-red-400" />;
    }
    return null;
  };

  const getValidationStatus = () => {
    if (validationState.isValidating) {
      return { color: 'text-blue-400', text: 'Validating...' };
    }
    if (validationState.isValid === true) {
      return { color: 'text-green-400', text: 'Valid' };
    }
    if (validationState.isValid === false) {
      return { color: 'text-red-400', text: 'Invalid' };
    }
    return { color: 'text-gray-400', text: 'Not validated' };
  };

  const status = getValidationStatus();

  return (
    <div className="flex items-center gap-2 mt-1">
      {renderValidationIcon()}
      <span className={`text-xs ${status.color}`}>
        {status.text}
      </span>
      {validationState.message && (
        <Badge variant="outline" className="text-xs">
          {validationState.message}
        </Badge>
      )}
    </div>
  );
};
