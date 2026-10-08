import { useEffect, useState } from "react";
import {
  ShieldCheck,
  KeyRound,
  ScrollText,
  Mail,
  Download,
  RotateCcw,
  Bot,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import { api, post } from "./api";
import { Empty, Field, Loading } from "./components";
import { date } from "./types";
import type { AdminSettings, AuditList, MailQueue, User } from "./types";

type Props = {
  user: User;
  revision: number;
  refresh: () => void;
  notify: (text: string) => void;
  openTicket: (id: string) => void;
};

export function Security({
  user,
  revision,
  refresh,
  notify,
  openTicket,
}: Props) {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  useEffect(() => {
    let alive = true;
    api<AdminSettings>("/admin/settings")
      .then((s) => {
        if (alive) setSettings(s);
      })
      .catch((e) => notify(e.message));
    return () => {
      alive = false;
    };
  }, [revision, notify]);
  const admin = user.role === "platform_admin";
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">BGYS</span>
          <h1>Güvenlik ve denetim</h1>
          <p>
            Parolanızı yönetin
            {admin
              ? ", denetim kaydını inceleyin ve otomasyon durumunu görün."
              : " ve güvenlik ayarlarını görün."}
          </p>
        </div>
      </div>
      <div className="security-grid">
        <PasswordPanel user={user} notify={notify} />
        {settings && <SettingsPanel settings={settings} />}
      </div>
      {admin && (
        <>
          <AuditPanel revision={revision} notify={notify} />
          <MailPanel
            revision={revision}
            refresh={refresh}
            notify={notify}
            openTicket={openTicket}
          />
        </>
      )}
    </>
  );
}

function PasswordPanel({
  user,
  notify,
}: {
  user: User;
  notify: (text: string) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  if (!user.has_password)
    return (
      <section className="panel">
        <div className="panel-head">
          <h2>
            <KeyRound size={20} />
            Parola
          </h2>
        </div>
        <p className="panel-note">
          Hesabınız SenseİK oturumuyla açılır; bu portalda ayrı parola yoktur.
        </p>
      </section>
    );
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <KeyRound size={20} />
          Parolayı değiştir
        </h2>
        <span className="muted">
          {user.password_changed_at
            ? `Son değişiklik ${date(user.password_changed_at)}`
            : "Henüz değiştirilmedi"}
        </span>
      </div>
      <form
        className="panel-form"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const data = Object.fromEntries(new FormData(form)) as Record<
            string,
            string
          >;
          if (data.new_password !== data.confirm) {
            setError("Yeni parola ile tekrarı aynı olmalı.");
            return;
          }
          setBusy(true);
          setError("");
          try {
            await post("/auth/password", {
              current_password: data.current_password,
              new_password: data.new_password,
            });
            form.reset();
            notify("Parolanız değiştirildi. Diğer oturumlarınız kapatıldı.");
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Mevcut parola">
          <input
            name="current_password"
            type="password"
            autoComplete="current-password"
            required
          />
        </Field>
        <Field label="Yeni parola">
          <input
            name="new_password"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={200}
            required
          />
        </Field>
        <Field label="Yeni parola (tekrar)">
          <input
            name="confirm"
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={200}
            required
          />
        </Field>
        <small className="hint">
          En az 12 karakter; adınızı veya e-postanızı içermemeli. Değişiklik
          diğer tüm oturumlarınızı kapatır ve denetim kaydına yazılır.
        </small>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button className="button primary" disabled={busy}>
            {busy ? "Kaydediliyor…" : "Parolayı güncelle"}
          </button>
        </div>
      </form>
    </section>
  );
}

function SettingsPanel({ settings }: { settings: AdminSettings }) {
  const rows: [string, string][] = [
    [
      "SenseİK Asistan",
      settings.ai_available
        ? `Açık · varsayılan ${settings.ai_mode === "auto" ? "otomatik yanıt" : "taslak"} · ${settings.ai_model}`
        : "Kapalı (API anahtarı tanımlı değil)",
    ],
    [
      "Otomatik yanıt sınırı",
      `Talep başına ${settings.ai_max_auto_replies} yanıt, sonra ekibe devir`,
    ],
    [
      "Otomatik kapanış",
      settings.auto_close_days > 0
        ? `Çözülen talep ${settings.auto_close_days} gün sonra kapanır`
        : "Kapalı",
    ],
    [
      "E-posta bildirimi",
      settings.mail_enabled ? "Açık" : "Kapalı (SMTP tanımlı değil)",
    ],
    [
      "Hesap kilidi",
      `${settings.login_lock_threshold} hatalı denemede ${settings.login_lock_minutes} dk`,
    ],
    ["Boşta kalma", `Personel oturumu ${settings.staff_idle_minutes} dk`],
    [
      "Saklama",
      `Denetim ${settings.retention.audit_days || "∞"} g · bildirim ${settings.retention.notification_days || "∞"} g · e-posta ${settings.retention.mail_days || "∞"} g · kapalı talep ${settings.retention.closed_ticket_days || "süresiz"}`,
    ],
  ];
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <ShieldCheck size={20} />
          Yürürlükteki ayarlar
        </h2>
        <span className="muted">Ortam değişkenleriyle yönetilir</span>
      </div>
      <dl className="settings-list">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="panel-note">
        <Bot size={14} /> Asistan modu firma bazında “Firmalar” sayfasından
        değiştirilir. Tüm değişiklikler denetim kaydına yazılır.
      </p>
    </section>
  );
}

function AuditPanel({
  revision,
  notify,
}: {
  revision: number;
  notify: (text: string) => void;
}) {
  const [list, setList] = useState<AuditList | null>(null),
    [action, setAction] = useState(""),
    [q, setQ] = useState(""),
    [since, setSince] = useState(""),
    [until, setUntil] = useState(""),
    [page, setPage] = useState(1),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const params = new URLSearchParams({
      action,
      q,
      since,
      until,
      page: String(page),
    });
    api<AuditList>(`/admin/audit?${params}`)
      .then((value) => {
        if (alive) setList(value);
      })
      .catch((e) => notify(e.message))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [action, q, since, until, page, revision, notify]);
  const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;
  const exportUrl = `/api/v1/admin/audit/export?${new URLSearchParams({ action, q, since, until })}`;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <ScrollText size={20} />
          Denetim kaydı
        </h2>
        <a className="button secondary" href={exportUrl}>
          <Download size={15} />
          CSV indir
        </a>
      </div>
      <div className="audit-filters">
        <select
          aria-label="İşlem filtresi"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Tüm işlemler</option>
          {Object.entries(list?.actions || {}).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <input
          aria-label="Denetim kaydında ara"
          placeholder="Kullanıcı, ayrıntı, hedef veya IP"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <input
          type="date"
          aria-label="Başlangıç tarihi"
          value={since}
          onChange={(e) => {
            setSince(e.target.value);
            setPage(1);
          }}
        />
        <input
          type="date"
          aria-label="Bitiş tarihi"
          value={until}
          onChange={(e) => {
            setUntil(e.target.value);
            setPage(1);
          }}
        />
      </div>
      {loading && !list ? (
        <Loading />
      ) : !list?.items.length ? (
        <Empty
          title="Kayıt bulunamadı"
          description="Filtreleri değiştirerek tekrar deneyin."
        />
      ) : (
        <div className="audit-table-wrap">
          <table className="audit-table">
            <thead>
              <tr>
                <th>Zaman</th>
                <th>İşlem</th>
                <th>Kullanıcı</th>
                <th>Ayrıntı</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((row) => (
                <tr
                  key={row.id}
                  className={row.outcome !== "success" ? "failure" : ""}
                >
                  <td>{date(row.created_at)}</td>
                  <td>
                    <b>{row.label}</b>
                    {row.outcome !== "success" && (
                      <span className="priority urgent"> · başarısız</span>
                    )}
                  </td>
                  <td>
                    {row.actor_name || "—"}
                    <small>{row.actor_role}</small>
                  </td>
                  <td>
                    {row.detail || row.target_id}
                    {row.target_type && <small>{row.target_type}</small>}
                  </td>
                  <td>{row.ip || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list && list.total > list.page_size && (
        <div className="pagination">
          <button
            className="icon-btn"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
            aria-label="Önceki sayfa"
          >
            <ArrowLeft size={16} />
          </button>
          <span>
            {page} / {pages}
          </span>
          <button
            className="icon-btn"
            disabled={page >= pages}
            onClick={() => setPage(page + 1)}
            aria-label="Sonraki sayfa"
          >
            <ArrowRight size={16} />
          </button>
        </div>
      )}
    </section>
  );
}

function MailPanel({
  revision,
  refresh,
  notify,
  openTicket,
}: {
  revision: number;
  refresh: () => void;
  notify: (text: string) => void;
  openTicket: (id: string) => void;
}) {
  const [queue, setQueue] = useState<MailQueue | null>(null),
    [busy, setBusy] = useState("");
  useEffect(() => {
    let alive = true;
    api<MailQueue>("/admin/mail-queue")
      .then((value) => {
        if (alive) setQueue(value);
      })
      .catch((e) => notify(e.message));
    return () => {
      alive = false;
    };
  }, [revision, notify]);
  if (!queue) return null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>
          <Mail size={20} />
          E-posta kuyruğu
        </h2>
        <span className="muted">
          {queue.enabled
            ? `Bekleyen ${queue.counts.pending} · gönderilen ${queue.counts.sent} · başarısız ${queue.counts.failed}`
            : "SMTP yapılandırılmadı; e-posta gönderilmiyor"}
        </span>
      </div>
      {!queue.items.length ? (
        <p className="panel-note">Bekleyen veya başarısız e-posta yok.</p>
      ) : (
        <div className="management-list">
          {queue.items.map((item) => (
            <article className="management-row" key={item.id}>
              <div className="management-name">
                <h3>{item.subject}</h3>
                <p>
                  {item.recipient} · {date(item.created_at)} · {item.attempts}{" "}
                  deneme
                  {item.last_error && (
                    <>
                      <br />
                      <span className="priority urgent">{item.last_error}</span>
                    </>
                  )}
                </p>
              </div>
              <span
                className={`status ${item.status === "failed" ? "closed" : "open"}`}
              >
                <i />
                {item.status === "failed" ? "Başarısız" : "Bekliyor"}
              </span>
              <button
                className="text-button"
                onClick={() => openTicket(item.ticket_id)}
              >
                #{item.ticket_number}
              </button>
              {item.status === "failed" && (
                <button
                  className="button secondary"
                  disabled={busy === item.id}
                  onClick={async () => {
                    setBusy(item.id);
                    try {
                      await post(`/admin/mail-queue/${item.id}/retry`);
                      refresh();
                      notify("E-posta yeniden kuyruğa alındı.");
                    } catch (e) {
                      notify((e as Error).message);
                    } finally {
                      setBusy("");
                    }
                  }}
                >
                  <RotateCcw size={14} />
                  Yeniden dene
                </button>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
