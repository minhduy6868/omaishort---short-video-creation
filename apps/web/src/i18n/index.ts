import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enCommon from './locales/en/common.json';
import enLanding from './locales/en/landing.json';
import viCommon from './locales/vi/common.json';
import viLanding from './locales/vi/landing.json';
import jaCommon from './locales/ja/common.json';
import jaLanding from './locales/ja/landing.json';

export const SUPPORTED_LANGS = ['en', 'vi', 'ja'] as const;
export type SupportedLang = (typeof SUPPORTED_LANGS)[number];

export const LANG_LABELS: Record<SupportedLang, string> = {
  en: 'English',
  vi: 'Tiếng Việt',
  ja: '日本語',
};

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: enCommon, landing: enLanding },
      vi: { common: viCommon, landing: viLanding },
      ja: { common: jaCommon, landing: jaLanding },
    },
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'landing'],
    interpolation: { escapeValue: false },
    detection: {
      order: ['path', 'localStorage', 'navigator'],
      lookupFromPathIndex: 0,
      caches: ['localStorage'],
    },
  });

export default i18n;
