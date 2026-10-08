import { useEffect, useState } from "react";
import {
  Bell,
  Check,
  Plus,
  Building2,
  Users,
  ArrowUpRight,
  X,
  Mail,
  Bot,
  LockKeyhole,
} from "lucide-react";
import { api, post } from "./api";
import { Empty, Field, Loading, Modal } from "./components";
import { AI_MODES, date, initials } from "./types";
import type { Notice, Reminder, Staff, Tenant, User } from "./types";

type Props = {
  revision: number;
  refresh: () => void;
  notify: (text: string) => void;
  openTicket: (id: string) => void;
};
export function Reminders({ revision, refresh, notify, openTicket }: Props) {
  const [rows, setRows] = useState<Reminder[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [history, setHistory] = useState(false),
    [busy, setBusy] = useState("");
  useEffect(() => {
    let alive = true;
    api<Reminder[]>("/reminders")
      .then((r) => {
        if (alive) {
          setRows(r);
          setError("");
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [revision]);
  const update = async (id: string, complete: boolean) => {
    setBusy(id);
    try {
      await api(`/reminders/${id}${complete ? "/complete" : ""}`, {
        method: complete ? "POST" : "DELETE",
      });
      refresh();
      notify(complete ? "Hatırlatma tamamlandı." : "Hatırlatma iptal edildi.");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  const filtered = rows.filter((r) =>
    history ? r.status !== "pending" : r.status === "pending",
  );
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">TAKİP SİZDE</span>
          <h1>Hatırlatmalarım</h1>
          <p>Talebinize tekrar dönmek istediğiniz zamanı planlayın.</p>
        </div>
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>
            <Bell size={20} />
            Kişisel hatırlatmalar
          </h2>
          <div className="segment">
            <button
              className={!history ? "selected" : ""}
              onClick={() => setHistory(false)}
            >
              Planlanan
            </button>
            <button
              className={history ? "selected" : ""}
              onClick={() => setHistory(true)}
            >
              Geçmiş
            </button>
          </div>
        </div>
        {loading ? (
          <Loading />
        ) : error ? (
          <Empty
            title="Hatırlatmalar yüklenemedi"
            description={error}
            action={
              <button className="button secondary" onClick={refresh}>
                Tekrar dene
              </button>
            }
          />
        ) : !filtered.length ? (
          <Empty
            title={history ? "Henüz geçmiş hatırlatma yok" : "Takviminiz açık"}
            description="Bir talebi açıp “Hatırlatma oluştur” düğmesinden size uygun zamanı seçebilirsiniz."
          />
        ) : (
          <div className="reminder-list">
            {filtered.map((r) => (
              <article className="reminder-card" key={r.id}>
                <span
                  className={`reminder-bell ${new Date(r.due_at) < new Date() ? "due" : ""}`}
                >
                  <Bell size={21} />
                </span>
                <div>
                  <div className="reminder-date">
                    {date(r.due_at)}
                    {r.status === "pending" &&
                      new Date(r.due_at) < new Date() && (
                        <span className="priority high">Zamanı geldi</span>
                      )}
                    {r.status !== "pending" && (
                      <span className="status closed">
                        {r.status === "completed"
                          ? "Tamamlandı"
                          : "İptal edildi"}
                      </span>
                    )}
                  </div>
                  <h3>{r.note}</h3>
                  <button
                    className="text-button"
                    onClick={() => openTicket(r.ticket_id)}
                  >
                    #{r.ticket_number} · {r.subject}
                    <ArrowUpRight size={14} />
                  </button>
                </div>
                {r.status === "pending" && (
                  <div className="reminder-buttons">
                    <button
                      className="button secondary"
                      disabled={busy === r.id}
                      onClick={() => void update(r.id, true)}
                    >
                      <Check size={15} />
                      Tamamla
                    </button>
                    <button
                      className="icon-btn"
                      disabled={busy === r.id}
                      onClick={() => void update(r.id, false)}
                      aria-label="Hatırlatmayı iptal et"
                    >
                      <X size={17} />
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

export function Notifications({
  notices,
  user,
  onUser,
  onClose,
  openTicket,
  refresh,
  notify,
}: {
  notices: Notice[];
  user: User;
  onUser: (u: User) => void;
  onClose: () => void;
  openTicket: (id: string) => void;
  refresh: () => void;
  notify: (text: string) => void;
}) {
  const [saving, setSaving] = useState(false);
  return (
    <Modal title="Bildirimler" onClose={onClose}>
      <label className="pref-toggle">
        <input
          type="checkbox"
          checked={user.email_notifications}
          disabled={saving || !user.mail_enabled}
          onChange={async (e) => {
            setSaving(true);
            try {
              const updated = await api<User>("/me/preferences", {
                method: "PATCH",
                body: JSON.stringify({ email_notifications: e.target.checked }),
              });
              onUser({
                ...user,
                email_notifications: updated.email_notifications,
              });
              notify(
                updated.email_notifications
                  ? "E-posta bildirimleri açıldı."
                  : "E-posta bildirimleri kapatıldı.",
              );
            } catch (err) {
              notify((err as Error).message);
            } finally {
              setSaving(false);
            }
          }}
        />
        <span>
          <Mail size={15} />
          <b>E-posta ile de bilgilendir</b>
          <small>
            {user.mail_enabled
              ? "Yanıt, durum değişikliği ve hatırlatmalar için kısa bir e-posta gelir; mesaj içeriği e-postada yer almaz."
              : "E-posta gönderimi bu kurulumda yapılandırılmamış."}
          </small>
        </span>
      </label>
      <div className="notifications">
        {!notices.length ? (
          <Empty
            title="Her şey güncel"
            description="Yeni yanıtlar ve hatırlatmalarınız burada görünecek."
          />
        ) : (
          notices.map((n) => (
            <button
              className={`notice ${n.read ? "" : "unread"}`}
              key={n.id}
              onClick={async () => {
                try {
                  await post(`/notifications/${n.id}/read`);
                  refresh();
                  openTicket(n.ticket_id);
                  onClose();
                } catch (e) {
                  notify((e as Error).message);
                }
              }}
            >
              <span className="notice-icon">
                {n.kind === "ai" ? <Bot size={16} /> : <Bell size={16} />}
              </span>
              <span>
                <b>{n.text}</b>
                <small>{date(n.created_at)}</small>
              </span>
              {!n.read && <i className="unread-dot" />}
            </button>
          ))
        )}
      </div>
    </Modal>
  );
}

export function Management({
  kind,
  user,
  revision,
  refresh,
  notify,
}: {
  kind: "tenants" | "staff";
  user: User;
  revision: number;
  refresh: () => void;
  notify: (text: string) => void;
}) {
  const [tenants, setTenants] = useState<Tenant[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [create, setCreate] = useState(false),
    [busy, setBusy] = useState("");
  useEffect(() => {
    let alive = true;
    setLoading(true);
    api<Tenant[] | Staff[]>(`/admin/${kind}`)
      .then((r) => {
        if (alive) {
          if (kind === "tenants") setTenants(r as Tenant[]);
          else setStaff(r as Staff[]);
          setError("");
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [kind, revision]);
  const edit = async (
    id: string,
    values: object,
    path = `/admin/${kind}/${id}`,
    method = "PATCH",
  ) => {
    setBusy(id);
    try {
      await api(path, { method, body: JSON.stringify(values) });
      refresh();
      notify("Değişiklik kaydedildi.");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy("");
    }
  };
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">DESTEK YÖNETİMİ</span>
          <h1>{kind === "tenants" ? "Firmalar" : "Destek ekibi"}</h1>
          <p>
            {kind === "tenants"
              ? "Firmaların destek erişimini, asistan modunu ve açık taleplerini görüntüleyin."
              : "Destek görevlilerini ve yönetim yetkilerini düzenleyin."}
          </p>
        </div>
        {kind === "staff" && user.role === "platform_admin" && (
          <button className="button primary" onClick={() => setCreate(true)}>
            <Plus size={17} />
            Görevli ekle
          </button>
        )}
      </div>
      <section className="panel">
        <div className="panel-head">
          <h2>
            {kind === "tenants" ? <Building2 size={20} /> : <Users size={20} />}
            {kind === "tenants" ? "Firma çalışma alanları" : "Ekip üyeleri"}
          </h2>
          <span className="muted">
            {kind === "tenants" ? tenants.length : staff.length} kayıt
          </span>
        </div>
        {loading ? (
          <Loading />
        ) : error ? (
          <Empty
            title="Bilgiler yüklenemedi"
            description={error}
            action={
              <button className="button secondary" onClick={refresh}>
                Tekrar dene
              </button>
            }
          />
        ) : (
          <div className="management-list">
            {kind === "tenants"
              ? tenants.map((t) => (
                  <article className="management-row" key={t.id}>
                    <span className="avatar">{initials(t.name)}</span>
                    <div className="management-name">
                      <h3>{t.name}</h3>
                      <p>
                        {t.slug} · {t.external_id}
                      </p>
                    </div>
                    <span className="open-count">
                      {t.open_count} açık talep
                    </span>
                    {user.role === "platform_admin" ? (
                      <label className="ai-mode">
                        <Bot size={14} />
                        <select
                          aria-label={`${t.name} asistan modu`}
                          value={t.ai_mode}
                          disabled={busy === t.id}
                          onChange={(e) =>
                            void edit(t.id, { ai_mode: e.target.value })
                          }
                        >
                          {Object.entries(AI_MODES).map(([v, l]) => (
                            <option key={v} value={v}>
                              {l}
                            </option>
                          ))}
                        </select>
                        <small>
                          {t.ai_effective === "off"
                            ? "Asistan kapalı"
                            : t.ai_effective === "auto"
                              ? "Otomatik yanıt veriyor"
                              : "Ekibe taslak hazırlıyor"}
                        </small>
                      </label>
                    ) : (
                      <span className="role-label">
                        <Bot size={13} />{" "}
                        {t.ai_effective === "off"
                          ? "Asistan kapalı"
                          : t.ai_effective === "auto"
                            ? "Otomatik yanıt"
                            : "Taslak modu"}
                      </span>
                    )}
                    <span
                      className={`status ${t.active ? "resolved" : "closed"}`}
                    >
                      <i />
                      {t.active ? "Erişim açık" : "Erişim kapalı"}
                    </span>
                    {user.role === "platform_admin" && (
                      <button
                        className="button secondary"
                        disabled={busy === t.id}
                        onClick={() => void edit(t.id, { active: !t.active })}
                      >
                        {t.active ? "Erişimi kapat" : "Erişimi aç"}
                      </button>
                    )}
                  </article>
                ))
              : staff.map((s) => (
                  <article className="management-row" key={s.id}>
                    <span className="avatar purple">{initials(s.name)}</span>
                    <div className="management-name">
                      <h3>
                        {s.name}
                        {s.id === user.id && <small> (siz)</small>}
                      </h3>
                      <p>{s.email}</p>
                    </div>
                    {user.role === "platform_admin" && s.id !== user.id ? (
                      <select
                        aria-label={`${s.name} rolü`}
                        value={s.role}
                        disabled={busy === s.id}
                        onChange={(e) =>
                          void edit(s.id, { role: e.target.value })
                        }
                      >
                        <option value="support_agent">Destek görevlisi</option>
                        <option value="platform_admin">
                          Platform yöneticisi
                        </option>
                      </select>
                    ) : (
                      <span className="role-label">
                        {s.role === "platform_admin"
                          ? "Platform yöneticisi"
                          : "Destek görevlisi"}
                      </span>
                    )}
                    <span
                      className={`status ${s.active ? "resolved" : "closed"}`}
                    >
                      <i />
                      {s.active ? "Aktif" : "Pasif"}
                    </span>
                    {s.locked && user.role === "platform_admin" && (
                      <button
                        className="button secondary"
                        disabled={busy === s.id}
                        onClick={() =>
                          void edit(
                            s.id,
                            {},
                            `/admin/staff/${s.id}/unlock`,
                            "POST",
                          )
                        }
                      >
                        <LockKeyhole size={14} />
                        Kilidi kaldır
                      </button>
                    )}
                    {user.role === "platform_admin" && s.id !== user.id && (
                      <button
                        className="button secondary"
                        disabled={busy === s.id}
                        onClick={() => void edit(s.id, { active: !s.active })}
                      >
                        {s.active ? "Erişimi kapat" : "Erişimi aç"}
                      </button>
                    )}
                  </article>
                ))}
          </div>
        )}
      </section>
      {create && (
        <StaffForm
          onClose={() => setCreate(false)}
          onSaved={() => {
            setCreate(false);
            refresh();
            notify("Destek görevlisi eklendi.");
          }}
        />
      )}
    </>
  );
}

function StaffForm({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Modal title="Destek görevlisi ekle" onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await post(
              "/admin/staff",
              Object.fromEntries(new FormData(e.currentTarget)),
            );
            onSaved();
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Ad soyad">
          <input name="name" required minLength={2} maxLength={200} />
        </Field>
        <Field label="E-posta">
          <input name="email" type="email" required maxLength={200} />
        </Field>
        <Field label="Başlangıç parolası">
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={200}
          />
        </Field>
        <small className="hint">
          En az 12 karakter; ad veya e-posta içermemeli. Parolayı görevliye
          güvenli bir kanaldan iletin; görevli ilk girişte Güvenlik sayfasından
          değiştirebilir.
        </small>
        <Field label="Rol">
          <select name="role">
            <option value="support_agent">Destek görevlisi</option>
            <option value="platform_admin">Platform yöneticisi</option>
          </select>
        </Field>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Vazgeç
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "Ekleniyor…" : "Görevliyi ekle"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
