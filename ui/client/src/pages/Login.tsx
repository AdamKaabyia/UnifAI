import React from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { FaBuilding } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi';

export default function Login() {
  const { login, isLoading: authLoading } = useAuth();

  const handleSSOLogin = () => {
    login();
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
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
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-purple-700 mb-4 shadow-lg shadow-purple-500/25"
          >
            <HiSparkles className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome to UnifAI</h1>
          <p className="text-gray-400">Sign in to continue to your dashboard</p>
        </div>

        <Card className="border-0 bg-[#1C2128]/80 backdrop-blur-xl shadow-2xl">
          <CardContent>
            <Button
              type="button"
              variant="outline"
              className="w-full h-12 bg-[#2A303C] border-[#3D4450] hover:bg-[#353D4A] hover:border-purple-500/50 text-white transition-all duration-200"
              onClick={handleSSOLogin}
              disabled={authLoading}
            >
              <FaBuilding className="mr-2 h-4 w-4 text-purple-400" />
              Login using SSO
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
