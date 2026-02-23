 import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
 import { api, User, setAuthToken, getAuthToken, ApiError } from '@/lib/api';
 
 interface AuthContextType {
   user: User | null;
   isLoading: boolean;
   isAuthenticated: boolean;
   login: (email: string, password: string) => Promise<void>;
   register: (email: string, password: string, companyName: string) => Promise<void>;
   logout: () => void;
   error: string | null;
   clearError: () => void;
 }
 
 const AuthContext = createContext<AuthContextType | undefined>(undefined);
 
 export function AuthProvider({ children }: { children: ReactNode }) {
   const [user, setUser] = useState<User | null>(null);
   const [isLoading, setIsLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
 
   // Check for existing token on mount
   useEffect(() => {
     const initAuth = async () => {
       const token = getAuthToken();
       if (token) {
         try {
           const userData = await api.auth.me();
           setUser(userData);
         } catch {
           // Token invalid, clear it
           setAuthToken(null);
         }
       }
       setIsLoading(false);
     };
 
     initAuth();
   }, []);
 
   const login = async (email: string, password: string) => {
     setError(null);
     setIsLoading(true);
     try {
       const response = await api.auth.login({ username: email, password });
       setAuthToken(response.access_token);
       const userData = await api.auth.me();
       setUser(userData);
     } catch (err) {
       const message = err instanceof ApiError ? err.message : 'Login failed';
       setError(message);
       throw err;
     } finally {
       setIsLoading(false);
     }
   };
 
   const register = async (email: string, password: string, companyName: string) => {
  setError(null);
  setIsLoading(true);
  try {
    // Register returns User, not token
    await api.auth.register({ 
    email, 
    password, 
    company_name: companyName   // ✅ Match backend field name
  });
    
    // Login after successful registration
    const loginResponse = await api.auth.login({ username: email, password });
    setAuthToken(loginResponse.access_token);
    
    // Get user data
    const userData = await api.auth.me();
    setUser(userData);
  } catch (err) {
    const message = err instanceof ApiError ? err.message : 'Registration failed';
    setError(message);
    throw err;
  } finally {
    setIsLoading(false);
  }
};
 
   const logout = () => {
     setAuthToken(null);
     setUser(null);
   };
 
   const clearError = () => setError(null);
 
   return (
     <AuthContext.Provider
       value={{
         user,
         isLoading,
         isAuthenticated: !!user,
         login,
         register,
         logout,
         error,
         clearError,
       }}
     >
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