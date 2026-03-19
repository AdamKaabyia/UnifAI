import React from 'react';
import { motion } from 'framer-motion';

interface LoginPageProps {
  onLogin: () => void;
  showSessionEnded?: boolean;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin, showSessionEnded = false }) => {
  return (
    <div className="relative flex items-center justify-center min-h-screen overflow-hidden bg-[#0D1117]">

      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.8) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="relative z-10 flex flex-col items-center w-full max-w-md mx-4"
      >
        {/* Logo */}
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-gray-500 flex items-center justify-center mb-8 shadow-lg shadow-primary/20"
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M3 12H7M17 12H21M12 3V7M12 17V21M5 19L8 16M16 8L19 5M19 19L16 16M5 5L8 8"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </motion.div>

        {/* Welcome text */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="text-center mb-10"
        >
          <h1 className="text-4xl font-heading font-bold text-white mb-3 tracking-tight">
            Welcome to <span className="bg-gradient-to-r from-primary to-purple-300 bg-clip-text text-transparent">UnifAI</span>
          </h1>
          <p className="text-gray-400 text-lg leading-relaxed max-w-sm mx-auto">
            Your unified platform for intelligent automation and AI-powered workflows.
          </p>
        </motion.div>

        {/* Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="w-full rounded-2xl border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-8 shadow-2xl"
        >
          {showSessionEnded && (
            <div className="mb-6 flex items-center gap-3 rounded-lg bg-white/[0.04] border border-white/[0.06] px-4 py-3">
              <div className="flex-shrink-0 w-2 h-2 rounded-full bg-amber-400" />
              <p className="text-sm text-gray-300">Your session has ended. Sign in to continue.</p>
            </div>
          )}

          <button
            onClick={onLogin}
            className="group w-full flex items-center justify-center gap-3 px-6 py-3.5 rounded-xl bg-primary hover:brightness-110 text-white font-semibold text-base transition-all duration-200 shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:scale-[1.02] active:scale-[0.98]"
          >
            <svg
              className="w-5 h-5 transition-transform duration-200 group-hover:-translate-x-0.5"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"
                fill="currentColor"
              />
            </svg>
            Connect with SSO
          </button>

          <p className="mt-5 text-center text-xs text-gray-500">
            Secure single sign-on through your organization
          </p>
        </motion.div>

        {/* Footer */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mt-8 text-xs text-gray-600"
        >
          &copy; {new Date().getFullYear()} UnifAI
        </motion.p>
      </motion.div>
    </div>
  );
};

export default LoginPage;
