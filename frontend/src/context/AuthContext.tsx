import React, { createContext, useContext, useState, ReactNode } from 'react';

interface User {
  name: string;
  role: 'admin' | 'worker';
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => boolean;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const login = (username: string, password: string): boolean => {
    // Admin credentials
    if (username === 'admin' && password === 'admin123') {
      setUser({ name: 'Neural Ninjas (Admin)', role: 'admin' });
      return true;
    }
    // Worker credentials
    if (username === 'worker' && password === 'worker123') {
      setUser({ name: 'Neural Ninjas (Worker)', role: 'worker' });
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
