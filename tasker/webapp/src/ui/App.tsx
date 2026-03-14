import React, { useEffect, useMemo, useState } from "react";
import "./App.css";

type Task = {
  task_id: number;
  title: string;
  due_at: string | null;
  status: string;
  source?: string;
  created_at?: string;
};

// Используем относительные пути - Vite прокси перенаправит на backend
const API_BASE = "";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = d.getTime() - now.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return `сегодня в ${d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
    if (diffDays === 1) return `завтра в ${d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
    if (diffDays === -1) return `вчера в ${d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
    if (diffDays > 1 && diffDays < 7) {
      return d.toLocaleDateString("ru-RU", { weekday: "long", hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  } catch {
    return dateStr;
  }
}

function TaskCard({
  task,
  onRefresh,
  onEdit,
  onDelete,
  editingTaskId,
  editTitle,
  editDueAt,
  setEditTitle,
  setEditDueAt,
  onSaveEdit,
  onCancelEdit,
  apiBase,
  userId,
}: {
  task: Task;
  onRefresh: () => void;
  onEdit: (task: Task) => void;
  onDelete: (taskId: number) => void;
  editingTaskId: number | null;
  editTitle: string;
  editDueAt: string;
  setEditTitle: (s: string) => void;
  setEditDueAt: (s: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  apiBase: string;
  userId: number;
}) {
  const statusEmoji = task.status === "todo" ? "📋" : task.status === "done" ? "✅" : "⏸️";
  const isOverdue = task.due_at && new Date(task.due_at) < new Date() && task.status === "todo";
  const isEditing = editingTaskId === task.task_id;

  if (isEditing) {
    return (
      <div className="task-card task-card--editing">
        <div className="task-card__edit-form">
          <input
            className="task-card__edit-input"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            placeholder="Название задачи"
          />
          <input
            type="datetime-local"
            className="task-card__edit-input"
            value={editDueAt}
            onChange={(e) => setEditDueAt(e.target.value)}
          />
          <div className="task-card__edit-actions">
            <button className="task-card__edit-button task-card__edit-button--save" onClick={onSaveEdit}>
              💾 Сохранить
            </button>
            <button className="task-card__edit-button task-card__edit-button--cancel" onClick={onCancelEdit}>
              ❌ Отмена
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`task-card ${isOverdue ? "task-card--overdue" : ""}`}>
      <div className="task-card__header">
        <span className="task-card__status">{statusEmoji}</span>
        <span className="task-card__title">{task.title}</span>
        <div className="task-card__actions">
          <button className="task-card__action-button" onClick={() => onEdit(task)} title="Редактировать">
            ✏️
          </button>
          <button className="task-card__action-button task-card__action-button--delete" onClick={() => onDelete(task.task_id)} title="Удалить">
            🗑️
          </button>
        </div>
      </div>
      {task.due_at && (
        <div className={`task-card__due ${isOverdue ? "task-card__due--overdue" : ""}`}>
          ⏰ {formatDate(task.due_at)}
        </div>
      )}
      <div className="task-card__meta">
        <span className="task-card__id">#{task.task_id}</span>
        {task.source && <span className="task-card__source">via {task.source}</span>}
        <button
          className="task-card__status-button"
          onClick={async () => {
            const newStatus = task.status === "todo" ? "done" : "todo";
            const r = await fetch(`${apiBase}/api/tasks/${task.task_id}?user_id=${userId}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: newStatus }),
            });
            if (r.ok) onRefresh();
          }}
        >
          {task.status === "todo" ? "✅ Выполнить" : "↩️ Вернуть"}
        </button>
      </div>
    </div>
  );
}

export function App() {
  const [userId, setUserId] = useState<number>(1);
  const [timezone, setTimezone] = useState<string>("Europe/Moscow"); // По умолчанию Москва (UTC+3)
  const [text, setText] = useState<string>("");
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState<string>("");
  const [editDueAt, setEditDueAt] = useState<string>("");

  const apiBase = useMemo(() => String(API_BASE).replace(/\/$/, ""), []);

  useEffect(() => {
    refresh();
  }, [userId]);

  async function refresh() {
    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/api/tasks?user_id=${userId}`);
      if (!r.ok) {
        const errorData = await r.json().catch(() => ({ detail: "Ошибка загрузки" }));
        throw new Error(errorData.detail || "Ошибка загрузки");
      }
      const data = await r.json();
      setTasks(data);
    } catch (err) {
      console.error("Ошибка загрузки задач:", err);
      setStatus({ type: "error", message: "Не удалось загрузить задачи. Проверьте, что backend запущен." });
    } finally {
      setLoading(false);
    }
  }

  async function createTask() {
    if (!text.trim()) {
      setStatus({ type: "error", message: "Введите описание задачи" });
      return;
    }

    setStatus(null);
    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/api/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, text, timezone, source: "webapp" }),
      });
      
      if (!r.ok) {
        let errorMessage = "Ошибка создания задачи";
        try {
          const errorData = await r.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
          console.error("Backend error:", errorData);
        } catch (e) {
          console.error("Failed to parse error response:", e);
          errorMessage = `HTTP ${r.status}: ${r.statusText}`;
        }
        setStatus({ type: "error", message: errorMessage });
        return;
      }
      
      const data = await r.json();
      setText("");
      setStatus({ type: "success", message: `Задача создана: «${data.title}»` });
      await refresh();
    } catch (err) {
      console.error("Ошибка запроса:", err);
      setStatus({ type: "error", message: "Ошибка соединения с сервером. Проверьте, что backend запущен." });
    } finally {
      setLoading(false);
    }
  }

  async function updateTask(taskId: number) {
    if (!editTitle.trim()) {
      setStatus({ type: "error", message: "Введите название задачи" });
      return;
    }

    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/api/tasks/${taskId}?user_id=${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editTitle,
          due_at: editDueAt || null,
        }),
      });

      if (!r.ok) {
        const errorData = await r.json().catch(() => ({ detail: "Ошибка обновления" }));
        setStatus({ type: "error", message: errorData.detail || "Ошибка обновления задачи" });
        return;
      }

      setEditingTaskId(null);
      setEditTitle("");
      setEditDueAt("");
      setStatus({ type: "success", message: "Задача обновлена" });
      await refresh();
    } catch (err) {
      console.error("Ошибка обновления:", err);
      setStatus({ type: "error", message: "Ошибка соединения с сервером" });
    } finally {
      setLoading(false);
    }
  }

  async function deleteTask(taskId: number) {
    if (!confirm("Вы уверены, что хотите удалить эту задачу?")) {
      return;
    }

    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/api/tasks/${taskId}?user_id=${userId}`, {
        method: "DELETE",
      });

      if (!r.ok) {
        const errorData = await r.json().catch(() => ({ detail: "Ошибка удаления" }));
        setStatus({ type: "error", message: errorData.detail || "Ошибка удаления задачи" });
        return;
      }

      setStatus({ type: "success", message: "Задача удалена" });
      await refresh();
    } catch (err) {
      console.error("Ошибка удаления:", err);
      setStatus({ type: "error", message: "Ошибка соединения с сервером" });
    } finally {
      setLoading(false);
    }
  }

  function startEdit(task: Task) {
    setEditingTaskId(task.task_id);
    setEditTitle(task.title);
    if (task.due_at) {
      const d = new Date(task.due_at);
      const localDateTime = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      setEditDueAt(localDateTime);
    } else {
      setEditDueAt("");
    }
  }

  function cancelEdit() {
    setEditingTaskId(null);
    setEditTitle("");
    setEditDueAt("");
  }

  const filteredTasks = useMemo(() => {
    if (filterStatus === "all") return tasks;
    return tasks.filter((t) => t.status === filterStatus);
  }, [tasks, filterStatus]);

  const stats = useMemo(() => {
    const todo = tasks.filter((t) => t.status === "todo").length;
    const done = tasks.filter((t) => t.status === "done").length;
    return { total: tasks.length, todo, done };
  }, [tasks]);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">📝 Tasker</h1>
        <p className="app-subtitle">Управление задачами с умным парсингом дат</p>
      </header>

      <div className="app-content">
        <section className="section">
          <h2 className="section-title">Создать задачу</h2>
          <div className="task-form">
            <div className="task-form__row">
              <input
                className="task-form__input"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !loading && createTask()}
                placeholder="Например: Купить билеты завтра 18:00"
                disabled={loading}
              />
              <button className="task-form__button" onClick={createTask} disabled={loading || !text.trim()}>
                {loading ? "⏳" : "➕ Создать"}
              </button>
            </div>
            <div className="task-form__hint">
              💡 Попробуйте: "Позвонить маме", "Отправить отчёт в пятницу", "Купить билеты завтра 18:00"
            </div>
          </div>

          {status && (
            <div className={`status-message status-message--${status.type}`}>
              {status.type === "success" ? "✅" : "❌"} {status.message}
            </div>
          )}

          <div className="settings">
            <label className="settings__label">
              <span>User ID:</span>
              <input
                type="number"
                value={userId}
                onChange={(e) => setUserId(Number(e.target.value))}
                className="settings__input"
              />
            </label>
            <label className="settings__label">
              <span>Часовой пояс:</span>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="settings__input"
              >
                <option value="Europe/Moscow">Москва (UTC+3)</option>
                <option value="UTC">UTC</option>
                <option value="Europe/Kiev">Киев (UTC+2)</option>
                <option value="Europe/Minsk">Минск (UTC+3)</option>
                <option value="Asia/Yekaterinburg">Екатеринбург (UTC+5)</option>
                <option value="Asia/Novosibirsk">Новосибирск (UTC+7)</option>
                <option value="Europe/London">Лондон (UTC+0)</option>
                <option value="America/New_York">Нью-Йорк (UTC-5)</option>
              </select>
            </label>
            <button className="settings__button" onClick={refresh} disabled={loading}>
              🔄 Обновить
            </button>
          </div>
        </section>

        <section className="section">
          <div className="section-header">
            <h2 className="section-title">Задачи</h2>
            <div className="stats">
              <span className="stat">Всего: {stats.total}</span>
              <span className="stat stat--todo">📋 {stats.todo}</span>
              <span className="stat stat--done">✅ {stats.done}</span>
            </div>
          </div>

          <div className="filters">
            <button
              className={`filter-button ${filterStatus === "all" ? "filter-button--active" : ""}`}
              onClick={() => setFilterStatus("all")}
            >
              Все
            </button>
            <button
              className={`filter-button ${filterStatus === "todo" ? "filter-button--active" : ""}`}
              onClick={() => setFilterStatus("todo")}
            >
              📋 К выполнению
            </button>
            <button
              className={`filter-button ${filterStatus === "done" ? "filter-button--active" : ""}`}
              onClick={() => setFilterStatus("done")}
            >
              ✅ Выполнено
            </button>
          </div>

          {loading && tasks.length === 0 ? (
            <div className="loading">Загрузка...</div>
          ) : filteredTasks.length === 0 ? (
            <div className="empty-state">
              {tasks.length === 0 ? "📭 Нет задач. Создайте первую!" : "🔍 Нет задач с выбранным фильтром"}
            </div>
          ) : (
            <div className="task-list">
              {filteredTasks.map((task) => (
                <TaskCard
                  key={task.task_id}
                  task={task}
                  onRefresh={refresh}
                  onEdit={startEdit}
                  onDelete={deleteTask}
                  editingTaskId={editingTaskId}
                  editTitle={editTitle}
                  editDueAt={editDueAt}
                  setEditTitle={setEditTitle}
                  setEditDueAt={setEditDueAt}
                  onSaveEdit={() => updateTask(editingTaskId!)}
                  onCancelEdit={cancelEdit}
                  apiBase={apiBase}
                  userId={userId}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
