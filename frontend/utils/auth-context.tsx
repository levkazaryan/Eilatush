'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { vipApi } from "../api";
import { loadAuth, saveAuth, clearAuth, type VIPMember } from "./auth-storage";

type RegisterPayload = {
  full_name: string;
  email: string;
  phone: string;
  dob: string; // YYYY-MM-DD
  address: string;
};

type LoginPayload = {
  phone: string;
  dob: string; // YYYY-MM-DD
};

type AuthContextValue = {
  hydrated: boolean;
  member: VIPMember | null;
  token: string | null;
  login: (p: LoginPayload) => Promise<void>;
  register: (p: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshMember: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [member, setMember] = useState<VIPMember | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { token: t, member: m } = await loadAuth();
        if (t && m) {
          setToken(t);
          setMember(m);
          // Verify token is still valid by hitting /me (best-effort, non-blocking)
          try {
            const fresh = await vipApi.me(t);
            setMember(fresh);
            await saveAuth(t, fresh);
          } catch {
            // token expired or invalid → clear
            await clearAuth();
            setToken(null);
            setMember(null);
          }
        }
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  const login = useCallback(async (p: LoginPayload) => {
    const res = await vipApi.login(p);
    setToken(res.token);
    setMember(res.member);
    await saveAuth(res.token, res.member);
  }, []);

  const register = useCallback(async (p: RegisterPayload) => {
    const res = await vipApi.register(p);
    setToken(res.token);
    setMember(res.member);
    await saveAuth(res.token, res.member);
  }, []);

  const logout = useCallback(async () => {
    await clearAuth();
    setToken(null);
    setMember(null);
  }, []);

  const refreshMember = useCallback(async () => {
    if (!token) return;
    try {
      const fresh = await vipApi.me(token);
      setMember(fresh);
      await saveAuth(token, fresh);
    } catch {
      // ignore
    }
  }, [token]);

  return (
    <AuthContext.Provider value={{ hydrated, member, token, login, register, logout, refreshMember }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
