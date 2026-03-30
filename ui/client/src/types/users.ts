// Response types
export interface CheckAvailabilityResponse {
  available: boolean;
}

export interface ProfileUpdateResponse {
  success: boolean;
  message?: string;
}

export interface PasswordUpdateResponse {
  success: boolean;
  message?: string;
}

export interface SignupResponse {
  success: boolean;
  message?: string;
}

export interface ProfileData {
  name: string;
  email: string;
  username: string;
}

export interface PasswordData {
  currentPassword: string;
  newPassword: string;
}

export interface SignupData {
  username: string;
  email: string;
  name: string;
  password: string;
}