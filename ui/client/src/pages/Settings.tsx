import { useState } from "react";
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
import { api } from "@/http/authClient";
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
  
  // Check if user is external (local auth)
  const isExternalUser = authProvider === 'local';
  const isEnterpriseUser = authProvider === 'keycloak' || !authProvider;
  
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
      const response = await api.put('/auth/local/profile', {
        name: profileData.name,
        email: profileData.email,
        username: profileData.username
      });
      
      if (response.data.success) {
        setProfileSuccess('Profile updated successfully');
        await checkAuthStatus(); // Refresh user data
        toast({
          title: "Profile Updated",
          description: "Your profile has been updated successfully.",
        });
      } else {
        setProfileError(response.data.message || 'Failed to update profile');
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
      const response = await api.put('/auth/local/password', {
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword
      });
      
      if (response.data.success) {
        setPasswordSuccess('Password updated successfully');
        setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
        toast({
          title: "Password Updated",
          description: "Your password has been changed successfully.",
        });
      } else {
        setPasswordError(response.data.message || 'Failed to update password');
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
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Profile Card */}
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardContent className="p-6">
                      <div className="flex flex-col items-center text-center">
                        <div className="w-24 h-24 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center mb-4 shadow-lg shadow-purple-500/25">
                          <span className="text-3xl font-bold text-white">
                            {getInitials(user?.name || 'U')}
                          </span>
                        </div>
                        <h3 className="text-xl font-semibold text-white">{user?.name}</h3>
                        <p className="text-gray-400 text-sm mt-1">@{user?.username}</p>
                        
                        <div className="mt-4 flex items-center gap-2">
                          {isExternalUser ? (
                            <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                              <FaUser className="mr-1 h-3 w-3" />
                              External User
                            </Badge>
                          ) : (
                            <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                              <FaBuilding className="mr-1 h-3 w-3" />
                              Enterprise SSO
                            </Badge>
                          )}
                        </div>
                        
                        <div className="mt-6 w-full pt-6 border-t border-gray-800">
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">Email</span>
                            <span className="text-white truncate max-w-[150px]">{user?.email}</span>
                          </div>
                          <div className="flex justify-between text-sm mt-2">
                            <span className="text-gray-400">User ID</span>
                            <span className="text-white font-mono text-xs truncate max-w-[150px]">{user?.sub?.slice(0, 12)}...</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Edit Profile Form */}
                  <Card className="bg-background-card shadow-card border-gray-800 lg:col-span-2">
                    <CardHeader>
                      <CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
                        <FaUserEdit className="text-purple-400" />
                        Edit Profile
                      </CardTitle>
                      <CardDescription className="text-gray-400">
                        {isExternalUser 
                          ? "Update your personal information below"
                          : "Your profile is managed by your enterprise identity provider"
                        }
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      {/* Enterprise User Notice */}
                      {isEnterpriseUser && (
                        <div className="mb-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                          <div className="flex items-start gap-3">
                            <FaLock className="text-blue-400 mt-0.5 flex-shrink-0" />
                            <div>
                              <h4 className="text-blue-400 font-medium">Enterprise Managed Account</h4>
                              <p className="text-sm text-gray-400 mt-1">
                                Your profile information is managed by your organization's identity provider (SSO). 
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      <form onSubmit={handleUpdateProfile} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Full Name */}
                          <div className="space-y-2">
                            <Label htmlFor="name" className="text-gray-300">Full Name</Label>
                            <div className="relative">
                              <FaUserEdit className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                              <Input
                                id="name"
                                name="name"
                                type="text"
                                value={profileData.name}
                                onChange={handleProfileChange}
                                disabled={isEnterpriseUser}
                                className={`pl-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 
                                  ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : 'focus:border-purple-500'}`}
                                placeholder="Enter your full name"
                              />
                            </div>
                          </div>
                          
                          {/* Username */}
                          <div className="space-y-2">
                            <Label htmlFor="username" className="text-gray-300">Username</Label>
                            <div className="relative">
                              <FaUser className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                              <Input
                                id="username"
                                name="username"
                                type="text"
                                value={profileData.username}
                                onChange={handleProfileChange}
                                disabled={isEnterpriseUser}
                                className={`pl-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 
                                  ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : 'focus:border-purple-500'}`}
                                placeholder="Enter your username"
                              />
                            </div>
                          </div>
                        </div>
                        
                        {/* Email */}
                        <div className="space-y-2">
                          <Label htmlFor="email" className="text-gray-300">Email Address</Label>
                          <div className="relative">
                            <FaEnvelope className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                            <Input
                              id="email"
                              name="email"
                              type="email"
                              value={profileData.email}
                              onChange={handleProfileChange}
                              disabled={isEnterpriseUser}
                              className={`pl-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 
                                ${isEnterpriseUser ? 'opacity-60 cursor-not-allowed' : 'focus:border-purple-500'}`}
                              placeholder="Enter your email"
                            />
                          </div>
                        </div>
                        
                        {/* Success/Error Messages */}
                        {profileError && (
                          <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2"
                          >
                            <FaTimes className="flex-shrink-0" />
                            {profileError}
                          </motion.div>
                        )}
                        
                        {profileSuccess && (
                          <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-center gap-2"
                          >
                            <FaCheck className="flex-shrink-0" />
                            {profileSuccess}
                          </motion.div>
                        )}
                        
                        {/* Submit Button */}
                        {isExternalUser && (
                          <Button
                            type="submit"
                            className="w-full h-11 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white font-medium shadow-lg shadow-purple-500/25"
                            disabled={isUpdatingProfile}
                          >
                            {isUpdatingProfile ? (
                              <div className="flex items-center">
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                                Updating...
                              </div>
                            ) : (
                              <div className="flex items-center">
                                <FaCheck className="mr-2" />
                                Save Changes
                              </div>
                            )}
                          </Button>
                        )}
                      </form>
                    </CardContent>
                  </Card>
                  
                  {/* Change Password Card - Only for external users */}
                  {isExternalUser && (
                    <Card className="bg-background-card shadow-card border-gray-800 lg:col-span-3">
                      <CardHeader>
                        <CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
                          <FaKey className="text-purple-400" />
                          Change Password
                        </CardTitle>
                        <CardDescription className="text-gray-400">
                          Update your password to keep your account secure
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <form onSubmit={handleUpdatePassword} className="space-y-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Current Password */}
                            <div className="space-y-2">
                              <Label htmlFor="currentPassword" className="text-gray-300">Current Password</Label>
                              <div className="relative">
                                <FaKey className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                                <Input
                                  id="currentPassword"
                                  name="currentPassword"
                                  type="password"
                                  value={passwordData.currentPassword}
                                  onChange={handlePasswordChange}
                                  className="pl-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                                  placeholder="Current password"
                                />
                              </div>
                            </div>
                            
                            {/* New Password */}
                            <div className="space-y-2">
                              <Label htmlFor="newPassword" className="text-gray-300">New Password</Label>
                              <div className="relative">
                                <FaKey className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 h-4 w-4" />
                                <Input
                                  id="newPassword"
                                  name="newPassword"
                                  type="password"
                                  value={passwordData.newPassword}
                                  onChange={handlePasswordChange}
                                  className="pl-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                                  placeholder="New password"
                                />
                              </div>
                              {/* Password requirements */}
                              {passwordData.newPassword.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-2">
                                  {passwordRequirements.map((req, idx) => (
                                    <span key={idx} className={`text-xs px-2 py-1 rounded-full ${req.met ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-500'}`}>
                                      {req.met ? <FaCheck className="inline h-2 w-2 mr-1" /> : <FaTimes className="inline h-2 w-2 mr-1" />}
                                      {req.label}
                                    </span>
                                  ))}
                                </div>
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
                                  value={passwordData.confirmPassword}
                                  onChange={handlePasswordChange}
                                  className="pl-10 pr-10 h-11 bg-[#2A303C] border-[#3D4450] text-white placeholder:text-gray-500 focus:border-purple-500"
                                  placeholder="Confirm password"
                                />
                                {passwordData.confirmPassword.length > 0 && (
                                  <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                                    {passwordsMatch ? (
                                      <FaCheck className="text-green-500 h-4 w-4" />
                                    ) : (
                                      <FaTimes className="text-red-500 h-4 w-4" />
                                    )}
                                  </div>
                                )}
                              </div>
                              {passwordData.confirmPassword.length > 0 && !passwordsMatch && (
                                <p className="text-red-400 text-xs">Passwords do not match</p>
                              )}
                            </div>
                          </div>
                          
                          {/* Success/Error Messages */}
                          {passwordError && (
                            <motion.div
                              initial={{ opacity: 0, y: -10 }}
                              animate={{ opacity: 1, y: 0 }}
                              className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2"
                            >
                              <FaTimes className="flex-shrink-0" />
                              {passwordError}
                            </motion.div>
                          )}
                          
                          {passwordSuccess && (
                            <motion.div
                              initial={{ opacity: 0, y: -10 }}
                              animate={{ opacity: 1, y: 0 }}
                              className="p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-center gap-2"
                            >
                              <FaCheck className="flex-shrink-0" />
                              {passwordSuccess}
                            </motion.div>
                          )}
                          
                          {/* Submit Button */}
                          <Button
                            type="submit"
                            variant="outline"
                            className="h-11 border-[#3D4450] text-white hover:bg-purple-600 hover:border-purple-600"
                            disabled={isUpdatingPassword || !allPasswordRequirementsMet || !passwordsMatch || !passwordData.currentPassword}
                          >
                            {isUpdatingPassword ? (
                              <div className="flex items-center">
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                                Updating...
                              </div>
                            ) : (
                              <div className="flex items-center">
                                <FaKey className="mr-2" />
                                Update Password
                              </div>
                            )}
                          </Button>
                        </form>
                      </CardContent>
                    </Card>
                  )}
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

