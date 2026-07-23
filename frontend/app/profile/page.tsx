"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Check, Clock3, KeyRound, NotebookPen, Save, UserRound } from "lucide-react";
import { useAuth } from "@/components/auth-provider";

type Mock = {
  id: string;
  track: string;
  score: number;
  total_questions: number;
  correct_answers: number;
  duration_seconds: number;
  completed_at: string;
};

type SavedNote = {
  id: string;
  body?: string;
  module: string;
};

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [mocks, setMocks] = useState<Mock[]>([]);
  const [notes, setNotes] = useState<SavedNote[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [passwordPending, setPasswordPending] = useState(false);

  useEffect(() => {
    Promise.all(
      ["mock-exams", "notes"].map((path) =>
        fetch(`/api/account/progress/${path}`).then((response) => response.ok ? response.json() : [])
      )
    ).then(([savedMocks, savedNotes]) => {
      setMocks(savedMocks);
      setNotes(savedNotes);
    }).catch(() => {
      setMocks([]);
      setNotes([]);
    });
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/account/profile", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        display_name: form.get("display_name"),
        first_name: form.get("first_name") || null,
        last_name: form.get("last_name") || null,
        preferred_track: form.get("preferred_track") || null,
        timezone: form.get("timezone"),
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(data.detail || "Unable to update profile.");
      return;
    }
    await refresh();
    setNotice("Profile saved.");
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const passwordForm = event.currentTarget;
    const form = new FormData(passwordForm);
    const currentPassword = String(form.get("current_password") || "");
    const newPassword = String(form.get("new_password") || "");
    const confirmation = String(form.get("confirm") || "");

    setError("");
    setNotice("");
    if (newPassword !== confirmation) {
      setError("New passwords do not match.");
      return;
    }
    if (currentPassword === newPassword) {
      setError("New password must be different from the current password.");
      return;
    }

    setPasswordPending(true);
    try {
      const response = await fetch("/api/account/auth/change-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.detail || "Unable to change password.");
        return;
      }
      passwordForm.reset();
      setNotice(data.message || "Password updated successfully.");
    } catch {
      setError("The account service is temporarily unavailable.");
    } finally {
      setPasswordPending(false);
    }
  }

  return (
    <div className="profile-page">
      <section className="profile-hero">
        <div className="profile-avatar">{(user?.display_name || "D").slice(0, 1).toUpperCase()}</div>
        <div><span>PERSONAL STUDY SPACE</span><h1>{user?.display_name || "Your profile"}</h1><p>{user?.email}</p></div>
        <Link href="/progress">View analytics →</Link>
      </section>

      {(notice || error) ? <div className={error ? "profile-notice error" : "profile-notice"} role={error ? "alert" : "status"}>{error || notice}</div> : null}

      <div className="profile-layout">
        <div className="profile-main">
          <section className="profile-panel">
            <div className="profile-panel-title"><UserRound /><div><span>ACCOUNT</span><h2>Profile details</h2></div></div>
            <form className="profile-form" onSubmit={saveProfile}>
              <label><span>Display name</span><input name="display_name" defaultValue={user?.display_name || ""} required /></label>
              <div className="form-pair">
                <label><span>First name</span><input name="first_name" defaultValue={user?.first_name || ""} /></label>
                <label><span>Last name</span><input name="last_name" defaultValue={user?.last_name || ""} /></label>
              </div>
              <div className="form-pair">
                <label><span>Preferred exam</span><select name="preferred_track" defaultValue={user?.preferred_track || ""}><option value="">Not selected</option><option value="citizenship">Citizenship</option><option value="pr">Permanent Residence</option></select></label>
                <label><span>Timezone</span><input name="timezone" defaultValue={user?.timezone || "Europe/Copenhagen"} /></label>
              </div>
              <button type="submit"><Save size={16} /> Save profile</button>
            </form>
          </section>

          <section className="profile-panel">
            <div className="profile-panel-title"><KeyRound /><div><span>SECURITY</span><h2>Change password</h2></div></div>
            <form className="profile-form" onSubmit={changePassword}>
              <label><span>Current password</span><input name="current_password" type="password" autoComplete="current-password" required /></label>
              <div className="form-pair">
                <label><span>New password</span><input name="new_password" type="password" autoComplete="new-password" minLength={8} required /></label>
                <label><span>Confirm password</span><input name="confirm" type="password" autoComplete="new-password" minLength={8} required /></label>
              </div>
              <button type="submit" disabled={passwordPending}><KeyRound size={16} /> {passwordPending ? "Updating…" : "Update password"}</button>
            </form>
          </section>

          <section className="profile-panel">
            <div className="profile-panel-title"><Check /><div><span>EXAM HISTORY</span><h2>Completed mock exams</h2></div></div>
            {mocks.length ? <div className="history-list">{mocks.map((mock) => <article key={mock.id}><div><strong>{mock.track === "pr" ? "Permanent Residence" : "Citizenship"}</strong><span>{new Date(mock.completed_at).toLocaleDateString()}</span></div><b>{mock.score}/{mock.total_questions}</b><span><Clock3 size={14} />{Math.round(mock.duration_seconds / 60)} min</span></article>)}</div> : <p className="profile-empty">Completed mock exams will appear here. Interrupted exams are never restored.</p>}
          </section>
        </div>

        <aside className="profile-side">
          <section className="profile-panel">
            <div className="profile-panel-title"><NotebookPen /><div><span>STUDY NOTES</span><h2>Recent notes</h2></div></div>
            {notes.length ? <div className="saved-list">{notes.map((item) => <article key={item.id}><strong>{item.module.replaceAll("_", " ")}</strong><p>{item.body}</p></article>)}</div> : <p className="profile-empty">Notes saved while reading and practising will appear here.</p>}
          </section>
        </aside>
      </div>
    </div>
  );
}
