import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCommon from '../locales/en/common.json';
import enNavigation from '../locales/en/navigation.json';
import enUpload from '../locales/en/upload.json';
import enAssignments from '../locales/en/assignments.json';
import enSubmissions from '../locales/en/submissions.json';
import enResults from '../locales/en/results.json';
import enPairComparison from '../locales/en/pair-comparison.json';
import enOverview from '../locales/en/overview.json';
import enStatus from '../locales/en/status.json';
import enLanguages from '../locales/en/languages.json';
import enReview from '../locales/en/review.json';
import enSessions from '../locales/en/sessions.json';
import enStorage from '../locales/en/storage.json';
import enQuickCheck from '../locales/en/quick-check.json';
import enFiles from '../locales/en/files.json';
import enEvents from '../locales/en/events.json';

import ruCommon from '../locales/ru/common.json';
import ruFiles from '../locales/ru/files.json';
import ruEvents from '../locales/ru/events.json';
import ruNavigation from '../locales/ru/navigation.json';
import ruUpload from '../locales/ru/upload.json';
import ruAssignments from '../locales/ru/assignments.json';
import ruSubmissions from '../locales/ru/submissions.json';
import ruResults from '../locales/ru/results.json';
import ruPairComparison from '../locales/ru/pair-comparison.json';
import ruOverview from '../locales/ru/overview.json';
import ruStatus from '../locales/ru/status.json';
import ruLanguages from '../locales/ru/languages.json';
import ruReview from '../locales/ru/review.json';
import ruSessions from '../locales/ru/sessions.json';
import ruStorage from '../locales/ru/storage.json';
import ruQuickCheck from '../locales/ru/quick-check.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        navigation: enNavigation,
        upload: enUpload,
        assignments: enAssignments,
        submissions: enSubmissions,
        results: enResults,
        pairComparison: enPairComparison,
        overview: enOverview,
        status: enStatus,
        languages: enLanguages,
        review: enReview,
        sessions: enSessions,
        storage: enStorage,
        quickCheck: enQuickCheck,
        files: enFiles,
        events: enEvents,
      },
      ru: {
        common: ruCommon,
        navigation: ruNavigation,
        upload: ruUpload,
        assignments: ruAssignments,
        submissions: ruSubmissions,
        results: ruResults,
        pairComparison: ruPairComparison,
        overview: ruOverview,
        status: ruStatus,
        languages: ruLanguages,
        review: ruReview,
        sessions: ruSessions,
        storage: ruStorage,
        quickCheck: ruQuickCheck,
        files: ruFiles,
        events: ruEvents,
      },
    },
    lng: localStorage.getItem('language') || 'en',
    fallbackLng: 'en',
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
