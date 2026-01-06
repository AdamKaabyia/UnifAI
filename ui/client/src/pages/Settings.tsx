import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { checkUsernameAvailability, checkEmailAvailability, updateProfile, updatePassword } from "@/api/users";
import { motion } from "framer-motion";
import { 
  FaUser, FaEnvelope, FaKey, FaUserEdit, FaCheck, FaTimes, 
  FaBuilding, FaBell, FaPalette, FaLock
} from "react-icons/fa";
import { useToast } from "@/hooks/use-toast";

interface PasswordRequirement {
  label: string;
  met: boolean;
}

export default function Settings() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, authProvider, checkAuthStatus } = useAuth();
  const { toast } = useToast();
  
  // Profile form state
  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    username: user?.username || ''
  });
  
  // Password form state
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  
  // Availability checking state
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
  const [checkingUsername, setCheckingUsername] = useState(false);
  const [checkingEmail, setCheckingEmail] = useState(false);
  
  // Check if user is external (local auth)
  const isExternalUser = authProvider === 'local';
  const isEnterpriseUser = authProvider === 'keycloak' || !authProvider;
  
  // Debounced username availability check
  useEffect(() => {
    // Only check if username changed from original
    if (profileData.username === user?.username) {
      setUsernameAvailable(null);
      setCheckingUsername(false);
      return;
    }
    
    if (profileData.username.length >= 3) {
      setCheckingUsername(true);
      const timer = setTimeout(async () => {
        try {
          const available = await checkUsernameAvailability(profileData.username);
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
  }, [profileData.username, user?.username]);
  
  // Debounced email availability check
  useEffect(() => {
    // Only check if email changed from original
    if (profileData.email === user?.email) {
      setEmailAvailable(null);
      setCheckingEmail(false);
      return;
    }
    
    if (profileData.email.includes('@') && profileData.email.includes('.')) {
      setCheckingEmail(true);
      const timer = setTimeout(async () => {
        try {
          const available = await checkEmailAvailability(profileData.email);
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
  }, [profileData.email, user?.email]);
  
  // Check if profile can be saved
  const hasProfileChanges = 
    profileData.name !== user?.name ||
    profileData.username !== user?.username ||
    profileData.email !== user?.email;
  
  const isUsernameValid = 
    profileData.username === user?.username || // unchanged
    (profileData.username.length >= 3 && usernameAvailable === true); // changed and available
  
  const isEmailValid = 
    profileData.email === user?.email || // unchanged
    (profileData.email.includes('@') && emailAvailable === true); // changed and available
  
  const canSaveProfile = 
    hasProfileChanges && 
    isUsernameValid && 
    isEmailValid && 
    profileData.name.length >= 2 &&
    !checkingUsername &&
    !checkingEmail;
  
  // Password requirements
  const passwordRequirements: PasswordRequirement[] = [
    { label: 'At least 8 characters', met: passwordData.newPassword.length >= 8 },
    { label: 'At least one letter', met: /[a-zA-Z]/.test(passwordData.newPassword) },
    { label: 'One number', met: /\d/.test(passwordData.newPassword) },
  ];
  
  const allPasswordRequirementsMet = passwordRequirements.every(req => req.met);
  const passwordsMatch = passwordData.newPassword === passwordData.confirmPassword && 
                         passwordData.confirmPassword.length > 0;
  
  const handleProfileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setProfileData(prev => ({ ...prev, [name]: value }));
    setProfileError('');
    setProfileSuccess('');
  };
  
  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPasswordData(prev => ({ ...prev, [name]: value }));
    setPasswordError('');
    setPasswordSuccess('');
  };
  
  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isExternalUser) return;
    
    setIsUpdatingProfile(true);
    setProfileError('');
    setProfileSuccess('');
    
    try {
      const response = await updateProfile({
        name: profileData.name,
        email: profileData.email,
        username: profileData.username
      });
      
      if (response.success) {
        setProfileSuccess('Profile updated successfully');
        await checkAuthStatus(); // Refresh user data
        toast({
          title: "Profile Updated",
          description: "Your profile has been updated successfully.",
        });
      } else {
        setProfileError(response.message || 'Failed to update profile');
      }
    } catch (err: any) {
      setProfileError(err.response?.data?.message || 'An error occurred while updating profile');
    } finally {
      setIsUpdatingProfile(false);
    }
  };
  
  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isExternalUser) return;
    
    if (!allPasswordRequirementsMet) {
      setPasswordError('Please meet all password requirements');
      return;
    }
    
    if (!passwordsMatch) {
      setPasswordError('Passwords do not match');
      return;
    }
    
    setIsUpdatingPassword(true);
    setPasswordError('');
    setPasswordSuccess('');
    
    try {
      const response = await updatePassword({
        currentPassword: passwordData.currentPassword,
        newPassword: passwordData.newPassword
      });
      
      if (response.success) {
        setPasswordSuccess('Password updated successfully');
        setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
        toast({
          title: "Password Updated",
          description: "Your password has been changed successfully.",
        });
      } else {
        setPasswordError(response.message || 'Failed to update password');
      }
    } catch (err: any) {
      setPasswordError(err.response?.data?.message || 'An error occurred while updating password');
    } finally {
      setIsUpdatingPassword(false);
    }
  };
  
  const getInitials = (name: string): string => {
    return name
      .split(' ')
      .filter(Boolean)
      .map(part => part[0].toUpperCase())
      .join('');
  };
  
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Settings" onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        
        <main className="flex-1 overflow-y-auto p-6 bg-background-dark">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Tabs defaultValue="profile" className="w-full">
              <TabsList className="mb-6">
                <TabsTrigger value="profile" className="data-[state=active]:bg-primary data-[state=active]:text-white">
                  <FaUser className="mr-2" />
                  Profile
                </TabsTrigger>
                <TabsTrigger value="notifications" className="data-[state=active]:bg-primary data-[state=active]:text-white" disabled>
                  <FaBell className="mr-2" />
                  Notifications
                </TabsTrigger>
                <TabsTrigger value="appearance" className="data-[state=active]:bg-primary data-[state=active]:text-white" disabled>
                  <FaPalette className="mr-2" />
                  Appearance
                </TabsTrigger>
              </TabsList>
              
              {/* Profile Tab */}
              <TabsContent value="profile">
                <div className="grid grid-cols-1 lg:grid-cols-1 gap-6 max-w-4xl mx-auto">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardHeader>
                      <CardTitle className="text-xl font-semibold text-white flex items-center gap-2">
                        <FaUserEdit className="text-purple-400" />
                        Account Settings
                      </CardTitle>
                      <CardDescription className="text-gray-400">
                        Manage your profile information and update your password here.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-8">

                      {/* Enterprise User Notice */}
                      {isEnterpriseUser && (
                        <div className="mb-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                          <div className="flex items-start gap-3">
                            <FaLock className="text-blue-400 mt-0.5 flex-shrink-0" />
                            <div>
                              <h4 className="text-blue-400 font-medium">Enterprise Managed Account</h4>
                              <p className="text-sm text-gray-400 mt-1">
                                Your profile information is managed by your organization's identity provider (SSO) 
                                and cannot be edited here.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Profile Section */}
                      <form onSubmit={handleUpdateProfile} className="space-y-4">
                        <h3 className="text-lg font-medium text-white mb-2">Profile Information</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="name" className="text-gray-300">Full Name</Label>
                            <Input
                              id="name"
                              name="name"
                              type="text"
                              value={profileData.name}
                              onChange={handleProfileChange}
                              disabled={isEnterpriseUser}
                              placeholder="Full Name"
                              className={`h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500
                                ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : ''}`}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="username" className="text-gray-300">Username</Label>
                            <div className="relative">
                              <Input
                                id="username"
                                name="username"
                                type="text"
                                value={profileData.username}
                                onChange={handleProfileChange}
                                disabled={isEnterpriseUser}
                                placeholder="Username"
                                className={`h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500 pr-10
                                  ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : ''}
                                  ${profileData.username !== user?.username && usernameAvailable === false ? 'border-red-500' : ''}
                                  ${profileData.username !== user?.username && usernameAvailable === true ? 'border-green-500' : ''}`}
                              />
                              {profileData.username !== user?.username && (
                                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                  {checkingUsername ? (
                                    <div className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                                  ) : usernameAvailable === true ? (
                                    <FaCheck className="text-green-400" />
                                  ) : usernameAvailable === false ? (
                                    <FaTimes className="text-red-400" />
                                  ) : null}
                                </div>
                              )}
                            </div>
                            {profileData.username !== user?.username && usernameAvailable === false && (
                              <p className="text-red-400 text-xs mt-1">Username is already taken</p>
                            )}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="email" className="text-gray-300">Email Address</Label>
                          <div className="relative">
                            <Input
                              id="email"
                              name="email"
                              type="email"
                              value={profileData.email}
                              onChange={handleProfileChange}
                              disabled={isEnterpriseUser}
                              placeholder="Email"
                              className={`h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500 pr-10
                                ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : ''}
                                ${profileData.email !== user?.email && emailAvailable === false ? 'border-red-500' : ''}
                                ${profileData.email !== user?.email && emailAvailable === true ? 'border-green-500' : ''}`}
                            />
                            {profileData.email !== user?.email && (
                              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                {checkingEmail ? (
                                  <div className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                                ) : emailAvailable === true ? (
                                  <FaCheck className="text-green-400" />
                                ) : emailAvailable === false ? (
                                  <FaTimes className="text-red-400" />
                                ) : null}
                              </div>
                            )}
                          </div>
                          {profileData.email !== user?.email && emailAvailable === false && (
                            <p className="text-red-400 text-xs mt-1">Email is already in use</p>
                          )}
                        </div>
                        {profileError && <p className="text-red-400 text-sm">{profileError}</p>}
                        {profileSuccess && <p className="text-green-400 text-sm">{profileSuccess}</p>}
                        {isExternalUser && (
                          <Button type="submit" disabled={!canSaveProfile || isUpdatingProfile}>
                            {isUpdatingProfile ? 'Updating...' : checkingUsername || checkingEmail ? 'Checking...' : 'Save Profile'}
                          </Button>
                        )}
                      </form>

                      {/* Password Section */}
                      {isExternalUser && (
                        <form onSubmit={handleUpdatePassword} className="space-y-4">
                          <h3 className="text-lg font-medium text-white mb-2">Change Password</h3>
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Input
                              id="currentPassword"
                              name="currentPassword"
                              type="password"
                              value={passwordData.currentPassword}
                              onChange={handlePasswordChange}
                              placeholder="Current password"
                              className="h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                            />
                            <Input
                              id="newPassword"
                              name="newPassword"
                              type="password"
                              value={passwordData.newPassword}
                              onChange={handlePasswordChange}
                              placeholder="New password"
                              className="h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                            />
                            <Input
                              id="confirmPassword"
                              name="confirmPassword"
                              type="password"
                              value={passwordData.confirmPassword}
                              onChange={handlePasswordChange}
                              placeholder="Confirm password"
                              className="h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                            />
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {passwordRequirements.map((req, idx) => (
                              <Badge
                                key={idx}
                                className={req.met ? "bg-green-500/20 text-green-400" : "bg-gray-500/20 text-gray-500"}
                              >
                                {req.label}
                              </Badge>
                            ))}
                          </div>
                          {passwordError && <p className="text-red-400 text-sm">{passwordError}</p>}
                          {passwordSuccess && <p className="text-green-400 text-sm">{passwordSuccess}</p>}
                          <Button type="submit" disabled={!allPasswordRequirementsMet || !passwordsMatch || !passwordData.currentPassword || isUpdatingPassword}>
                            {isUpdatingPassword ? 'Updating...' : 'Update Password'}
                          </Button>
                        </form>
                      )}

                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
              
              {/* Notifications Tab - Coming Soon */}
              <TabsContent value="notifications">
                <Card className="bg-background-card shadow-card border-gray-800">
                  <CardContent className="p-12 text-center">
                    <FaBell className="mx-auto text-4xl text-gray-600 mb-4" />
                    <h3 className="text-lg font-medium text-white mb-2">Notification Settings Coming Soon</h3>
                    <p className="text-gray-400">Configure your notification preferences here.</p>
                  </CardContent>
                </Card>
              </TabsContent>
              
              {/* Appearance Tab - Coming Soon */}
              <TabsContent value="appearance">
                <Card className="bg-background-card shadow-card border-gray-800">
                  <CardContent className="p-12 text-center">
                    <FaPalette className="mx-auto text-4xl text-gray-600 mb-4" />
                    <h3 className="text-lg font-medium text-white mb-2">Appearance Settings Coming Soon</h3>
                    <p className="text-gray-400">Customize the look and feel of your interface here.</p>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </motion.div>
        </main>
        
        <StatusBar />
      </div>
    </div>
  );
}

