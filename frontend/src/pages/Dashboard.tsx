import React from 'react';
import { useAuth } from '@/context/AuthContext';

export const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <nav className="bg-white dark:bg-gray-800 shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold">
                Truth<span className="text-primary">Lens</span>
              </h1>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-600 dark:text-gray-300">
                <p>Welcome, {user?.name}</p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                className="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary/90 rounded-md transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Welcome to TruthLens
          </h2>
          <p className="text-gray-600 dark:text-gray-300 mb-4">
            AI-Powered Fake News Detection & Fact-Checking Assistant
          </p>
          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-900 rounded-md p-4">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Phase 2 implementation in progress. Authentication system is now complete!
            </p>
          </div>
        </div>
      </main>
    </div>
  );
};
