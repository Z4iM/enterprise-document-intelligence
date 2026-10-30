"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRound } from "lucide-react";
import { useAuth, type SignedInUser } from "@/components/auth";
import { request } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const labels: Record<string, string> = {
  documents_uploaded: "Documents uploaded",
  documents_reviewed: "Documents reviewed",
  reviews_completed: "Review decisions",
  policies_uploaded: "Policies uploaded",
  rules_approved: "Rules approved",
  active_users: "Active users in organization",
};

export function ProfileMenu() {
  const {user, logout, updateUser} = useAuth();
  const cache = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [editingPassword, setEditingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const profile = useQuery({queryKey: ["my-profile"], queryFn: () => request<{user: SignedInUser; stats: Record<string, number>}>("/auth/profile"), enabled: open, staleTime: 0});
  function toggle() {
    setName(user?.display_name || ""); setError(""); setMessage("");
    setEditingPassword(false); setCurrentPassword(""); setNewPassword(""); setConfirmation("");
    setOpen(!open);
  }
  return <div className="relative" onKeyDown={event => { if (event.key === "Escape" && !busy) {setOpen(false); setCurrentPassword(""); setNewPassword(""); setConfirmation("");} }}>
    <button type="button" aria-label="Open user profile" aria-expanded={open} aria-controls="user-profile" className="flex h-10 w-10 items-center justify-center rounded-full border border-stroke bg-[#f4f3ff] text-primary hover:bg-[#e9e7ff]" onClick={toggle}><UserRound size={19}/></button>
    {open && <section id="user-profile" aria-label="Your profile" className="absolute right-0 top-12 max-h-[80vh] w-[min(360px,calc(100vw-2rem))] space-y-5 overflow-y-auto rounded-2xl border border-stroke bg-white p-5 shadow-xl">
      <div><h2 className="font-semibold">{user?.display_name || "Your profile"}</h2><p className="break-all text-xs text-muted">{user?.email}</p><p className="mt-1 text-xs capitalize text-primary">{user?.role}</p></div>
      <form className="space-y-2" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError(""); setMessage("");
        try {const updated = await request<SignedInUser>("/auth/profile", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({display_name: name})}); updateUser(updated); cache.invalidateQueries(); setMessage("Name updated.");}
        catch (reason) {setError(reason instanceof Error ? reason.message : "Update failed.");}
        finally {setBusy(false);}
      }}><label className="block text-xs font-semibold">Your name<Input aria-label="Your name" autoComplete="name" required maxLength={100} value={name} onChange={e => setName(e.target.value)}/></label><Button size="sm" disabled={busy || !name.trim()}>Save name</Button></form>
      <div><h3 className="mb-2 text-xs font-semibold">Your activity · all time</h3>{profile.isLoading ? <p role="status" className="text-xs">Loading activity…</p> : profile.isError ? <p role="alert" className="text-xs text-red-700">Could not load activity.</p> : <dl className="space-y-2">{Object.entries(profile.data?.stats || {}).map(([key, count]) => <div key={key} className="flex justify-between gap-3 text-xs"><dt className="text-muted">{labels[key] || key}</dt><dd className="font-semibold">{count}</dd></div>)}</dl>}</div>
      {user?.role === "admin" && <Link href="/users" onClick={() => setOpen(false)} className="block text-xs font-semibold text-primary">Manage users</Link>}
      <button type="button" className="text-xs font-semibold text-primary" onClick={() => {setEditingPassword(!editingPassword); setError(""); setMessage(""); setCurrentPassword(""); setNewPassword(""); setConfirmation("");}}>Change password</button>
      {editingPassword && <form className="space-y-3 border-t border-stroke pt-3" onSubmit={async event => {
        event.preventDefault(); setError(""); setMessage("");
        if (newPassword !== confirmation) {setError("New passwords must match."); return;}
        setBusy(true);
        try {await request("/auth/change-password", {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({current_password: currentPassword, new_password: newPassword})}); setMessage("Password changed. Other sessions have been signed out."); setEditingPassword(false);}
        catch (reason) {setError(reason instanceof Error ? reason.message : "Password change failed.");}
        finally {setBusy(false); setCurrentPassword(""); setNewPassword(""); setConfirmation("");}
      }}>
        <label className="block text-xs">Current password<Input aria-label="Current password" type="password" autoComplete="current-password" required maxLength={128} value={currentPassword} onChange={e => setCurrentPassword(e.target.value)}/></label>
        <label className="block text-xs">New password<Input aria-label="New password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={e => setNewPassword(e.target.value)}/></label>
        <label className="block text-xs">Confirm new password<Input aria-label="Confirm new password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmation} onChange={e => setConfirmation(e.target.value)}/></label>
        <p className="text-xs text-muted">12–128 characters. Existing sessions will be revoked.</p><Button size="sm" disabled={busy}>Update password</Button>
      </form>}
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}{message && <p role="status" className="text-xs text-green-700">{message}</p>}
      <button type="button" disabled={busy} className="block text-xs font-semibold text-primary" onClick={async () => {setBusy(true); setError(""); try {await logout();} catch {setError("Sign out failed; try again.");} finally {setBusy(false);}}}>Sign out</button>
    </section>}
  </div>;
}
