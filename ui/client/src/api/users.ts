import { api } from '@/http/authClient';
import { CheckAvailabilityResponse, PasswordData, PasswordUpdateResponse, ProfileData, ProfileUpdateResponse, SignupData, SignupResponse } from '@/types/users';

// Check if a username is available
export async function checkUsernameAvailability(username: string): Promise<boolean> {
  const response = await api.get<CheckAvailabilityResponse>(
    `/auth/local/check-username?username=${encodeURIComponent(username)}`
  );
  return response.data.available;
}

// Check if an email is available
export async function checkEmailAvailability(email: string): Promise<boolean> {
  const response = await api.get<CheckAvailabilityResponse>(
    `/auth/local/check-email?email=${encodeURIComponent(email)}`
  );
  return response.data.available;
}

// Update user profile
export async function updateProfile(data: ProfileData): Promise<ProfileUpdateResponse> {
  const response = await api.put<ProfileUpdateResponse>('/auth/local/profile', {
    name: data.name,
    email: data.email,
    username: data.username,
  });
  return response.data;
}

// Update user password
export async function updatePassword(data: PasswordData): Promise<PasswordUpdateResponse> {
  const response = await api.put<PasswordUpdateResponse>('/auth/local/password', {
    current_password: data.currentPassword,
    new_password: data.newPassword,
  });
  return response.data;
}

// Register a new user
export async function signup(data: SignupData): Promise<SignupResponse> {
  const response = await api.post<SignupResponse>('/auth/local/signup', {
    username: data.username,
    email: data.email,
    name: data.name,
    password: data.password,
  });
  return response.data;
}

