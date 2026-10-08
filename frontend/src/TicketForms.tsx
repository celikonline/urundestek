import { useEffect, useRef, useState } from "react";
import { BellPlus, BookOpen, ChevronDown } from "lucide-react";
import { api, post } from "./api";
import { Field, Modal } from "./components";
import { CATEGORIES, PRIORITIES } from "./types";
import { MessageComposer, readDraft, writeDraft } from "./MessageEditor";
import type { HelpArticle, Ticket } from "./types";

const DRAFT_KEY = "taslak:yeni-talep";

function HelpSuggestions({ query }: { query: string }) {
  const [items, setItems] = useState<HelpArticle[]>([]),
    [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    if (query.trim().length < 3) {
      setItems([]);
      return;
    }
    let alive = true;
    const timer = setTimeout(() => {
      api<{ items: HelpArticle[] }>(`/help?q=${encodeURIComponent(query)}`)
        .then((r) => {
          if (alive) setItems(r.items);
        })
        .catch(() => {
          if (alive) setItems([]);
        });
    }, 300);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [query]);
  if (!items.length) return null;
  return (
    <div className="help-suggestions" aria-label="Yardımcı olabilecek bilgiler">
      <span className="help-title">
        <BookOpen size={14} />
        Talep açmadan önce bunlar yardımcı olabilir
      </span>
      {items.map((item) => (
        <details
          key={item.title}
          open={open === item.title}
          onToggle={(e) =>
            setOpen(
              (e.currentTarget as HTMLDetailsElement).open ? item.title : null,
            )
          }
        >
          <summary>
            {item.title}
            <ChevronDown size={14} />
          </summary>
          <ul>
            {item.lines.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}

export function NewTicket({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (t: Ticket) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const saved = useRef(readDraft(DRAFT_KEY));
  const draft = (() => {
    try {
      return JSON.parse(saved.current || "{}") as Record<string, string>;
    } catch {
      return {} as Record<string, string>;
    }
  })();
  const [subject, setSubject] = useState(draft.subject || "");
  const key = useRef(crypto.randomUUID());
  const remember = (form: HTMLFormElement | null) => {
    if (!form) return;
    const data = Object.fromEntries(new FormData(form)) as Record<
      string,
      string
    >;
    writeDraft(
      DRAFT_KEY,
      JSON.stringify({
        subject: data.subject || "",
        category: data.category || "",
        priority: data.priority || "",
      }),
    );
  };
  return (
    <Modal
      title="Yeni destek talebi"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="form-intro">
        Konuyu ve yaşadığınız durumu paylaşın. Birlikte çözelim.
      </p>
      <MessageComposer
        internal={false}
        busy={busy}
        editorLabel="Açıklama"
        submitLabel="Talebi oluştur"
        minimumTextLength={10}
        onCancel={onClose}
        storageKey={`${DRAFT_KEY}:aciklama`}
        beforeEditor={
          <div
            className="new-ticket-fields"
            onChange={(e) => remember(e.currentTarget.closest("form"))}
          >
            <Field label="Konu">
              <input
                name="subject"
                minLength={5}
                maxLength={160}
                required
                placeholder="Size hangi konuda yardımcı olabiliriz?"
                autoFocus
                disabled={busy}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </Field>
            <HelpSuggestions query={subject} />
            <div className="form-grid">
              <Field label="Kategori">
                <select
                  name="category"
                  disabled={busy}
                  defaultValue={draft.category || "general"}
                >
                  {Object.entries(CATEGORIES).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Öncelik">
                <select
                  name="priority"
                  disabled={busy}
                  defaultValue={draft.priority || "normal"}
                >
                  {Object.entries(PRIORITIES).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="field">
              <span>Açıklama</span>
            </div>
          </div>
        }
        onSend={async (payload) => {
          setBusy(true);
          setError("");
          try {
            const t = await api<Ticket>("/tickets/with-files", {
              method: "POST",
              headers: { "Idempotency-Key": key.current },
              body: payload,
            });
            writeDraft(DRAFT_KEY, "");
            writeDraft(`${DRAFT_KEY}:aciklama`, "");
            onCreated(t);
            return true;
          } catch (err) {
            setError((err as Error).message);
            return false;
          } finally {
            setBusy(false);
          }
        }}
      />
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
    </Modal>
  );
}

export function ReminderForm({
  ticket,
  onClose,
  onSaved,
}: {
  ticket: Ticket;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const local = new Date(Date.now() + 3600000);
  local.setMinutes(local.getMinutes() - local.getTimezoneOffset());
  return (
    <Modal title="Hatırlatma oluştur" onClose={onClose}>
      <p className="form-intro">
        #{ticket.number} · {ticket.subject}
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          const f = new FormData(e.currentTarget);
          try {
            await post(`/tickets/${ticket.id}/reminders`, {
              due_at: new Date(String(f.get("due_at"))).toISOString(),
              note: f.get("note"),
            });
            onSaved();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Tarih ve saat">
          <input
            type="datetime-local"
            name="due_at"
            defaultValue={local.toISOString().slice(0, 16)}
            required
          />
        </Field>
        <small className="hint">
          Saat seçimi cihazınızın saat dilimindedir. Portal tarihleri İstanbul
          saatini gösterir.
        </small>
        <Field label="Hatırlatma notu">
          <textarea
            name="note"
            required
            minLength={2}
            maxLength={500}
            rows={3}
            defaultValue="Talebin güncel durumunu kontrol et"
          />
        </Field>
        <p className="reminder-info">
          Zamanı geldiğinde portalda bildirim alacaksınız.
        </p>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Vazgeç
          </button>
          <button disabled={busy} className="button primary">
            <BellPlus size={16} />
            {busy ? "Kaydediliyor…" : "Hatırlatmayı kaydet"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
