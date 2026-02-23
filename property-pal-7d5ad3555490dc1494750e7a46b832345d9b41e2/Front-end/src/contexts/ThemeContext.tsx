import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

export type ThemeName = 'midnight-gold' | 'ocean-pro' | 'ember' | 'arctic';

interface ThemeContextType {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const STORAGE_KEY = 'erp_theme';

export const themeConfig: Record<ThemeName, { label: string; color: string }> = {
  'midnight-gold': { label: 'Midnight Gold', color: '#F5C518' },
  'ocean-pro': { label: 'Ocean Pro', color: '#00D4FF' },
  'ember': { label: 'Ember', color: '#FF6B00' },
  'arctic': { label: 'Arctic', color: '#7C3AED' },
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return (stored as ThemeName) || 'midnight-gold';
  });

  const setTheme = (t: ThemeName) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
