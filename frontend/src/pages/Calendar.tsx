import { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { useSettings } from "../components/SettingsProvider";
import { useToast } from "../components/Toast";
import {
  Button,
  Card,
  ErrorPanel,
  Field,
  LoadingBlock,
  Modal,
  PageHeader,
  Select,
  TextArea,
  TextInput,
} from "../components/ui";
import {
  addDaysISO,
  dateInputValue,
  fmtTime,
  fmtWeekRange,
  startOfWeekISO,
  timeInputValue,
  todayISO,
  weekDates,
} from "../lib/format";
import type { EventItem, EventKind } from "../lib/types";

const GRID_START = 7;
const GRID_END = 22;
const PX_PER_MIN = 0.9;
const HOURS = Array.from({ length: GRID_END - GRID_START }, (_, index) => GRID_START + index);
const GRID_HEIGHT = (GRID_END - GRID_START) * 60 * PX_PER_MIN;
const pad = (value: number) => value.toString().padStart(2, "0");

const KIND_STYLES: Record<string, string> = {
  meeting: "border-sky/60 bg-sky/[0.10] hover:bg-sky/[0.16]",
  focus: "border-brass/60 bg-brass/[0.10] hover:bg-brass/[0.16]",
  study: "border-brass/60 bg-brass/[0.10] hover:bg-brass/[0.16]",
  personal: "border-sage/60 bg-sage/[0.10] hover:bg-sage/[0.16]",
  break: "border-line bg-ink-800 hover:bg-ink-700",
};

const KIND_DOT: Record<string, string> = {
  meeting: "bg-sky",
  focus: "bg-brass",
  study: "bg-brass",
  personal: "bg-sage",
  break: "bg-muted",
};

const KIND_OPTIONS: EventKind[] = ["meeting", "focus", "study", "personal", "break"];

interface EventForm {
  id: string | null;
  title: string;
  date: string;
  start: string;
  end: string;
  location: string;
  kind: EventKind;
  description: string;
}

const blankForm = (date = todayISO()): EventForm => ({
  id: null,
  title: "",
  date,
  start: "09:00",
  end: "10:00",
  location: "",
  kind: "meeting",
  description: "",
});

export default function CalendarPage() {
  const { settings } = useSettings();
  const toast = useToast();
  const [weekStart, setWeekStart] = useState(() => startOfWeekISO(todayISO(), settings.week_start));
  const [form, setForm] = useState<EventForm | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    setWeekStart((current) => startOfWeekISO(current, settings.week_start));
  }, [settings.week_start]);

  const rangeEnd = addDaysISO(weekStart, 7);
  const eventsApi = useApi(() => api.events(weekStart, rangeEnd), [weekStart]);
  const events = eventsApi.data?.events ?? [];
  const format = settings.time_format;
  const days = useMemo(() => weekDates(weekStart), [weekStart]);
  const today = todayISO();

  const byDay = useMemo(() => {
    const map = new Map<string, EventItem[]>();
    days.forEach((day) => map.set(day, []));
    for (const event of events) {
      const bucket = map.get(dateInputValue(event.start_at));
      if (bucket) bucket.push(event);
    }
    for (const bucket of map.values()) {
      bucket.sort((a, b) => a.start_at.localeCompare(b.start_at));
    }
    return map;
  }, [events, days]);

  const openCreate = (date = today) => {
    setForm(blankForm(date));
    setFormError(null);
    setArmed(false);
  };

  const openEdit = (event: EventItem) => {
    setForm({
      id: event.id,
      title: event.title,
      date: dateInputValue(event.start_at),
      start: timeInputValue(event.start_at),
      end: timeInputValue(event.end_at),
      location: event.location,
      kind: (KIND_OPTIONS.includes(event.kind as EventKind) ? event.kind : "meeting") as EventKind,
      description: event.description,
    });
    setFormError(null);
    setArmed(false);
  };

  const save = async () => {
    if (!form) return;
    if (!form.title.trim()) {
      setFormError("Give the event a title.");
      return;
    }
    if (!form.date) {
      setFormError("Choose a date for the event.");
      return;
    }
    if (form.end <= form.start) {
      setFormError("End time must be after the start time.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const payload = {
      title: form.title.trim(),
      description: form.description,
      location: form.location.trim(),
      kind: form.kind,
      start_at: `${form.date}T${form.start}:00`,
      end_at: `${form.date}T${form.end}:00`,
    };
    try {
      if (form.id) {
        await api.updateEvent(form.id, payload);
        toast("Event updated.");
      } else {
        await api.createEvent(payload);
        toast("Event created.");
      }
      setForm(null);
      eventsApi.reload();
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : "The event could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!form?.id) return;
    setSaving(true);
    try {
      await api.deleteEvent(form.id);
      toast("Event deleted.");
      setForm(null);
      eventsApi.reload();
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : "The event could not be deleted.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Calendar"
        title="The week, in one frame."
        description="Create, edit and delete events. Everything is written to the local SQLite calendar provider and survives a backend restart."
        actions={
          <>
            <Button
              size="sm"
              variant="secondary"
              aria-label="Previous week"
              icon={<ChevronLeft className="size-3.5" />}
              onClick={() => setWeekStart((current) => addDaysISO(current, -7))}
            />
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setWeekStart(startOfWeekISO(todayISO(), settings.week_start))}
            >
              Today
            </Button>
            <Button
              size="sm"
              variant="secondary"
              aria-label="Next week"
              icon={<ChevronRight className="size-3.5" />}
              onClick={() => setWeekStart((current) => addDaysISO(current, 7))}
            />
            <Button size="sm" variant="primary" icon={<Plus className="size-3.5" />} onClick={() => openCreate()}>
              New event
            </Button>
          </>
        }
      />

      {eventsApi.error && (
        <div className="mb-4">
          <ErrorPanel message={eventsApi.error} onRetry={eventsApi.reload} />
        </div>
      )}

      <Card className="animate-enter overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-4 py-3">
          <div className="flex items-center gap-2">
            <CalendarDays className="size-4 text-brass" />
            <span className="serif text-[16px] text-bone">{fmtWeekRange(weekStart)}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[10.5px] text-muted">
            {["meeting", "focus", "personal"].map((kind) => (
              <span key={kind} className="inline-flex items-center gap-1.5 capitalize">
                <span className={cn("size-1.5 rounded-full", KIND_DOT[kind])} />
                {kind}
              </span>
            ))}
          </div>
        </div>

        {eventsApi.loading && !eventsApi.data ? (
          <LoadingBlock rows={6} label="Loading calendar" />
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[920px]">
              <div className="grid grid-cols-[52px_repeat(7,minmax(0,1fr))] border-b border-line-soft">
                <div />
                {days.map((day) => {
                  const date = new Date(`${day}T00:00:00`);
                  const isToday = day === today;
                  return (
                    <div key={day} className="border-l border-line-soft px-2 py-2 text-center">
                      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">
                        {new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(date)}
                      </div>
                      <div
                        className={cn(
                          "num mx-auto mt-1 flex size-6 items-center justify-center rounded-full text-[12px]",
                          isToday ? "bg-brass font-semibold text-ink-950" : "text-bone-dim",
                        )}
                      >
                        {date.getDate()}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="grid grid-cols-[52px_repeat(7,minmax(0,1fr))]">
                <div className="relative border-r border-line-soft" style={{ height: GRID_HEIGHT }}>
                  {HOURS.map((hour) => (
                    <div
                      key={hour}
                      className="absolute right-2 -translate-y-1/2 font-mono text-[10px] text-muted/70"
                      style={{ top: (hour - GRID_START) * 60 * PX_PER_MIN }}
                    >
                      {pad(hour)}:00
                    </div>
                  ))}
                </div>

                {days.map((day) => (
                  <div
                    key={day}
                    className={cn("relative border-l border-line-soft", day === today && "bg-brass/[0.015]")}
                    style={{ height: GRID_HEIGHT }}
                  >
                    {HOURS.map((hour) => (
                      <div
                        key={hour}
                        className="pointer-events-none absolute inset-x-0 border-t border-line-soft/70"
                        style={{ top: (hour - GRID_START) * 60 * PX_PER_MIN }}
                      />
                    ))}

                    {(byDay.get(day) ?? []).map((event) => {
                      const start = new Date(event.start_at);
                      const end = new Date(event.end_at);
                      const minutesFromStart = start.getHours() * 60 + start.getMinutes() - GRID_START * 60;
                      const top = Math.max(0, minutesFromStart * PX_PER_MIN);
                      const duration = Math.max(20, (end.getTime() - start.getTime()) / 60000);
                      const height = Math.max(24, duration * PX_PER_MIN);
                      return (
                        <button
                          key={event.id}
                          type="button"
                          onClick={() => openEdit(event)}
                          title={`${event.title} · ${fmtTime(event.start_at, format)}–${fmtTime(event.end_at, format)}`}
                          className={cn(
                            "absolute inset-x-1 overflow-hidden rounded-[4px] border-l-2 px-1.5 py-1 text-left transition-colors",
                            KIND_STYLES[event.kind] ?? KIND_STYLES.meeting,
                          )}
                          style={{ top, height }}
                        >
                          <p className="truncate text-[10.5px] font-medium leading-tight text-bone">
                            {event.title}
                          </p>
                          {height > 38 && (
                            <p className="num mt-0.5 truncate font-mono text-[9.5px] text-bone-dim/80">
                              {fmtTime(event.start_at, format)}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Card>

      <p className="mt-3 text-[11px] text-muted">
        Week starts {settings.week_start}. Click any event to edit or delete it.
      </p>

      <Modal
        open={form !== null}
        title={form?.id ? "Edit event" : "New event"}
        description="Stored in the local calendar provider (SQLite)."
        onClose={() => setForm(null)}
        footer={
          form ? (
            <>
              {form.id && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => (armed ? void remove() : setArmed(true))}
                  loading={saving && armed}
                  className="mr-auto"
                >
                  {armed ? "Confirm delete" : "Delete event"}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => setForm(null)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" loading={saving && !armed} onClick={save}>
                {form.id ? "Save changes" : "Create event"}
              </Button>
            </>
          ) : null
        }
      >
        {form && (
          <div className="space-y-4">
            <Field label="Title" htmlFor="event-title">
              <TextInput
                id="event-title"
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="Design review"
                autoFocus
              />
            </Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Date" htmlFor="event-date">
                <TextInput
                  id="event-date"
                  type="date"
                  value={form.date}
                  onChange={(event) => setForm({ ...form, date: event.target.value })}
                />
              </Field>
              <Field label="Start" htmlFor="event-start">
                <TextInput
                  id="event-start"
                  type="time"
                  value={form.start}
                  onChange={(event) => setForm({ ...form, start: event.target.value })}
                />
              </Field>
              <Field label="End" htmlFor="event-end">
                <TextInput
                  id="event-end"
                  type="time"
                  value={form.end}
                  onChange={(event) => setForm({ ...form, end: event.target.value })}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type" htmlFor="event-kind">
                <Select
                  id="event-kind"
                  value={form.kind}
                  onChange={(event) => setForm({ ...form, kind: event.target.value as EventKind })}
                >
                  {KIND_OPTIONS.map((kind) => (
                    <option key={kind} value={kind}>
                      {kind[0].toUpperCase() + kind.slice(1)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Location" htmlFor="event-location">
                <TextInput
                  id="event-location"
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                  placeholder="Room 2B / Meet"
                />
              </Field>
            </div>
            <Field label="Notes" htmlFor="event-notes" hint="Optional.">
              <TextArea
                id="event-notes"
                rows={3}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </Field>
            {formError && (
              <p className="rounded border border-clay/30 bg-clay/[0.06] px-3 py-2 text-[12px] text-clay">
                {formError}
              </p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
