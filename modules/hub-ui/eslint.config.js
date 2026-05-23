import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'src/generated']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // TODO: Refactor ScheduleConfigs to set preselectedTask directly as initial useState state
      // instead of using useEffect. Once refactored, remove this off rule to prevent cascading renders.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  {
    // Allow 'any' types in frontend modules for flexible dynamic mappings with backend payload JSON schemas
    files: ['src/{components,hooks,store,pages}/**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
])