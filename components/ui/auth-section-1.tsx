"use client";

import { GrainGradient } from "@paper-design/shaders-react";
import { BotIcon } from "lucide-react";
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";

const termsText = (
  <>
    By creating an account, you agree to our{" "}
    <a
      href="#"
      className="font-medium text-black/45 underline underline-offset-2 dark:text-white/45"
    >
      Terms and Services
    </a>{" "}
    and{" "}
    <a
      href="#"
      className="font-medium text-black/45 underline underline-offset-2 dark:text-white/45"
    >
      Privacy Policy
    </a>
  </>
);

export type AuthSectionOneProps = {
  email: string;
  password: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  busy?: boolean;
  error?: string | null;
  /** Slot above the headline — e.g. a theme toggle. */
  header?: ReactNode;
  /** Slot below the submit button — e.g. how an account gets created. */
  note?: ReactNode;
};

export default function AuthSectionOne({
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  busy = false,
  error = null,
  header,
  note,
}: AuthSectionOneProps) {
  return (
    <section className="min-h-screen bg-white p-3 text-black antialiased [font-synthesis:none] dark:bg-[#050505] dark:text-white">
      <div className="grid min-h-[calc(100vh-1.5rem)] gap-6 lg:grid-cols-[0.94fr_1.06fr]">
        <div className="flex min-h-[760px] items-start rounded-md border border-black/20 bg-white px-6 py-12 sm:px-10 dark:border-white/10 dark:bg-[#0a0a0a] lg:min-h-0 lg:px-14 lg:py-28 xl:px-20">
          <div className="mx-auto w-full max-w-[590px]">
            {header && (
              <div className="mb-8 flex items-center justify-between">{header}</div>
            )}

            <div>
              <h1 className="whitespace-nowrap text-3xl font-medium tracking-[-0.04em] sm:text-4xl lg:text-[42px] lg:leading-[1.05] xl:text-[50px]">
                Sign in
              </h1>
              <p className="mt-3 text-lg leading-snug text-black/60 dark:text-white/55 sm:text-xl lg:text-2xl xl:text-3xl">
                Approvals are recorded against this account.
              </p>
            </div>

            <form onSubmit={onSubmit} className="mt-12 space-y-5">
              <FieldBox
                label="Email"
                value={email}
                type="email"
                autoComplete="username"
                required
                onChange={onEmailChange}
              />
              <FieldBox
                label="Password"
                value={password}
                type="password"
                autoComplete="current-password"
                required
                onChange={onPasswordChange}
              />

              <div className="space-y-4 pt-2 text-sm leading-5 text-black/30 dark:text-white/35 sm:text-[15px]">
                <CheckboxLine>
                  I don&apos;t want to receive emails about solaceui feature updates
                </CheckboxLine>
                <CheckboxLine>{termsText}</CheckboxLine>
              </div>

              {error && (
                <p
                  role="alert"
                  className="text-sm leading-5 text-rose-700 dark:text-rose-400"
                >
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={busy}
                className="mt-9 flex h-12 w-full items-center justify-center rounded-[10px] border border-black/40 bg-black text-xl font-medium text-white transition-colors hover:bg-black/85 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/40 dark:bg-white dark:text-black dark:hover:bg-white/85"
              >
                {busy ? "Checking…" : "Sign in"}
              </button>
            </form>

            {note && (
              <div className="mt-8 font-mono text-[11px] leading-relaxed text-black/40 dark:text-white/40">
                {note}
              </div>
            )}
          </div>
        </div>

        <div className="relative flex min-h-[720px] overflow-hidden rounded-md bg-black p-8 text-white sm:p-12 lg:min-h-0">
          <GrainGradient
            speed={1}
            scale={1}
            rotation={0}
            offsetX={0}
            offsetY={0}
            softness={0.5}
            intensity={0.5}
            noise={0.25}
            shape="corners"
            frame={2854.5}
            colors={["#FFFFFF", "#FC7819", "#FC7819", "#FFFFFF"]}
            colorBack="#00000000"
            className="absolute inset-0 bg-black"
          />

          <div className="relative z-10 flex h-full w-full flex-col justify-between">
            <h2 className="max-w-[620px] pt-0 text-5xl font-medium tracking-[-0.05em] text-white sm:text-6xl lg:pt-16 lg:text-[64px] lg:leading-[0.98] xl:text-[70px]">
              Think fast,
              <br />
              Build faster
            </h2>

            <a
              href="#"
              className="mb-0 inline-flex h-12 max-w-full items-center gap-3 rounded-[10px] border border-white/25 px-5 text-base font-medium text-white/85 backdrop-blur-sm transition-colors hover:border-white/45 hover:text-white xl:mb-32 xl:px-6 xl:text-2xl"
            >
              <BotIcon className="size-5 shrink-0 xl:size-7" />
              <span className="truncate whitespace-nowrap">
                SIGAP | Supply Chain Agentic AI
              </span>
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

function FieldBox({
  label,
  value,
  type = "text",
  autoComplete,
  required = false,
  onChange,
}: {
  label: string;
  value: string;
  type?: string;
  autoComplete?: string;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  const [focused, setFocused] = useState(false);
  /* The label stands in for a placeholder: it sits to the right while the field
   * is empty, and leaves as soon as the field is focused or holds a value. */
  const showLabel = !focused && !value;

  return (
    <label className="flex h-14 items-center justify-between gap-4 rounded-[10px] border border-black/25 bg-white px-5 text-sm leading-none dark:border-white/15 dark:bg-white/5">
      <input
        type={type}
        value={value}
        aria-label={label}
        autoComplete={autoComplete}
        required={required}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 flex-1 truncate bg-transparent text-black outline-none placeholder:text-black/30 dark:text-white dark:placeholder:text-white/35"
      />
      {showLabel && (
        <span className="shrink-0 text-black dark:text-white">{label}</span>
      )}
    </label>
  );
}

function CheckboxLine({ children }: { children: ReactNode }) {
  return (
    <label className="flex items-start gap-3">
      <span className="relative mt-1 size-3.5 shrink-0">
        <input
          type="checkbox"
          className="peer size-full appearance-none rounded-[2px] border border-black/25 bg-white checked:border-black checked:bg-black dark:border-white/30 dark:bg-white/5 dark:checked:border-white dark:checked:bg-white"
        />
        <svg
          viewBox="0 0 12 12"
          className="pointer-events-none absolute inset-0 hidden size-full p-0.5 text-white peer-checked:block dark:text-black"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 6.2 5 8.1 9 3.9"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span>{children}</span>
    </label>
  );
}

function WindowsIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 4.7 10.7 3.6v7.7H3V4.7Zm8.8-1.25L21 2.1v9.2h-9.2V3.45ZM3 12.7h7.7v7.7L3 19.3v-6.6Zm8.8 0H21v9.2l-9.2-1.3v-7.9Z" />
    </svg>
  );
}
