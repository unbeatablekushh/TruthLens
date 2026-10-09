import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { apiClient } from '@/lib/api';

export type Role = 'USER' | 'ADMIN';

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (access_token: string, refresh_token: string, user: User) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Listen for the custom logout event triggered by the api interceptor
    const handleForceLogout = () => {
      setUser(null);
    };
    window.addEventListener('auth:logout', handleForceLogout);
    
    return () => {
      window.removeEventListener('auth:logout', handleForceLogout);
    };
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      const accessToken = localStorage.getItem('access_token');
      if (accessToken) {
        try {
          // Verify token and get user profile
          const { data } = await apiClient.get<User>('/api/auth/me');
          setUser(data);
        } catch (error) {
          // API interceptor will handle token refresh and potential logout
          console.error("Failed to load user profile", error);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = (access_token: string, refresh_token: string, userData: User) => {
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    setUser(userData);
  };

  const logout = async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      if (refreshToken) {
        await apiClient.post('/api/auth/logout', { refresh_token: refreshToken });
      }
    } catch (error) {
      console.error("Logout error", error);
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
