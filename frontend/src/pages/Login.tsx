import { useState, type FormEvent } from "react";
import { KeyRound, Loader2, LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../components/AuthProvider";
import { Button, ErrorPanel, Field, TextInput } from "../components/ui";

export default function LoginPage() {
  const { status, error, login, setup, refresh } = useAuth();
  const setupMode = status ? !status.configured : false;
  const [displayName, setDisplayName] = useState("Ari Mensha");
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const cleanUser = username.trim();
    const cleanName = displayName.trim();
    if (setupMode && !cleanName) {
      setFormError("Enter the profile name shown across LifeDesk.");
      return;
    }
    if (!cleanUser) {
      setFormError("Enter the workspace username.");
      return;
    }
    if (password.length < 8) {
      setFormError("Use at least 8 characters for the password.");
      return;
    }
    if (setupMode && password !== confirm) {
      setFormError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      if (setupMode) {
        await setup(cleanName, cleanUser, password);
      } else {
        await login(cleanUser, password);
      }
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : "Sign-in failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  if (!status && !error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-950">
        <div className="flex items-center gap-2 text-[12.5px] text-muted">
          <Loader2 className="spin size-4 text-brass" /> Checking workspace lock…
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(600px circle at 15% 10%, rgba(124,92,255,0.18), transparent 45%), radial-gradient(520px circle at 90% 85%, rgba(84,180,160,0.10), transparent 45%)",
        }}
        aria-hidden
      />
      <div className="relative grid w-full max-w-[980px] gap-5 lg:grid-cols-[1.05fr_1fr]">
        <section className="panel animate-enter flex flex-col justify-between overflow-hidden px-7 py-8 sm:px-9 sm:py-10">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-[12px] border border-white/20 bg-[linear-gradient(140deg,#a493ff_0%,#6f5bf0_55%,#4c3bd1_100%)] shadow-[0_8px_22px_-8px_rgba(124,92,255,0.95),inset_0_1px_0_rgba(255,255,255,0.4)]">
                <Sparkles className="size-[18px] text-white" />
              </div>
              <div>
                <p className="text-[17px] font-semibold leading-none tracking-[-0.02em] text-bone">LifeDesk</p>
                <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.2em] text-muted">Workflow studio</p>
              </div>
            </div>

            <div className="mt-9 inline-flex items-center gap-2 rounded-full border border-brass/30 bg-brass/[0.09] px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-[#c7bcff]">
              <LockKeyhole className="size-3" /> Workspace locked
            </div>
            <h1 className="serif mt-4 text-[31px] leading-[1.08] tracking-[-0.03em] text-bone sm:text-[37px]">
              {setupMode ? (
                <>Secure this workspace<br />before the first plan.</>
              ) : (
                <>Sign in to open<br />your command center.</>
              )}
            </h1>
            <p className="mt-3 max-w-md text-[13px] leading-relaxed text-muted">
              {setupMode
                ? "LifeDesk is local-first, so it ships locked. Create the single owner password now; it is stored only on this machine."
                : "Every calendar, task, reminder and automation route is gated by your session. Nothing loads until you sign in."}
            </p>
          </div>

          <ul className="mt-8 space-y-2.5 text-[11.5px] leading-relaxed text-muted">
            <li className="flex gap-2.5">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-brass/80" />
              PBKDF2-SHA256 password hash with a random salt — never plain text.
            </li>
            <li className="flex gap-2.5">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-brass/80" />
              HttpOnly, SameSite=Lax session cookie; the server stores only its hash.
            </li>
            <li className="flex gap-2.5">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-brass/80" />
              Approval gate still applies to every write after login.
            </li>
          </ul>
        </section>

        <section className="panel animate-enter px-6 py-7 sm:px-7">
          <div className="flex items-center gap-2">
            <KeyRound className="size-4 text-brass" />
            <span className="label-micro">{setupMode ? "First-run setup" : "Owner sign-in"}</span>
          </div>
          <h2 className="mt-2 text-[21px] leading-tight text-bone">
            {setupMode ? "Create the owner password" : "Welcome back"}
          </h2>
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
            {setupMode
              ? "This is the only account. Choose a password you can remember; there is no email reset in local mode."
              : "Use the owner credentials configured for this workspace."}
          </p>

          {error && (
            <div className="mt-4">
              <ErrorPanel message={error} onRetry={() => void refresh()} />
            </div>
          )}
          {formError && (
            <p className="mt-4 rounded border border-clay/30 bg-clay/[0.06] px-3 py-2 text-[12px] text-clay">
              {formError}
            </p>
          )}

          <form className="mt-5 space-y-3.5" onSubmit={submit}>
            {setupMode && (
              <Field
                label="Profile name"
                htmlFor="auth-display-name"
                hint="Used in the greeting, sidebar, avatar and reports."
              >
                <TextInput
                  id="auth-display-name"
                  autoComplete="name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Ari Mensha"
                  disabled={busy}
                />
              </Field>
            )}
            <Field label="Username" htmlFor="auth-username">
              <TextInput
                id="auth-username"
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="owner"
                disabled={busy}
              />
            </Field>
            <Field
              label="Password"
              htmlFor="auth-password"
              hint={setupMode ? "At least 8 characters." : undefined}
            >
              <TextInput
                id="auth-password"
                type="password"
                autoComplete={setupMode ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                disabled={busy}
              />
            </Field>
            {setupMode && (
              <Field label="Confirm password" htmlFor="auth-confirm">
                <TextInput
                  id="auth-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  placeholder="••••••••"
                  disabled={busy}
                />
              </Field>
            )}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={busy}
              icon={<LockKeyhole className="size-4" />}
              disabled={!username.trim() || !password}
            >
              {setupMode ? "Create workspace lock" : "Sign in"}
            </Button>
          </form>

          <p className="mt-4 border-t border-line-soft pt-3 text-[10.5px] leading-relaxed text-muted">
            {setupMode
              ? "After setup, restarting the backend keeps the account. Delete backend/lifedesk.db to reset the workspace."
              : "Too many failed attempts are throttled per username."}
          </p>
        </section>
      </div>
    </div>
  );
}
