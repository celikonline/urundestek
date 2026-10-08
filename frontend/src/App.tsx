import { useCallback, useEffect, useState } from "react";
import {
  LifeBuoy,
  Bell,
  Building2,
  Users,
  ArrowUpRight,
  LogOut,
  Menu,
  Check,
  ChevronRight,
  CircleHelp,
  ShieldCheck,
} from "lucide-react";
import { api, post, setCsrf } from "./api";
import { Brand, Loading } from "./components";
import Login from "./Login";
import Tickets from "./Tickets";
import { NewTicket } from "./TicketForms";
import { Management, Notifications, Reminders } from "./Panels";
import { Security } from "./Security";
import { initials } from "./types";
import type { Notice, Ticket, User } from "./types";

type Page = "tickets" | "reminders" | "tenants" | "staff" | "security";
export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [boot, setBoot] = useState(true),
    [loginError, setLoginError] = useState("");
  const [page, setPage] = useState<Page>("tickets"),
    [revision, setRevision] = useState(0),
    [selected, setSelected] = useState<string | null>(
      new URLSearchParams(location.search).get("talep"),
    );
  const [newTicket, setNewTicket] = useState(false),
    [notices, setNotices] = useState<Notice[]>([]),
    [showNotices, setShowNotices] = useState(false),
    [mobileMenu, setMobileMenu] = useState(false),
    [toast, setToast] = useState("");
  const notify = useCallback((text: string) => setToast(text), []);
  const refresh = useCallback(() => setRevision((x) => x + 1), []);
  const enter = useCallback((u: User) => {
    setCsrf(u.csrf_token);
    setUser(u);
    // A ticket link from an e-mail survives the login round-trip.
    const pending = new URLSearchParams(location.search).get("talep");
    setSelected(pending);
    setNotices([]);
    setPage("tickets");
    history.replaceState(
      null,
      "",
      (u.is_staff ? "/admin" : `/firma/${u.tenant?.slug}/talepler`) +
        (pending ? `?talep=${pending}` : ""),
    );
  }, []);
  useEffect(() => {
    let alive = true;
    const code = new URLSearchParams(location.hash.slice(1)).get("code");
    if (code) history.replaceState(null, "", location.pathname);
    const request = code
      ? post<User>("/auth/exchange", { code })
      : api<User>("/me");
    request
      .then((u) => {
        if (alive) {
          setCsrf(u.csrf_token);
          setUser(u);
          if (code) enter(u);
        }
      })
      .catch((e) => {
        if (alive && code) setLoginError(e.message);
      })
      .finally(() => {
        if (alive) setBoot(false);
      });
    return () => {
      alive = false;
    };
  }, [enter]);
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setNotices([]);
      setSelected(null);
      setShowNotices(false);
      setNewTicket(false);
      setCsrf("");
      setLoginError("Oturumunuz sona erdi. SenseİK üzerinden tekrar açın.");
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!user) return;
    const timer = setInterval(() => {
      if (!document.hidden) refresh();
    }, 15000);
    return () => clearInterval(timer);
  }, [user, refresh]);
  useEffect(() => {
    let alive = true;
    if (user)
      api<Notice[]>("/notifications")
        .then((n) => {
          if (alive) setNotices(n);
        })
        .catch((e) => {
          if (alive) notify(e.message);
        });
    return () => {
      alive = false;
    };
  }, [user, revision, notify]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5500);
    return () => clearTimeout(timer);
  }, [toast]);
  const choose = (id: string | null) => {
    setSelected(id);
    const url = new URL(location.href);
    if (id) url.searchParams.set("talep", id);
    else url.searchParams.delete("talep");
    history.replaceState(null, "", url.pathname + url.search);
  };
  const navigate = (target: Page) => {
    setPage(target);
    setMobileMenu(false);
    choose(null);
  };
  const openTicket = (id: string) => {
    setPage("tickets");
    choose(id);
  };
  const logout = async () => {
    try {
      await post("/auth/logout");
      setUser(null);
      setCsrf("");
      setSelected(null);
      setNotices([]);
      setLoginError("");
      history.replaceState(null, "", "/giris");
    } catch (e) {
      notify((e as Error).message);
    }
  };
  if (boot)
    return (
      <div className="boot">
        <Brand />
        <Loading />
      </div>
    );
  if (!user) return <Login onLogin={enter} initialError={loginError} />;
  const labels: Record<Page, string> = {
    tickets: user.is_staff ? "Destek talepleri" : "Taleplerim",
    reminders: "Hatırlatmalarım",
    tenants: "Firmalar",
    staff: "Destek ekibi",
    security: "Güvenlik",
  };
  const unread = notices.filter((n) => !n.read).length;
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "mobile-open" : ""}`}>
        <Brand />
        <div className="workspace-label">
          {user.is_staff ? "YÖNETİM ALANI" : "MÜŞTERİ ALANI"}
        </div>
        <nav aria-label="Ana menü">
          <button
            className={page === "tickets" ? "selected" : ""}
            onClick={() => navigate("tickets")}
          >
            <LifeBuoy size={19} />
            {labels.tickets}
          </button>
          <button
            className={page === "reminders" ? "selected" : ""}
            onClick={() => navigate("reminders")}
          >
            <Bell size={18} />
            Hatırlatmalarım
          </button>
          {user.is_staff && (
            <>
              <span className="nav-separator">YÖNETİM</span>
              <button
                className={page === "tenants" ? "selected" : ""}
                onClick={() => navigate("tenants")}
              >
                <Building2 size={18} />
                Firmalar
              </button>
              <button
                className={page === "staff" ? "selected" : ""}
                onClick={() => navigate("staff")}
              >
                <Users size={18} />
                Destek ekibi
              </button>
              <button
                className={page === "security" ? "selected" : ""}
                onClick={() => navigate("security")}
              >
                <ShieldCheck size={18} />
                Güvenlik
              </button>
            </>
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="support-note">
            <CircleHelp size={22} />
            <b>Bir mesaj kadar yakınız.</b>
            <p>Tüm sorularınız için aynı yerde buluşalım.</p>
          </div>
          {user.tenant && (
            <div className="tenant-context">
              <Building2 size={18} />
              <div>
                <b>{user.tenant.name}</b>
                <small>Firma çalışma alanı</small>
              </div>
            </div>
          )}
          <span className="powered">
            SenseİK <span>by AlgoSense</span>
          </span>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="menu-overlay"
          aria-label="Menüyü kapat"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <button
            className="icon-btn menu-toggle"
            onClick={() => setMobileMenu(!mobileMenu)}
            aria-label="Menüyü aç"
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            Destek
            <ChevronRight size={13} />
            <b>{labels[page]}</b>
          </div>
          <div className="topbar-actions">
            <span className="connection">
              <i />
              {user.is_staff ? "Destek yönetimi" : "Müşteri destek alanı"}
            </span>
            <button
              className="icon-btn notification-button"
              onClick={() => setShowNotices(true)}
              aria-label={`Bildirimler${unread ? `, ${unread} okunmamış` : ""}`}
            >
              <Bell size={19} />
              {unread > 0 && <span>{unread > 9 ? "9+" : unread}</span>}
            </button>
            <span className="topbar-divider" />
            <div className="user-summary">
              <span className="avatar small">{initials(user.name)}</span>
              <div>
                <b>{user.name}</b>
                <small>
                  {user.is_staff
                    ? "Destek ekibi"
                    : user.role === "tenant_admin"
                      ? "Firma yöneticisi"
                      : "Müşteri"}
                </small>
              </div>
            </div>
            <button
              className="icon-btn"
              onClick={() => void logout()}
              aria-label="Çıkış yap"
              title="Çıkış yap"
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <main className="main-content">
          {page === "tickets" ? (
            <Tickets
              user={user}
              revision={revision}
              selected={selected}
              onSelect={choose}
              refresh={refresh}
              notify={notify}
              onNew={() => setNewTicket(true)}
            />
          ) : page === "reminders" ? (
            <Reminders
              revision={revision}
              refresh={refresh}
              notify={notify}
              openTicket={openTicket}
            />
          ) : page === "security" ? (
            <Security
              user={user}
              revision={revision}
              refresh={refresh}
              notify={notify}
              openTicket={openTicket}
            />
          ) : (
            <Management
              kind={page}
              user={user}
              revision={revision}
              refresh={refresh}
              notify={notify}
            />
          )}
          <footer className="app-footer">
            <span>SenseİK destek · Birlikte ilerliyoruz.</span>
            <span>
              <Check size={12} />
              Güvenli firma alanı
            </span>
          </footer>
        </main>
      </div>
      {newTicket && (
        <NewTicket
          onClose={() => setNewTicket(false)}
          onCreated={(ticket: Ticket) => {
            setNewTicket(false);
            openTicket(ticket.id);
            refresh();
            notify(
              "Talebiniz oluşturuldu. Destek ekibimiz sizinle iletişime geçecek.",
            );
          }}
        />
      )}
      {showNotices && (
        <Notifications
          notices={notices}
          user={user}
          onUser={setUser}
          onClose={() => setShowNotices(false)}
          openTicket={openTicket}
          refresh={refresh}
          notify={notify}
        />
      )}{" "}
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          <span>{toast}</span>
          <button onClick={() => setToast("")} aria-label="Bildirimi kapat">
            <ArrowUpRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
