import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import StatusBar from "@/components/layout/StatusBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import {
  FaUser,
  FaUserEdit,
  FaBuilding,
  FaBell,
  FaPalette,
  FaLock,
} from "react-icons/fa";

export default function Settings() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user } = useAuth();

  const [profileData, setProfileData] = useState({
    name: user?.name || "",
    email: user?.email || "",
    username: user?.username || "",
  });

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name,
        email: user.email,
        username: user.username,
      });
    }
  }, [user]);

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

              <TabsContent value="profile">
                <div className="grid grid-cols-1 lg:grid-cols-1 gap-6 max-w-4xl mx-auto">
                  <Card className="bg-background-card shadow-card border-gray-800">
                    <CardHeader>
                      <CardTitle className="text-xl font-semibold text-white flex items-center gap-2">
                        <FaUserEdit className="text-purple-400" />
                        Account Settings
                      </CardTitle>
                      <CardDescription className="text-gray-400">
                        Your profile is managed by your organization&apos;s identity provider (SSO).
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-8">
                      <div className="mb-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                        <div className="flex items-start gap-3">
                          <FaLock className="text-blue-400 mt-0.5 flex-shrink-0" />
                          <div>
                            <h4 className="text-blue-400 font-medium">Enterprise managed account</h4>
                            <p className="text-sm text-gray-400 mt-1">
                              Profile and password changes are made through your SSO provider, not in UnifAI.
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-4">
                        <h3 className="text-lg font-medium text-white mb-2 flex items-center gap-2">
                          <FaBuilding className="text-purple-400" />
                          Profile information
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="name" className="text-gray-300">
                              Full name
                            </Label>
                            <Input
                              id="name"
                              type="text"
                              value={profileData.name}
                              readOnly
                              className="h-11 bg-[#2A303C] border-[#3D4450] text-white opacity-80 cursor-not-allowed"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="username" className="text-gray-300">
                              Username
                            </Label>
                            <Input
                              id="username"
                              type="text"
                              value={profileData.username}
                              readOnly
                              className="h-11 bg-[#2A303C] border-[#3D4450] text-white opacity-80 cursor-not-allowed"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="email" className="text-gray-300">
                            Email
                          </Label>
                          <Input
                            id="email"
                            type="email"
                            value={profileData.email}
                            readOnly
                            className="h-11 bg-[#2A303C] border-[#3D4450] text-white opacity-80 cursor-not-allowed"
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="notifications">
                <Card className="bg-background-card shadow-card border-gray-800">
                  <CardContent className="p-12 text-center">
                    <FaBell className="mx-auto text-4xl text-gray-600 mb-4" />
                    <h3 className="text-lg font-medium text-white mb-2">Notification settings coming soon</h3>
                    <p className="text-gray-400">Configure your notification preferences here.</p>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="appearance">
                <Card className="bg-background-card shadow-card border-gray-800">
                  <CardContent className="p-12 text-center">
                    <FaPalette className="mx-auto text-4xl text-gray-600 mb-4" />
                    <h3 className="text-lg font-medium text-white mb-2">Appearance settings coming soon</h3>
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
