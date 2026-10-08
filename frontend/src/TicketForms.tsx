import { useRef, useState } from "react";
import { Send, BellPlus } from "lucide-react";
import { api, post } from "./api";
import { Field, Modal } from "./components";
import { CATEGORIES, PRIORITIES } from "./types";
import type { Ticket } from "./types";

export function NewTicket({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (t: Ticket) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const key = useRef(crypto.randomUUID());
  return (
    <Modal title="Yeni destek talebi" onClose={onClose}>
      <p className="form-intro">
        Konuyu ve yaşadığınız durumu paylaşın. Birlikte çözelim.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const f = new FormData(e.currentTarget);
          try {
            const t = await api<Ticket>("/tickets", {
              method: "POST",
              headers: { "Idempotency-Key": key.current },
              body: JSON.stringify(Object.fromEntries(f)),
            });
            onCreated(t);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Konu">
          <input
            name="subject"
            minLength={5}
            maxLength={160}
            required
            placeholder="Size hangi konuda yardımcı olabiliriz?"
            autoFocus
          />
        </Field>
        <div className="form-grid">
          <Field label="Kategori">
            <select name="category">
              {Object.entries(CATEGORIES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Öncelik">
            <select name="priority">
              {Object.entries(PRIORITIES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Açıklama">
          <textarea
            name="body"
            minLength={10}
            maxLength={10000}
            required
            rows={6}
            placeholder="Ne yapmak istediniz, ne oldu? Adımları ve varsa hata mesajını yazabilirsiniz."
          />
        </Field>
        <small className="hint">
          Parola veya kişisel çalışan verisi paylaşmayın.
        </small>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Vazgeç
          </button>
          <button className="button primary" disabled={busy}>
            <Send size={16} />
            {busy ? "Oluşturuluyor…" : "Talebi oluştur"}
          </button>
        </div>
      </form>
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
