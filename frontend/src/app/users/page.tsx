"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth, type SignedInUser } from "@/components/auth";
import { request } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorState, SectionHeading } from "@/components/feedback";

export default function UsersPage() {
  const {user} = useAuth();
  const cache = useQueryClient();
  const [name, setName] = useState("");
  const [editing, setEditing] = useState("");
  const [editedName, setEditedName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"employee" | "reviewer" | "admin">("employee");
  const listing = useQuery({queryKey: ["users"], queryFn: () => request<(SignedInUser & {active: boolean})[]>("/admin/users"), enabled: user?.role === "admin"});
  const create = useMutation({mutationFn: () => request("/admin/users", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email, password, role, display_name: name})}), onSuccess: () => {setName(""); setEmail(""); setPassword(""); cache.invalidateQueries({queryKey:["users"]});}});
  const status = useMutation({mutationFn: ({id, active}: {id: string; active: boolean}) => request(`/admin/users/${encodeURIComponent(id)}/status`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({active})}), onSuccess: () => cache.invalidateQueries({queryKey:["users"]})});
  const rename = useMutation({mutationFn: () => request(`/admin/users/${encodeURIComponent(editing)}/profile`, {method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({display_name: editedName})}), onSuccess: () => {setEditing(""); cache.invalidateQueries({queryKey:["users"]});}});
  if (user?.role !== "admin") return <p>Administrator permission is required.</p>;
  return <><SectionHeading eyebrow="Administration" title="Users" description="Manage accounts within your organization. Passwords are hashed; account disable revokes existing sessions."/>
    <div className="grid gap-6 lg:grid-cols-2"><Card className="p-6"><form className="space-y-4" onSubmit={e => {e.preventDefault(); create.mutate();}}><h2 className="font-semibold">Create an account</h2><label className="block text-sm">Name<Input aria-label="New user name" required maxLength={100} value={name} onChange={e => setName(e.target.value)}/></label><label className="block text-sm">Email<Input aria-label="New user email" type="email" required value={email} onChange={e => setEmail(e.target.value)}/></label><label className="block text-sm">Initial password<Input aria-label="Initial password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)}/></label><label className="block text-sm">Role<select className="ml-3 rounded border border-stroke p-2" value={role} onChange={e => setRole(e.target.value as typeof role)}><option value="employee">Employee</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></select></label><Button disabled={create.isPending}>Create account</Button>{create.isError && <ErrorState error={create.error}/>} {create.isSuccess && <p role="status">Account created.</p>}</form></Card>
    <Card className="space-y-4 p-6">{listing.isError && <ErrorState error={listing.error}/>} {status.isError && <ErrorState error={status.error}/>} {rename.isError && <ErrorState error={rename.error}/>} {listing.data?.map(account => <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stroke pb-3" key={account.id}><div><p className="text-sm font-semibold">{account.display_name || "Unnamed user"}</p><p className="text-xs text-muted">{account.email}</p><p className="text-xs text-muted">{account.role} · {account.active ? "Active" : "Disabled"}</p></div><button className="text-xs text-primary" onClick={() => {setEditing(account.id); setEditedName(account.display_name || "");}}>Edit name</button>{editing === account.id && <form className="flex gap-2" onSubmit={e => {e.preventDefault(); rename.mutate();}}><Input aria-label="Updated user name" required maxLength={100} value={editedName} onChange={e => setEditedName(e.target.value)}/><Button size="sm" disabled={rename.isPending}>Save</Button><Button type="button" size="sm" variant="secondary" onClick={() => setEditing("")}>Cancel</Button></form>}<Button size="sm" variant="secondary" disabled={account.id === user.id || status.isPending} onClick={() => status.mutate({id:account.id, active:!account.active})}>{account.active ? "Disable" : "Enable"}</Button></div>)}</Card></div>
  </>;
}
