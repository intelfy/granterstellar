/* eslint-disable */
// Flat config for ESLint v9+
import js from '@eslint/js'

export default [
  // Ignore build artifacts and vendor files
  { ignores: ['dist/**', 'node_modules/**', 'eslint.config.js'] },
  js.configs.recommended,
  // Global overrides (applies to all matched files)
  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        navigator: 'readonly',
        fetch: 'readonly',
        Response: 'readonly',
        Request: 'readonly',
        Headers: 'readonly',
        FormData: 'readonly',
        File: 'readonly',
        alert: 'readonly',
        confirm: 'readonly',
        prompt: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setImmediate: 'readonly',
        queueMicrotask: 'readonly',
        MessageChannel: 'readonly',
        MutationObserver: 'readonly',
        performance: 'readonly',
        reportError: 'readonly',
        __REACT_DEVTOOLS_GLOBAL_HOOK__: 'readonly',
        URLSearchParams: 'readonly',
        URL: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-constant-condition': ['error', { checkLoops: false }],
      'no-empty': 'off',
      'no-prototype-builtins': 'off',
      'no-control-regex': 'off',
      'no-misleading-character-class': 'off',
      'no-console': 'off',
      'no-undef': 'off',
    },
  },
  {
    files: ['src/__tests__/**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        // Vitest / Jest-like globals
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        // jsdom/browser globals used in tests
        window: 'readonly',
        document: 'readonly',
        navigator: 'readonly',
        fetch: 'readonly',
        Response: 'readonly',
        Request: 'readonly',
        Headers: 'readonly',
        FormData: 'readonly',
        File: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        // node-like global for polyfills/mocks
        global: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': 'off',
  'no-undef': 'off',
    },
  },
  // Suppress noisy unused-vars in the large single-file app shell until refactor
  {
  files: ['**/src/main.jsx'],
    rules: {
      'no-unused-vars': 'off',
    },
  },
]
