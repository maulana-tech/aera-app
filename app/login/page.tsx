"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme";
import AuthSectionOne from "@/components/ui/auth-section-1";

/* The visual is the registry component; the auth is ours. This file owns the
 * session — email and password go to /api/login, which sets an httpOnly cookie
 * the page never sees. Identity is not this component's business.
 */
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error((await res.json()).error ?? "could not sign in");
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSectionOne
      email={email}
      password={password}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onSubmit={submit}
      busy={busy}
      error={error}
      header={<ThemeToggle />}
      note={
        <>
          No account yet? They are created with the admin tool:
          <br />
          python3 manage.py user email name role password
        </>
      }
    />
  );
}
