import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { fetchCurrentUser, jAccountLogoutUrl } from "../api/auth";
import type { AuthResult, AuthUser } from "../api/auth";
import {
  clearAssessmentLocalData,
  clearExpiredAssessmentStorage,
  clearLegacyAssessmentStorage
} from "../storage/assessmentStorage";

const TOKEN_KEY = "siyuan_auth_token";
const USER_KEY = "siyuan_auth_user";
export const AUTH_UNAUTHORIZED_EVENT = "siyuan:auth-unauthorized";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  completeLogin: (result: AuthResult) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredUser(): AuthUser | null {
  try {
    const value = window.localStorage.getItem(USER_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function clearStoredAuth() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(readStoredUser);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let closed = false;
    fetchCurrentUser()
      .then((currentUser) => {
        if (closed) return;
        setUser(currentUser);
        if (currentUser.authSource === "local") {
          window.localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
        } else {
          window.localStorage.removeItem(TOKEN_KEY);
          window.localStorage.removeItem(USER_KEY);
        }
      })
      .catch(() => {
        if (closed) return;
        window.localStorage.removeItem(TOKEN_KEY);
        window.localStorage.removeItem(USER_KEY);
        setUser(null);
      })
      .finally(() => {
        if (!closed) setLoading(false);
      });
    return () => {
      closed = true;
    };
  }, []);

  useEffect(() => {
    clearExpiredAssessmentStorage();
    clearLegacyAssessmentStorage();
    const handleUnauthorized = () => setUser((currentUser) => {
      if (currentUser) clearAssessmentLocalData(currentUser.id);
      return null;
    });
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    completeLogin(result) {
      if (user && user.id !== result.user.id) {
        clearAssessmentLocalData(user.id);
      }
      window.localStorage.setItem(TOKEN_KEY, result.token);
      window.localStorage.setItem(USER_KEY, JSON.stringify(result.user));
      setUser(result.user);
    },
    logout() {
      if (user) clearAssessmentLocalData(user.id);
      clearStoredAuth();
      setUser(null);
      if (user?.authSource === "jaccount") {
        window.location.assign(jAccountLogoutUrl());
      }
    }
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth 必须在 AuthProvider 中使用");
  return value;
}
