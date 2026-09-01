"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Save } from "lucide-react";
import RequireAuth from "@/components/auth/RequireAuth";
import { AUTH_CHANGE_EVENT, AuthUser, getCurrentUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import styles from "./settings.module.css";

function SettingsContent() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => { void getCurrentUser().then((account) => { setUser(account); setFullName(account?.full_name ?? ""); setPhone(account?.phone ?? ""); }); }, []);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setMessage("");
    try {
      const updated = await apiFetch("/api/v1/auth/me", { method: "PATCH", body: JSON.stringify({ full_name: fullName, phone: phone || null }) }) as AuthUser;
      setUser(updated); setFullName(updated.full_name); setPhone(updated.phone ?? ""); setMessage("Your profile has been updated."); window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not update your profile."); } finally { setSaving(false); }
  }
  return <main className={styles.page}><div className={styles.kicker}>Account settings</div><h1>Keep your profile up to date</h1><p>Manage the contact details used for your Shopy account. Your email is your sign-in identity and is not changed here.</p><form className={styles.form} onSubmit={save}><label>Full name<input value={fullName} onChange={(event) => setFullName(event.target.value)} minLength={2} required /></label><label>Email<input value={user?.email ?? ""} disabled /></label><label>Phone number<input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="Add a phone number" /></label>{message && <div className={styles.message}><CheckCircle2 size={17} />{message}</div>}<button type="submit" disabled={saving}><Save size={16} />{saving ? "Saving…" : "Save changes"}</button></form></main>;
}
export default function SettingsPage() { return <RequireAuth><SettingsContent /></RequireAuth>; }
