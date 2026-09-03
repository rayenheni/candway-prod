// ============================================================
// Language Context - Candway Tunisia i18n
// ============================================================

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { dictionaries, type Language } from '@/i18n/dictionaries';

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('candway-lang') as Language;
      if (saved === 'en' || saved === 'fr') return saved;
    }
    return 'en';
  });

  const setLanguage = useCallback((lang: Language) => {
    const targetLang = (lang === 'en' || lang === 'fr') ? lang : 'en';
    setLanguageState(targetLang);
    localStorage.setItem('candway-lang', targetLang);
    
    document.documentElement.dir = 'ltr';
    document.documentElement.lang = targetLang;
  }, []);

  // Initialize on mount
  useEffect(() => {
    setLanguage(language);
  }, [language, setLanguage]);

  const t = useCallback((key: string): string => {
    const dict = dictionaries[language] || dictionaries['en'];
    // Fallback to English if translation is missing in the current language
    return dict[key] || dictionaries['en'][key] || key;
  }, [language]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
