import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { checkUsernameAvailability, checkEmailAvailability, signup } from '@/api/users';
import { FaUser, FaEnvelope, FaKey, FaUserEdit, FaArrowRight, FaCheck, FaTimes } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi';

interface PasswordRequirement {
  label: string;
  met: boolean;
}

export default function Signup() {
  const [, setLocation] = useLocation();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    name: '',
    password: '',
    confirmPassword: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
  const [checkingUsername, setCheckingUsername] = useState(false);
  const [checkingEmail, setCheckingEmail] = useState(false);

  // Password requirements
  const passwordRequirements: PasswordRequirement[] = [
    { label: 'At least 8 characters', met: formData.password.length >= 8 },
    { label: 'At least one letter', met: /[a-zA-Z]/.test(formData.password) },
    { label: 'One number', met: /\d/.test(formData.password) },
  ];

  const allRequirementsMet = passwordRequirements.every(req => req.met);
  const passwordsMatch = formData.password === formData.confirmPassword && formData.confirmPassword.length > 0;

  // Debounced username check
  useEffect(() => {
    if (formData.username.length >= 3) {
      setCheckingUsername(true);
      const timer = setTimeout(async () => {
        try {
          const available = await checkUsernameAvailability(formData.username);
          setUsernameAvailable(available);
        } catch {
          setUsernameAvailable(null);
        } finally {
          setCheckingUsername(false);
        }
      }, 500);
      return () => clearTimeout(timer);
    } else {
      setUsernameAvailable(null);
    }
  }, [formData.username]);

  // Debounced email check
  useEffect(() => {
    if (formData.email.includes('@') && formData.email.includes('.')) {
      setCheckingEmail(true);
      const timer = setTimeout(async () => {
        try {
          const available = await checkEmailAvailability(formData.email);
          setEmailAvailable(available);
        } catch {
          setEmailAvailable(null);
        } finally {
          setCheckingEmail(false);
        }
      }, 500);
      return () => clearTimeout(timer);
    } else {
      setEmailAvailable(null);
    }
  }, [formData.email]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validations
    if (!allRequirementsMet) {
      setError('Please meet all password requirements');
      return;
    }

    if (!passwordsMatch) {
      setError('Passwords do not match');
      return;
    }

    if (usernameAvailable === false) {
      setError('Username is not available');
      return;
    }

    if (emailAvailable === false) {
      setError('Email is already registered');
      return;
    }

    setIsLoading(true);

    try {
      const response = await signup({
        username: formData.username,
        email: formData.email,
        name: formData.name,
        password: formData.password
      });

      if (response.success) {
        setSuccess(true);
        // Redirect to login after 2 seconds
        setTimeout(() => {
          setLocation('/login');
        }, 2000);
      } else {
        setError(response.message || 'Registration failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'An error occurred during registration');
    } finally {
      setIsLoading(false);
    }
  };

  const isFormValid = 
    formData.username.length >= 3 &&
    formData.email.includes('@') &&
    formData.name.length >= 2 &&
    allRequirementsMet &&
    passwordsMatch &&
    usernameAvailable !== false &&
    emailAvailable !== false;

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[#0D1117] via-[#161B22] to-[#1a1f2e]" />
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
          className="text-center z-10"
        >
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-green-500 to-green-600 mb-6 shadow-lg shadow-green-500/25">
            <FaCheck className="w-10 h-10 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Account Created!</h2>
          <p className="text-gray-400">Redirecting you to login...</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0D1117] via-[#161B22] to-[#1a1f2e]">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse delay-1000" />
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-purple-700 mb-4 shadow-lg shadow-purple-500/25"
          >
            <HiSparkles className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-bold text-white mb-2">Create Account</h1>
          <p className="text-gray-400">Join UnifAI and start your journey</p>
        </div>

        <Card className="border-0 bg-[#1C2128]/80 backdrop-blur-xl shadow-2xl">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl text-white">Sign Up</CardTitle>
            <CardDescription className="text-gray-400">
              Fill in your details to create an account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Username */}
              <div className="space-y-2">
                <Label htmlFor="username" className="text-gray-300">Username</Label>
                <div className="relative">
                  <FaUser className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    placeholder="Choose a username"
                    value={formData.username}
                    onChange={handleChange}
                    className="pl-10 pr-10 h-12 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-white-500 focus:border-purple-500"
                    required
                    minLength={3}
                  />
                  {formData.username.length >= 3 && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      {checkingUsername ? (
                        <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                      ) : usernameAvailable === true ? (
                        <FaCheck className="text-green-500 h-4 w-4" />
                      ) : usernameAvailable === false ? (
                        <FaTimes className="text-red-500 h-4 w-4" />
                      ) : null}
                    </div>
                  )}
                </div>
                {usernameAvailable === false && (
                  <p className="text-red-400 text-xs">Username is already taken</p>
                )}
              </div>

              {/* Email */}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-gray-300">Email</Label>
                <div className="relative">
                  <FaEnvelope className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="Enter your email"
                    value={formData.email}
                    onChange={handleChange}
                    className="pl-10 pr-10 h-12 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-white-500 focus:border-purple-500"
                    required
                  />
                  {formData.email.includes('@') && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      {checkingEmail ? (
                        <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                      ) : emailAvailable === true ? (
                        <FaCheck className="text-green-500 h-4 w-4" />
                      ) : emailAvailable === false ? (
                        <FaTimes className="text-red-500 h-4 w-4" />
                      ) : null}
                    </div>
                  )}
                </div>
                {emailAvailable === false && (
                  <p className="text-red-400 text-xs">Email is already registered</p>
                )}
              </div>

              {/* Name */}
              <div className="space-y-2">
                <Label htmlFor="name" className="text-gray-300">Full Name</Label>
                <div className="relative">
                  <FaUserEdit className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="Enter your full name"
                    value={formData.name}
                    onChange={handleChange}
                    className="pl-10 h-12 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                    required
                    minLength={2}
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-2">
                <Label htmlFor="password" className="text-gray-300">Password</Label>
                <div className="relative">
                  <FaKey className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    placeholder="Create a password"
                    value={formData.password}
                    onChange={handleChange}
                    className="pl-10 h-12 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                    required
                  />
                </div>
                {/* Password requirements */}
                {formData.password.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="grid grid-cols-2 gap-1 mt-2"
                  >
                    {passwordRequirements.map((req, idx) => (
                      <div key={idx} className="flex items-center text-xs">
                        {req.met ? (
                          <FaCheck className="text-green-500 h-3 w-3 mr-1" />
                        ) : (
                          <FaTimes className="text-gray-500 h-3 w-3 mr-1" />
                        )}
                        <span className={req.met ? 'text-green-400' : 'text-gray-500'}>
                          {req.label}
                        </span>
                      </div>
                    ))}
                  </motion.div>
                )}
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-gray-300">Confirm Password</Label>
                <div className="relative">
                  <FaKey className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type="password"
                    placeholder="Confirm your password"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className="pl-10 pr-10 h-12 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                    required
                  />
                  {formData.confirmPassword.length > 0 && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      {passwordsMatch ? (
                        <FaCheck className="text-green-500 h-4 w-4" />
                      ) : (
                        <FaTimes className="text-red-500 h-4 w-4" />
                      )}
                    </div>
                  )}
                </div>
                {formData.confirmPassword.length > 0 && !passwordsMatch && (
                  <p className="text-red-400 text-xs">Passwords do not match</p>
                )}
              </div>

              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
                >
                  {error}
                </motion.div>
              )}

              <Button
                type="submit"
                className="w-full h-12 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white font-medium shadow-lg shadow-purple-500/25 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || !isFormValid}
              >
                {isLoading ? (
                  <div className="flex items-center">
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                    Creating account...
                  </div>
                ) : (
                  <div className="flex items-center">
                    Create Account
                    <FaArrowRight className="ml-2 h-4 w-4" />
                  </div>
                )}
              </Button>
            </form>

            {/* Login Link */}
            <div className="text-center pt-4">
              <p className="text-gray-400 text-sm">
                Already have an account?{' '}
                <Link href="/login" className="text-purple-400 hover:text-purple-300 font-medium transition-colors">
                  Sign in
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <p className="text-center text-gray-500 text-xs mt-6">
          By creating an account, you agree to our Terms of Service and Privacy Policy
        </p>
      </motion.div>
    </div>
  );
}

