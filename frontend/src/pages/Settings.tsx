import { useEffect, useState } from "react";
import { Cpu, Database, HardDrive, Save, ShieldCheck, SlidersHorizontal, UserRound } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useSettings } from "../components/SettingsProvider";
import { useToast } from "../components/Toast";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ErrorPanel,
  Field,
  LoadingBlock,
  PageHeader,
  Select,
  TextInput,
} from "../components/ui";
import type { Settings } from "../lib/types";

const numberValue = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export default function SettingsPage() {
  const settingsApi = useApi(() => api.settings(), []);
  const systemApi = useApi(() => api.system(), []);
  const { refresh } = useSettings();
  const toast = useToast();
  const [form, setForm] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (settingsApi.data) {
      setForm(settingsApi.data);
      setFormError(null);
    }
  }, [settingsApi.data]);

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  const save = async () => {
    if (!form) return;
    if (!form.display_name.trim()) {
      setFormError("Display name cannot be empty.");
      return;
    }
    if (form.day_end <= form.day_start) {
      setFormError("The working day must end after it starts.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const saved = await api.saveSettings({ ...form, display_name: form.display_name.trim() });
      setForm(saved);
      refresh();
      toast("Preferences saved.");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Settings could not be saved.";
      setFormError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  const system = systemApi.data;

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Preferences and integrations."
        description="Personal preferences shape the planner window and how times are displayed. Integration status is read directly from the backend."
        actions={
          <Button variant="primary" icon={<Save className="size-4" />} loading={saving} disabled={!form} onClick={save}>
            Save changes
          </Button>
        }
      />

      {settingsApi.error && <div className="mb-4"><ErrorPanel message={settingsApi.error} onRetry={settingsApi.reload} /></div>}

      {settingsApi.loading && !form && (
        <Card>
          <LoadingBlock rows={8} label="Loading settings" />
        </Card>
      )}

      {form && (
        <div className="grid animate-enter gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-4">
            <Card>
              <CardHeader
                eyebrow="Profile"
                title="How LifeDesk addresses you"
                action={<UserRound className="size-4 text-muted" />}
              />
              <div className="space-y-4 p-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Display name" htmlFor="settings-name">
                    <TextInput
                      id="settings-name"
                      value={form.display_name}
                      onChange={(event) => update("display_name", event.target.value)}
                      placeholder="Ari Mensah"
                    />
                  </Field>
                  <Field label="Role" htmlFor="settings-role" hint="Used only for display.">
                    <TextInput
                      id="settings-role"
                      value={form.role}
                      onChange={(event) => update("role", event.target.value)}
                      placeholder="Computer science student"
                    />
                  </Field>
                </div>
                <Field label="Workspace label" htmlFor="settings-workspace">
                  <TextInput
                    id="settings-workspace"
                    value={form.workspace}
                    onChange={(event) => update("workspace", event.target.value)}
                    placeholder="Personal desk"
                  />
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Time format" htmlFor="settings-time">
                    <Select
                      id="settings-time"
                      value={form.time_format}
                      onChange={(event) => update("time_format", event.target.value as Settings["time_format"])}
                    >
                      <option value="24h">24-hour · 14:30</option>
                      <option value="12h">12-hour · 2:30 PM</option>
                    </Select>
                  </Field>
                  <Field label="Week starts on" htmlFor="settings-week">
                    <Select
                      id="settings-week"
                      value={form.week_start}
                      onChange={(event) => update("week_start", event.target.value as Settings["week_start"])}
                    >
                      <option value="monday">Monday</option>
                      <option value="sunday">Sunday</option>
                    </Select>
                  </Field>
                </div>
              </div>
            </Card>

            <Card>
              <CardHeader
                eyebrow="Productivity"
                title="Planning window and focus defaults"
                action={<SlidersHorizontal className="size-4 text-muted" />}
              />
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                <Field label="Day starts" htmlFor="settings-day-start" hint="Used by the daily planner.">
                  <TextInput
                    id="settings-day-start"
                    type="time"
                    value={form.day_start}
                    onChange={(event) => update("day_start", event.target.value)}
                  />
                </Field>
                <Field label="Day ends" htmlFor="settings-day-end" hint="Must be after the start time.">
                  <TextInput
                    id="settings-day-end"
                    type="time"
                    value={form.day_end}
                    onChange={(event) => update("day_end", event.target.value)}
                  />
                </Field>
                <Field label="Default focus block" htmlFor="settings-focus" hint="Minutes · 15–480">
                  <TextInput
                    id="settings-focus"
                    type="number"
                    min={15}
                    max={480}
                    step={15}
                    value={form.focus_block_minutes}
                    onChange={(event) =>
                      update("focus_block_minutes", numberValue(event.target.value, form.focus_block_minutes))
                    }
                  />
                </Field>
                <Field label="Default study session" htmlFor="settings-study" hint="Minutes · 15–480">
                  <TextInput
                    id="settings-study"
                    type="number"
                    min={15}
                    max={480}
                    step={15}
                    value={form.default_study_minutes}
                    onChange={(event) =>
                      update("default_study_minutes", numberValue(event.target.value, form.default_study_minutes))
                    }
                  />
                </Field>
                <Field label="Buffer between blocks" htmlFor="settings-buffer" hint="Minutes · 0–60">
                  <TextInput
                    id="settings-buffer"
                    type="number"
                    min={0}
                    max={60}
                    value={form.buffer_minutes}
                    onChange={(event) => update("buffer_minutes", numberValue(event.target.value, form.buffer_minutes))}
                  />
                </Field>
                <Field label="Minimum block length" htmlFor="settings-min-block" hint="Minutes · 15–120">
                  <TextInput
                    id="settings-min-block"
                    type="number"
                    min={15}
                    max={120}
                    value={form.min_block_minutes}
                    onChange={(event) =>
                      update("min_block_minutes", numberValue(event.target.value, form.min_block_minutes))
                    }
                  />
                </Field>
              </div>
              {formError && (
                <p className="mx-5 mb-5 rounded border border-clay/30 bg-clay/[0.06] px-3 py-2 text-[12px] text-clay">
                  {formError}
                </p>
              )}
              <div className="flex items-center justify-between gap-2 border-t border-line-soft px-5 py-3">
                <p className="text-[11px] text-muted">Preferences persist in the local SQLite database.</p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    if (settingsApi.data) setForm(settingsApi.data);
                    setFormError(null);
                  }}
                >
                  Reset
                </Button>
              </div>
            </Card>
          </div>

          <div className="space-y-4">
            <Card className="border-brass/30 bg-brass/[0.03]">
              <div className="px-5 py-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-brass" />
                  <span className="label-micro text-brass">Demo boundary</span>
                </div>
                <h2 className="serif mt-2 text-[22px] leading-tight text-bone">Demo Mode — Local Data</h2>
                <p className="mt-2 text-[12px] leading-relaxed text-muted">
                  This prototype runs entirely on your machine. No MCP servers, OAuth providers or paid
                  LLM APIs are connected, and nothing sends your data anywhere.
                </p>
                <ul className="mt-3 space-y-1.5 text-[11.5px] text-muted">
                  <li className="flex gap-2"><span className="mt-1.5 size-1 rounded-full bg-brass/70" />SQLite calendar, task and reminder providers</li>
                  <li className="flex gap-2"><span className="mt-1.5 size-1 rounded-full bg-brass/70" />Deterministic intent interpreter</li>
                  <li className="flex gap-2"><span className="mt-1.5 size-1 rounded-full bg-brass/70" />Approval gate before every write</li>
                </ul>
              </div>
            </Card>

            <Card>
              <CardHeader
                eyebrow="Integrations"
                title="Provider status"
                action={<Cpu className="size-4 text-muted" />}
              />
              <div className="divide-y divide-line-soft">
                {(system?.providers ?? []).map((provider) => (
                  <div key={provider.key} className="px-5 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[12.5px] text-bone-dim">{provider.label}</p>
                      <div className="flex items-center gap-1.5">
                        <Badge tone={provider.kind === "local" ? "sage" : "sky"}>{provider.kind}</Badge>
                        <Badge tone={provider.status === "connected" ? "sage" : "neutral"} dot>
                          {provider.status === "connected" ? "Connected" : "Not configured"}
                        </Badge>
                      </div>
                    </div>
                    <p className="mt-1 font-mono text-[10px] text-muted">
                      {provider.key} · {provider.transport}
                    </p>
                    <p className="mt-1 text-[11px] leading-relaxed text-muted">{provider.note}</p>
                  </div>
                ))}
                {!system && <div className="px-5 py-4 text-[12px] text-muted">Loading provider status…</div>}
              </div>
            </Card>

            <Card>
              <CardHeader eyebrow="AI" title="Interpreter mode" />
              <div className="px-5 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="brass">{system?.ai.mode ?? "deterministic"}</Badge>
                  <Badge tone="outline">
                    {system?.ai.llm_configured ? "LLM configured" : "No LLM configured"}
                  </Badge>
                  {system?.ai.requires_api_key === false && <Badge tone="sage">No API key</Badge>}
                </div>
                <p className="mt-2 text-[12px] leading-relaxed text-muted">
                  {system?.ai.description ??
                    "Deterministic keyword rules over local data. Reliable offline, with no paid API."}
                </p>
                <div className="mt-3 space-y-1">
                  {(system?.ai.supported_intents ?? []).map((intent) => (
                    <p key={intent.intent} className="text-[11px] text-muted">
                      <span className="text-bone-dim">{intent.example}</span>
                    </p>
                  ))}
                </div>
              </div>
            </Card>

            <Card>
              <CardHeader eyebrow="System" title="Storage & integrations" action={<Database className="size-4 text-muted" />} />
              <div className="space-y-3 px-5 py-4">
                <div className="flex items-start gap-2.5">
                  <HardDrive className="mt-0.5 size-3.5 text-muted" />
                  <div>
                    <p className="text-[12px] text-bone-dim">
                      {system?.storage.engine ?? "SQLite"} · persistent
                    </p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-muted">
                      {system?.storage.note ?? "Changes survive backend restarts."}
                    </p>
                  </div>
                </div>
                <div className="space-y-2 border-t border-line-soft pt-3">
                  {(system?.integrations ?? []).map((integration) => (
                    <div key={integration.name} className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-[12px] text-bone-dim">{integration.name}</p>
                        <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted">{integration.detail}</p>
                      </div>
                      <Badge tone="neutral">Not configured</Badge>
                    </div>
                  ))}
                </div>
                <p className="border-t border-line-soft pt-3 font-mono text-[10px] text-muted">
                  {system?.app ?? "LifeDesk"} v{system?.version ?? "0.9.0"} · provider mode{" "}
                  {system?.provider_mode ?? "local"}
                </p>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
