import { create } from 'zustand';
import { client } from '../generated/api/client.gen';
import { getTaskSpecsApiV1TasksSpecsGet } from '../generated/api/sdk.gen';

interface AuthState {
  apiKey: string | null;
  isAuthenticated: boolean;
  isValidating: boolean;
  login: (key: string) => Promise<boolean>;
  logout: () => void;
  initializeAuth: () => void;
}

// Session storage key for persistent auth
const AUTH_KEY = 'scheduler-api-key';

export const useAuthStore = create<AuthState>((set, get) => ({
  apiKey: null,
  isAuthenticated: false,
  isValidating: false,

  login: async (key: string) => {
    set({ isValidating: true });

    // Temporarily set the key in state to test the request
    const originalKey = get().apiKey;
    set({ apiKey: key });

    try {
      // Try fetching a lightweight protected endpoint to test key validity
      const result = await getTaskSpecsApiV1TasksSpecsGet({ throwOnError: true });

      if (result && result.response && result.response.status === 200) {
        sessionStorage.setItem(AUTH_KEY, key);
        set({ isAuthenticated: true, isValidating: false });
        return true;
      }

      // If not successful status, rollback
      set({ apiKey: originalKey, isAuthenticated: !!originalKey, isValidating: false });
      return false;
    } catch {
      // Rollback on error
      set({ apiKey: originalKey, isAuthenticated: !!originalKey, isValidating: false });
      return false;
    }
  },

  logout: () => {
    sessionStorage.removeItem(AUTH_KEY);
    set({ apiKey: null, isAuthenticated: false });
  },

  initializeAuth: () => {
    const savedKey = sessionStorage.getItem(AUTH_KEY);
    if (savedKey) {
      set({ apiKey: savedKey, isAuthenticated: true });
    }
  },
}));

// Register interceptors once at module load
client.interceptors.request.use((request) => {
  const currentKey = useAuthStore.getState().apiKey || sessionStorage.getItem(AUTH_KEY);
  if (currentKey) {
    request.headers.set('X-API-Key', currentKey);
  }
  return request;
});

function getStatusFromError(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  if ('status' in error && typeof (error as { status: unknown }).status === 'number') {
    return (error as { status: number }).status;
  }
  if ('response' in error) {
    const errResp = (error as { response: unknown }).response;
    if (errResp && typeof errResp === 'object' && 'status' in errResp && typeof (errResp as { status: unknown }).status === 'number') {
      return (errResp as { status: number }).status;
    }
  }
  return undefined;
}

client.interceptors.error.use((error: unknown, response: Response | undefined) => {
  const status = response?.status ?? getStatusFromError(error);

  if (status === 401) {
    useAuthStore.getState().logout();
  }
  return Promise.reject(error);
});