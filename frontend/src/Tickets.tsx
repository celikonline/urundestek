import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Search,
  MessageSquare,
  BellPlus,
  Check,
  RotateCcw,
  ArrowUpRight,
  SlidersHorizontal,
  Clock3,
  LockKeyhole,
  ChevronDown,
} from "lucide-react";
import { api, post } from "./api";
import { Empty, Loading, Status } from "./components";
import { ReminderForm } from "./TicketForms";
import { MessageComposer, MessageContent } from "./MessageEditor";
import { CATEGORIES, PRIORITIES, STATUSES, date, initials } from "./types";
import type { Staff, Tenant, Ticket, TicketList, User } from "./types";

type Props = {
  user: User;
  revision: number;
  selected: string | null;
  onSelect: (id: string | null) => void;
  refresh: () => void;
  notify: (text: string) => void;
  onNew: () => void;
};
export default function Tickets({
  user,
  revision,
  selected,
  onSelect,
  refresh,
  notify,
  onNew,
}: Props) {
  const [list, setList] = useState<TicketList>({
    items: [],
    total: 0,
    page: 1,
    page_size: 30,
  });
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState("active"),
    [tenantId, setTenantId] = useState(""),
    [priority, setPriority] = useState(""),
    [assigned, setAssigned] = useState(""),
    [category, setCategory] = useState(""),
    [page, setPage] = useState(1);
  const [tenants, setTenants] = useState<Tenant[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [filters, setFilters] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [detail, setDetail] = useState<Ticket | null>(null),
    [detailError, setDetailError] = useState("");
  const initialSelection = useRef(false);
  useEffect(() => {
    if (initialSelection.current || !list.items.length) return;
    initialSelection.current = true;
    if (!selected && window.innerWidth > 640) onSelect(list.items[0].id);
  }, [list.items, onSelect, selected]);
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(query);
      setPage(1);
    }, 250);
    return () => clearTimeout(t);
  }, [query]);
  useEffect(() => {
    if (user.is_staff) {
      Promise.all([
        api<Tenant[]>("/admin/tenants"),
        api<Staff[]>("/admin/staff"),
      ])
        .then(([t, s]) => {
          setTenants(t);
          setStaff(s);
        })
        .catch((e) => setError(e.message));
    }
  }, [user.is_staff, revision]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const params = new URLSearchParams({
      q: search,
      status,
      tenant_id: tenantId,
      priority,
      assigned_to: assigned,
      category,
      page: String(page),
    });
    api<TicketList>(`${user.is_staff ? "/admin" : ""}/tickets?${params}`)
      .then((value) => {
        if (alive) {
          setList(value);
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
  }, [
    search,
    status,
    tenantId,
    priority,
    assigned,
    category,
    page,
    revision,
    user.is_staff,
  ]);
  useEffect(() => {
    let alive = true;
    setDetail(null);
    setDetailError("");
    if (selected) {
      api<Ticket>(`/tickets/${selected}`)
        .then((value) => {
          if (alive) setDetail(value);
        })
        .catch((e) => {
          if (alive) setDetailError(e.message);
        });
      post(`/tickets/${selected}/read`).catch(() => {});
    }
    return () => {
      alive = false;
    };
  }, [selected]);
  useEffect(() => {
    let alive = true;
    if (selected && revision) {
      api<Ticket>(`/tickets/${selected}`)
        .then((value) => {
          if (alive) setDetail(value);
        })
        .catch((e) => {
          if (alive) setDetailError(e.message);
        });
    }
    return () => {
      alive = false;
    };
  }, [selected, revision]);
  const updated = useCallback(
    (ticket: Ticket) => {
      setDetail(ticket);
      refresh();
    },
    [refresh],
  );
  const filter = (setter: (value: string) => void, value: string) => {
    setter(value);
    setPage(1);
  };
  return (
    <>
      <div className="page-intro">
        <div>
          <span className="eyebrow">
            {user.is_staff
              ? "DESTEK YÖNETİMİ"
              : user.tenant?.name.toLocaleUpperCase("tr-TR")}
          </span>
          <h1>
            {user.is_staff ? "Her talebin yanında." : "Birlikte çözelim."}
          </h1>
          <p>
            {user.is_staff
              ? "Firmaların taleplerini takip edin, ekibinizle çözüm üretin."
              : "Taleplerinizi takip edin, destek ekibimizle iletişimde kalın."}
          </p>
        </div>
        {!user.is_staff && (
          <button className="button primary new-ticket" onClick={onNew}>
            <span aria-hidden="true">+</span>Yeni talep
          </button>
        )}
      </div>
      <section
        className={`workspace ${selected ? "has-selection" : ""}`}
        aria-label="Destek talepleri"
      >
        <div className="ticket-list">
          <div className="list-heading">
            <h2>
              {user.is_staff ? "Destek talepleri" : "Taleplerim"}
              <span>{list.total}</span>
            </h2>
            <button
              className={`icon-btn ${filters ? "active" : ""}`}
              onClick={() => setFilters(!filters)}
              aria-label="Ayrıntılı filtreler"
              aria-expanded={filters}
            >
              <SlidersHorizontal size={18} />
            </button>
          </div>
          <div className="search-box">
            <Search size={17} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Konu veya talep numarası ara"
              aria-label="Taleplerde ara"
            />
          </div>
          <div className="list-tabs">
            {[
              ["active", "Aktif"],
              ["", "Tümü"],
              ["closed", "Kapalı"],
            ].map(([v, l]) => (
              <button
                key={v}
                className={status === v ? "selected" : ""}
                onClick={() => filter(setStatus, v)}
              >
                {l}
              </button>
            ))}
          </div>
          {user.is_staff && (
            <label className="firm-filter">
              <span>Firma</span>
              <select
                aria-label="Firma filtresi"
                value={tenantId}
                onChange={(e) => filter(setTenantId, e.target.value)}
              >
                <option value="">Tüm firmalar</option>
                {tenants.map((t) => (
                  <option value={t.id} key={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} />
            </label>
          )}
          {filters && (
            <div className="advanced-filters">
              <select
                aria-label="Durum filtresi"
                value={status}
                onChange={(e) => filter(setStatus, e.target.value)}
              >
                <option value="">Tüm durumlar</option>
                <option value="active">Aktif talepler</option>
                {Object.entries(STATUSES).map(([v, l]) => (
                  <option value={v} key={v}>
                    {l}
                  </option>
                ))}
              </select>
              <select
                aria-label="Öncelik filtresi"
                value={priority}
                onChange={(e) => filter(setPriority, e.target.value)}
              >
                <option value="">Tüm öncelikler</option>
                {Object.entries(PRIORITIES).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
              <select
                aria-label="Kategori filtresi"
                value={category}
                onChange={(e) => filter(setCategory, e.target.value)}
              >
                <option value="">Tüm kategoriler</option>
                {Object.entries(CATEGORIES).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
              {user.is_staff && (
                <select
                  aria-label="Sorumlu filtresi"
                  value={assigned}
                  onChange={(e) => filter(setAssigned, e.target.value)}
                >
                  <option value="">Tüm sorumlular</option>
                  <option value="me">Bana atanan</option>
                  <option value="unassigned">Atanmamış</option>
                  {staff
                    .filter((s) => s.active)
                    .map((s) => (
                      <option value={s.id} key={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              )}
              <button
                className="text-button"
                onClick={() => {
                  setQuery("");
                  setStatus("active");
                  setTenantId("");
                  setPriority("");
                  setAssigned("");
                  setCategory("");
                  setPage(1);
                }}
              >
                Filtreleri temizle
              </button>
            </div>
          )}
          <div className="list-items">
            {error ? (
              <Empty
                title="Talepler yüklenemedi"
                description={error}
                action={
                  <button className="button secondary" onClick={refresh}>
                    Tekrar dene
                  </button>
                }
              />
            ) : loading && !list.items.length ? (
              <Loading />
            ) : !list.items.length ? (
              <Empty
                title="Burada henüz talep yok"
                description="Filtreleri değiştirebilir veya yeni bir talep açabilirsiniz."
                action={
                  !user.is_staff && (
                    <button className="button secondary" onClick={onNew}>
                      Yeni talep aç
                    </button>
                  )
                }
              />
            ) : (
              list.items.map((t) => (
                <button
                  key={t.id}
                  className={`ticket-row ${selected === t.id ? "selected" : ""}`}
                  onClick={() => onSelect(t.id)}
                >
                  <div className="row-top">
                    <span className="ticket-number">#{t.number}</span>
                    <span className="row-date">{date(t.updated_at)}</span>
                  </div>
                  <h3>
                    {t.subject}
                    {t.unread > 0 && (
                      <i className="unread-dot" aria-label="Okunmamış yanıt" />
                    )}
                  </h3>
                  {user.is_staff && (
                    <span className="row-firm">
                      {t.tenant_name} · {t.requester_name}
                    </span>
                  )}
                  <div className="row-bottom">
                    <Status value={t.status} />
                    {t.priority !== "normal" && (
                      <span className={`priority ${t.priority}`}>
                        {PRIORITIES[t.priority]}
                      </span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
          {list.total > 30 && (
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
                {page} / {Math.ceil(list.total / 30)}
              </span>
              <button
                className="icon-btn"
                disabled={page * 30 >= list.total}
                onClick={() => setPage(page + 1)}
                aria-label="Sonraki sayfa"
              >
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          <div className="list-foot">
            <ShieldNote />
          </div>
        </div>
        <div className="ticket-detail">
          {!selected ? (
            <Empty
              title="Bir talep seçin"
              description="Yazışmaları ve talebinizin güncel durumunu burada görüntüleyebilirsiniz."
            />
          ) : detailError ? (
            <Empty
              title="Talep açılamadı"
              description={detailError}
              action={
                <button
                  className="button secondary"
                  onClick={() => onSelect(null)}
                >
                  Listeye dön
                </button>
              }
            />
          ) : !detail ? (
            <Loading />
          ) : (
            <Thread
              key={detail.id}
              ticket={detail}
              user={user}
              staff={staff}
              onBack={() => onSelect(null)}
              onUpdate={updated}
              notify={notify}
              refresh={refresh}
            />
          )}
        </div>
      </section>
    </>
  );
}

function ShieldNote() {
  return (
    <>
      <LockKeyhole size={13} />
      <span>Firmanıza özel destek alanı</span>
    </>
  );
}

function Thread({
  ticket,
  user,
  staff,
  onBack,
  onUpdate,
  notify,
  refresh,
}: {
  ticket: Ticket;
  user: User;
  staff: Staff[];
  onBack: () => void;
  onUpdate: (t: Ticket) => void;
  notify: (text: string) => void;
  refresh: () => void;
}) {
  const [internal, setInternal] = useState(false),
    [busy, setBusy] = useState(false),
    [reminder, setReminder] = useState(false);
  const act = async (
    path: string,
    data: unknown,
    success: string,
    method = "POST",
  ) => {
    setBusy(true);
    try {
      const updated = await api<Ticket>(path, {
        method,
        body: JSON.stringify(data),
      });
      onUpdate(updated);
      notify(success);
      return true;
    } catch (err) {
      notify((err as Error).message);
      refresh();
      return false;
    } finally {
      setBusy(false);
    }
  };
  const modify = (data: Record<string, unknown>) =>
    void act(
      `/admin/tickets/${ticket.id}`,
      { version: ticket.version, ...data },
      "Talep güncellendi.",
      "PATCH",
    );
  const feed = [
    ...(ticket.messages || []).map((m) => ({
      type: "message" as const,
      id: m.id,
      at: m.created_at,
      message: m,
    })),
    ...(ticket.events || []).map((e) => ({
      type: "event" as const,
      id: e.id,
      at: e.created_at,
      event: e,
    })),
  ].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  const progress = [
    "open",
    "in_progress",
    "waiting_customer",
    "resolved",
    "closed",
  ];
  return (
    <>
      <div className="detail-heading">
        <button
          className="icon-btn mobile-back"
          onClick={onBack}
          aria-label="Talep listesine dön"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <div className="detail-kicker">
            <span>TALEP #{ticket.number}</span>
            <Status value={ticket.status} />
          </div>
          <h2>{ticket.subject}</h2>
          <p>
            {CATEGORIES[ticket.category]}
            <span>·</span>
            {user.is_staff ? ticket.tenant_name : "SenseİK"}
            <span>·</span>
            {date(ticket.created_at)}
          </p>
        </div>
        <button
          className="icon-btn detail-close"
          onClick={onBack}
          aria-label="Talep detayını kapat"
        >
          <ArrowUpRight size={19} />
        </button>
      </div>
      <div
        className="status-track"
        aria-label={`Talep durumu: ${STATUSES[ticket.status]}`}
      >
        {progress.map((status, index) => (
          <span
            key={status}
            aria-current={ticket.status === status ? "step" : undefined}
            className={
              ticket.status === status
                ? "current"
                : index < progress.indexOf(ticket.status)
                  ? "done"
                  : ""
            }
          >
            <span className="status-step-label">
              <i>
                {index < progress.indexOf(ticket.status) ? (
                  <Check size={10} />
                ) : null}
              </i>
              <b>{STATUSES[status]}</b>
            </span>
          </span>
        ))}
      </div>
      {user.is_staff ? (
        <div className="admin-controls">
          <label>
            Durum
            <select
              value={ticket.status}
              disabled={busy}
              onChange={(e) => modify({ status: e.target.value })}
            >
              {Object.entries(STATUSES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sorumlu
            <select
              value={ticket.assigned_to || ""}
              disabled={busy}
              onChange={(e) => modify({ assigned_to: e.target.value || null })}
            >
              <option value="">Atanmamış</option>
              {staff
                .filter((s) => s.active)
                .map((s) => (
                  <option value={s.id} key={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Öncelik
            <select
              value={ticket.priority}
              disabled={busy}
              onChange={(e) => modify({ priority: e.target.value })}
            >
              {Object.entries(PRIORITIES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <div className="detail-assignee">
          <span className="small-avatar">
            {ticket.assignee_name ? initials(ticket.assignee_name) : "SK"}
          </span>
          <span>
            {ticket.assignee_name || "SenseİK destek ekibi"}
            <small>
              {ticket.assignee_name
                ? "Talebinizle ilgileniyor"
                : "Talebiniz destek ekibine ulaştı"}
            </small>
          </span>
          {ticket.priority !== "normal" && (
            <span className={`priority ${ticket.priority}`}>
              {PRIORITIES[ticket.priority]} öncelik
            </span>
          )}
        </div>
      )}
      <div className="conversation" aria-label="Talep yazışmaları">
        {feed.map((item) =>
          item.type === "event" ? (
            <div className="timeline-event" key={item.id}>
              <i />
              <span>{item.event.label}</span>
              <time>{date(item.at)}</time>
            </div>
          ) : (
            <article
              key={item.id}
              className={`message ${item.message.kind} ${item.message.author_id === user.id ? "own" : ""}`}
            >
              <div className="message-head">
                <span className="small-avatar">
                  {initials(item.message.author_name)}
                </span>
                <b>{item.message.author_name}</b>
                {item.message.kind === "support" && (
                  <span className="support-label">Destek ekibi</span>
                )}
                {item.message.kind === "internal" && (
                  <span className="support-label">
                    <LockKeyhole size={10} /> İç not
                  </span>
                )}
                <time>{date(item.at)}</time>
              </div>
              <MessageContent message={item.message} />
            </article>
          ),
        )}
        <div className="conversation-end">
          <MessageSquare size={12} />
          <span>Tüm yazışmalar bu talepte saklanır.</span>
        </div>
      </div>
      <div className="composer">
        {ticket.status === "closed" ? (
          <div className="closed-banner">
            <span>
              <Check size={18} />
              Bu talep kapatıldı.
            </span>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() =>
                void act(
                  `/tickets/${ticket.id}/reopen`,
                  { version: ticket.version },
                  "Talep yeniden açıldı.",
                )
              }
            >
              <RotateCcw size={15} />
              Yeniden aç
            </button>
          </div>
        ) : (
          <>
            <div className="composer-tabs">
              <button
                className={!internal ? "selected" : ""}
                disabled={busy}
                onClick={() => setInternal(false)}
              >
                <MessageSquare size={14} />
                {user.is_staff ? "Müşteriye yanıt" : "Mesaj yaz"}
              </button>
              {user.is_staff && (
                <button
                  className={internal ? "selected" : ""}
                  disabled={busy}
                  onClick={() => setInternal(true)}
                >
                  <LockKeyhole size={13} />
                  İç not
                </button>
              )}
              <span>
                {internal
                  ? "Yalnız destek ekibi görür"
                  : "Bu talep üzerinden paylaşılır"}
              </span>
            </div>
            {[false, ...(user.is_staff ? [true] : [])].map((isInternal) => (
              <div key={String(isInternal)} hidden={isInternal !== internal}>
                <MessageComposer
                  internal={isInternal}
                  busy={busy}
                  onSend={async (payload) => {
                    setBusy(true);
                    payload.set("version", String(ticket.version));
                    try {
                      const updated = await api<Ticket>(
                        isInternal
                          ? `/admin/tickets/${ticket.id}/notes/with-files`
                          : `/tickets/${ticket.id}/messages/with-files`,
                        { method: "POST", body: payload },
                      );
                      onUpdate(updated);
                      notify(
                        isInternal
                          ? "İç not kaydedildi."
                          : "Mesajınız gönderildi.",
                      );
                      return true;
                    } catch (err) {
                      notify((err as Error).message);
                      refresh();
                      return false;
                    } finally {
                      setBusy(false);
                    }
                  }}
                />
              </div>
            ))}
          </>
        )}
        <div className="ticket-actions">
          {ticket.status !== "closed" && (
            <>
              <button className="text-button" onClick={() => setReminder(true)}>
                <BellPlus size={15} />
                Hatırlatma oluştur
              </button>
              {!user.is_staff && (
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      `/tickets/${ticket.id}/follow-up`,
                      { version: ticket.version },
                      "Güncel durum isteğiniz destek ekibine iletildi.",
                    )
                  }
                >
                  <Clock3 size={15} />
                  Güncel durum iste
                </button>
              )}
              <button
                className="text-button close-action"
                disabled={busy}
                onClick={() =>
                  void act(
                    `/tickets/${ticket.id}/close`,
                    { version: ticket.version },
                    "Talep kapatıldı.",
                  )
                }
              >
                <Check size={15} />
                Talebi kapat
              </button>
            </>
          )}
        </div>
      </div>
      {reminder && (
        <ReminderForm
          ticket={ticket}
          onClose={() => setReminder(false)}
          onSaved={() => {
            setReminder(false);
            refresh();
            notify("Hatırlatma kaydedildi.");
          }}
        />
      )}
    </>
  );
}
