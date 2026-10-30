"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, request } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface SignedInUser {
  id: string;
  email: string;
  display_name: string;
  role: "employee" | "reviewer" | "admin";
  organization_id: string;
}

const Context = createContext<{user: SignedInUser | null; logout: () => Promise<void>; updateUser: (user: SignedInUser) => void}>({user: null, logout: async () => {}, updateUser: () => {}});
export const useAuth = () => useContext(Context);

export function SessionGate({children}: {children: React.ReactNode}) {
  const cache = useQueryClient();
  const [user, setUser] = useState<SignedInUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    const expired = () => { cache.clear(); setUser(null); };
    window.addEventListener("edi-session-expired", expired);
    request<SignedInUser>("/auth/me").then(value => { if (live) setUser(value); })
      .catch(reason => { if (live && !(reason instanceof ApiError && reason.status === 401)) setError(reason.message); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; window.removeEventListener("edi-session-expired", expired); };
  }, [cache]);
  async function logout() {
    await request("/auth/logout", {method: "POST"});
    cache.clear();
    setUser(null);
    setPassword("");
  }
  if (loading) return <div role="status" className="p-12 text-center">Checking session…</div>;
  if (!user) return <main className="flex min-h-screen items-center justify-center bg-canvas p-6">
    <form className="w-full max-w-md space-y-5 rounded-2xl border border-stroke bg-white p-8 shadow-sm" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError("");
      try {
        const result = await request<{user: SignedInUser}>("/auth/login", {
          method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({email, password}),
        });
        cache.clear(); setUser(result.user); setPassword("");
      } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign in failed."); }
      finally { setBusy(false); }
    }}>
      <div><p className="text-xs font-semibold uppercase tracking-widest text-primary">Enterprise Document Intelligence</p><h1 className="mt-3 text-2xl font-bold">Sign in to your workspace</h1></div>
      <label className="block text-sm font-medium">Email<Input className="mt-2" type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)}/></label>
      <label className="block text-sm font-medium">Password<Input className="mt-2" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)}/></label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Button className="w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
      <p className="text-xs leading-5 text-muted">Use an account created by your administrator. Document review and policy-rule approval are separate permissions.</p>
    </form>
  </main>;
  return <Context.Provider value={{user, logout, updateUser: setUser}}>{children}</Context.Provider>;
}
