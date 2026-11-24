import { useEffect, useState } from "react";
import { Check, ListChecks, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { useApi } from "../lib/useApi";
import { useSettings } from "../components/SettingsProvider";
import { useToast } from "../components/Toast";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorPanel,
  Field,
  LoadingBlock,
  Modal,
  PageHeader,
  PriorityBadge,
  Select,
  StatusBadge,
  TextArea,
  TextInput,
} from "../components/ui";
import { dateInputValue, fmtDateTime, timeInputValue, todayISO } from "../lib/format";
import type { Priority, Task, TaskStatus } from "../lib/types";

interface TaskForm {
  id: string | null;
  title: string;
  description: string;
  priority: Priority;
  status: TaskStatus;
  due_date: string;
  due_time: string;
  estimate_minutes: number;
  tags: string;
}

const blankForm = (): TaskForm => ({
  id: null,
  title: "",
  description: "",
  priority: "medium",
  status: "todo",
  due_date: "",
  due_time: "18:00",
  estimate_minutes: 60,
  tags: "",
});

export default function TasksPage() {
  const { settings } = useSettings();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("open");
  const [priority, setPriority] = useState("all");
  const [form, setForm] = useState<TaskForm | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [armed, setArmed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  const tasksApi = useApi(
    () =>
      api.tasks({
        status: status === "all" ? undefined : status,
        priority: priority === "all" ? undefined : priority,
        search: debounced || undefined,
      }),
    [status, priority, debounced],
  );

  const tasks = tasksApi.data?.tasks ?? [];
  const format = settings.time_format;
  const openCount = tasks.filter((task) => task.status !== "done").length;
  const overdue = tasks.filter(
    (task) => task.status !== "done" && task.due_at && new Date(task.due_at) < new Date(),
  ).length;

  const toggle = async (task: Task) => {
    setBusyId(task.id);
    try {
      await api.updateTask(task.id, { status: task.status === "done" ? "todo" : "done" });
      toast(task.status === "done" ? "Task reopened." : `Completed “${task.title}”.`);
      tasksApi.reload();
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : "Could not update the task.", "error");
    } finally {
      setBusyId(null);
    }
  };

  const openCreate = () => {
    setForm(blankForm());
    setFormError(null);
    setArmed(false);
  };

  const openEdit = (task: Task) => {
    setForm({
      id: task.id,
      title: task.title,
      description: task.description,
      priority: task.priority,
      status: task.status,
      due_date: task.due_at ? dateInputValue(task.due_at) : "",
      due_time: task.due_at ? timeInputValue(task.due_at) : "18:00",
      estimate_minutes: task.estimate_minutes,
      tags: task.tags.join(", "),
    });
    setFormError(null);
    setArmed(false);
  };

  const save = async () => {
    if (!form) return;
    if (!form.title.trim()) {
      setFormError("A task needs a title.");
      return;
    }
    const estimate = Number(form.estimate_minutes);
    if (!Number.isFinite(estimate) || estimate < 15 || estimate > 480) {
      setFormError("Estimate must be between 15 and 480 minutes.");
      return;
    }
    const payload = {
      title: form.title.trim(),
      description: form.description,
      priority: form.priority,
      status: form.status,
      estimate_minutes: estimate,
      due_at: form.due_date ? `${form.due_date}T${form.due_time || "18:00"}:00` : null,
      tags: form.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    };
    setSaving(true);
    setFormError(null);
    try {
      if (form.id) {
        await api.updateTask(form.id, payload);
        toast("Task updated.");
      } else {
        await api.createTask(payload);
        toast("Task created.");
      }
      setForm(null);
      tasksApi.reload();
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : "The task could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!form?.id) return;
    setSaving(true);
    try {
      await api.deleteTask(form.id);
      toast("Task deleted.");
      setForm(null);
      tasksApi.reload();
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : "The task could not be deleted.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="Task Manager"
        title="The work, made explicit."
        description="Priority, deadline, estimate and status — the exact inputs the planner uses. Searches and filters run against the local task provider."
        actions={
          <Button variant="primary" icon={<Plus className="size-4" />} onClick={openCreate}>
            New task
          </Button>
        }
      />

      <Card className="animate-enter mb-4 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
            <TextInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search tasks…"
              aria-label="Search tasks"
              className="pl-8"
            />
          </div>
          <Select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            aria-label="Filter by status"
            className="w-auto min-w-[130px]"
          >
            <option value="open">Open tasks</option>
            <option value="all">All statuses</option>
            <option value="todo">To do</option>
            <option value="in_progress">In progress</option>
            <option value="done">Done</option>
          </Select>
          <Select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            aria-label="Filter by priority"
            className="w-auto min-w-[130px]"
          >
            <option value="all">All priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </Select>
          {(search || status !== "open" || priority !== "all") && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSearch("");
                setStatus("open");
                setPriority("all");
              }}
            >
              Clear filters
            </Button>
          )}
          <span className="ml-auto text-[11px] text-muted">
            {openCount} open · {overdue > 0 ? `${overdue} overdue` : "none overdue"}
          </span>
        </div>
      </Card>

      {tasksApi.error && <div className="mb-4"><ErrorPanel message={tasksApi.error} onRetry={tasksApi.reload} /></div>}

      <Card className="animate-enter overflow-hidden">
        {tasksApi.loading && !tasksApi.data ? (
          <LoadingBlock rows={6} label="Loading tasks" />
        ) : tasks.length === 0 ? (
          <EmptyState
            icon={<ListChecks className="size-4" />}
            title={debounced || status !== "open" || priority !== "all" ? "No tasks match" : "No tasks yet"}
            description={
              debounced || status !== "open" || priority !== "all"
                ? "Adjust the filters or search for something else."
                : "Add your first task to give the planner something to schedule."
            }
            action={
              <Button size="sm" variant="secondary" icon={<Plus className="size-3.5" />} onClick={openCreate}>
                New task
              </Button>
            }
          />
        ) : (
          <div className="divide-y divide-line-soft">
            {tasks.map((task) => {
              const isOverdue =
                task.status !== "done" && task.due_at && new Date(task.due_at) < new Date();
              return (
                <div key={task.id} className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-ink-850/40 sm:px-5">
                  <button
                    type="button"
                    aria-label={task.status === "done" ? "Reopen task" : "Complete task"}
                    disabled={busyId === task.id}
                    onClick={() => toggle(task)}
                    className={cn(
                      "mt-0.5 flex size-[18px] shrink-0 items-center justify-center rounded-[4px] border transition-colors",
                      task.status === "done"
                        ? "border-sage/60 bg-sage/20 text-sage"
                        : "border-line text-transparent hover:border-sage/60 hover:text-sage",
                      busyId === task.id && "opacity-40",
                    )}
                  >
                    <Check className="size-3" />
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p
                        className={cn(
                          "text-[13px] font-medium",
                          task.status === "done" ? "text-muted line-through" : "text-bone",
                        )}
                      >
                        {task.title}
                      </p>
                      {task.status === "in_progress" && <StatusBadge status="in_progress" />}
                    </div>
                    {task.description && (
                      <p className="mt-0.5 line-clamp-1 text-[11.5px] text-muted">{task.description}</p>
                    )}
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-muted">
                      <PriorityBadge priority={task.priority} />
                      {task.due_at ? (
                        <span className={isOverdue ? "text-clay" : undefined}>
                          {isOverdue ? "Overdue · " : "Due "}
                          {fmtDateTime(task.due_at, format)}
                        </span>
                      ) : (
                        <span>No deadline</span>
                      )}
                      <span>{task.estimate_minutes} min estimate</span>
                      {task.tags.map((tag) => (
                        <span key={tag} className="rounded border border-line px-1.5 py-px text-[9.5px]">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Edit ${task.title}`}
                      onClick={() => openEdit(task)}
                      className="px-2"
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Modal
        open={form !== null}
        title={form?.id ? "Edit task" : "New task"}
        description="Stored in the local task provider (SQLite)."
        onClose={() => setForm(null)}
        footer={
          form ? (
            <>
              {form.id && (
                <Button
                  variant="danger"
                  size="sm"
                  icon={<Trash2 className="size-3.5" />}
                  loading={saving && armed}
                  onClick={() => (armed ? void remove() : setArmed(true))}
                  className="mr-auto"
                >
                  {armed ? "Confirm delete" : "Delete"}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => setForm(null)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" loading={saving && !armed} onClick={save}>
                {form.id ? "Save changes" : "Create task"}
              </Button>
            </>
          ) : null
        }
      >
        {form && (
          <div className="space-y-4">
            <Field label="Title" htmlFor="task-title">
              <TextInput
                id="task-title"
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
                placeholder="Finish the literature review"
                autoFocus
              />
            </Field>
            <Field label="Description" htmlFor="task-description">
              <TextArea
                id="task-description"
                rows={2}
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="Optional context for future you"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Priority" htmlFor="task-priority">
                <Select
                  id="task-priority"
                  value={form.priority}
                  onChange={(event) => setForm({ ...form, priority: event.target.value as Priority })}
                >
                  <option value="urgent">Urgent</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </Select>
              </Field>
              <Field label="Status" htmlFor="task-status">
                <Select
                  id="task-status"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value as TaskStatus })}
                >
                  <option value="todo">To do</option>
                  <option value="in_progress">In progress</option>
                  <option value="done">Done</option>
                </Select>
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Due date" htmlFor="task-due-date" className="col-span-2">
                <TextInput
                  id="task-due-date"
                  type="date"
                  value={form.due_date}
                  min="2000-01-01"
                  onChange={(event) => setForm({ ...form, due_date: event.target.value })}
                />
              </Field>
              <Field label="Time" htmlFor="task-due-time">
                <TextInput
                  id="task-due-time"
                  type="time"
                  value={form.due_time}
                  disabled={!form.due_date}
                  onChange={(event) => setForm({ ...form, due_time: event.target.value })}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Estimate" htmlFor="task-estimate" hint="15–480 minutes">
                <TextInput
                  id="task-estimate"
                  type="number"
                  min={15}
                  max={480}
                  step={15}
                  value={form.estimate_minutes}
                  onChange={(event) =>
                    setForm({ ...form, estimate_minutes: Number(event.target.value) || 0 })
                  }
                />
              </Field>
              <Field label="Tags" htmlFor="task-tags" hint="Comma separated">
                <TextInput
                  id="task-tags"
                  value={form.tags}
                  onChange={(event) => setForm({ ...form, tags: event.target.value })}
                  placeholder="Coursework, Writing"
                />
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <span className="label-micro">Preview</span>
              <Badge tone="outline">{form.priority}</Badge>
              <span>{form.due_date ? `Due ${form.due_date}` : "No deadline"}</span>
              <span>· {form.estimate_minutes || 0} min</span>
            </div>
            {formError && (
              <p className="rounded border border-clay/30 bg-clay/[0.06] px-3 py-2 text-[12px] text-clay">
                {formError}
              </p>
            )}
          </div>
        )}
      </Modal>

      <p className="mt-3 text-[11px] text-muted">
        Tip: the demo command “Plan my day” schedules the highest-priority open tasks first. Due date
        defaults to {todayISO()}.
      </p>
    </div>
  );
}
