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

client.interceptors.error.use((error: unknown, response: Response | undefined) => {
  let status: number | undefined = response?.status;
  
  if (!status && error && typeof error === 'object') {
    if ('status' in error) {
      status = (error as { status: number }).status;
    } else if ('response' in error) {
      const errResp = (error as { response: unknown }).response;
      if (errResp && typeof errResp === 'object' && 'status' in errResp) {
        status = (errResp as { status: number }).status;
      }
    }
  }

  if (status === 401) {
    useAuthStore.getState().logout();
  }
  return Promise.reject(error);
});