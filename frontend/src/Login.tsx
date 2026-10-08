import { useEffect, useState } from "react";
import {
  ArrowRight,
  MessageSquare,
  ShieldCheck,
  Clock3,
  LifeBuoy,
  Building2,
} from "lucide-react";
import { api, post, setCsrf } from "./api";
import { Brand, External, Field } from "./components";
import type { User } from "./types";

export default function Login({
  onLogin,
  initialError,
}: {
  onLogin: (u: User) => void;
  initialError: string;
}) {
  const [options, setOptions] = useState<{
    development: boolean;
    senseik_url: string | null;
  }>({ development: false, senseik_url: null });
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(initialError);
  useEffect(() => {
    api<typeof options>("/auth/options")
      .then(setOptions)
      .catch((e) => setError(e.message));
  }, []);
  const enter = async (path: string, body: unknown) => {
    setBusy(true);
    setError("");
    try {
      const user = await post<User>(path, body);
      setCsrf(user.csrf_token);
      onLogin(user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-page">
      <div className="login-nav">
        <Brand />
        <span>İhtiyacınız olduğunda, yanınızdayız.</span>
      </div>
      <main className="login-layout">
        <section className="login-story">
          <span className="eyebrow">SENSEİK DESTEK MERKEZİ</span>
          <h1>
            Çözüm için
            <br />
            birlikte ilerleyelim<span>.</span>
          </h1>
          <p>
            Sorularınız, talepleriniz ve tüm yanıtlarınız.
            <br />
            Firmanızın destek süreci tek bir yerde.
          </p>
          <div className="story-items">
            <div>
              <MessageSquare />
              <span>Destek ekibiyle doğrudan yazışın</span>
            </div>
            <div>
              <Clock3 />
              <span>Her adımı takip edin, hatırlatma oluşturun</span>
            </div>
            <div>
              <ShieldCheck />
              <span>Firmanıza özel, güvenli çalışma alanı</span>
            </div>
          </div>
          <div className="story-mark">
            <LifeBuoy size={100} strokeWidth={1} />
            <span>Birlikte çözeriz.</span>
          </div>
        </section>
        <section className="login-card">
          <span className="welcome-icon">
            <LifeBuoy size={27} />
          </span>
          <h2>Destek alanınıza hoş geldiniz</h2>
          <p>
            Müşteriyseniz SenseİK içindeki <b>Destek</b> bağlantısını kullanarak
            giriş yapabilirsiniz.
          </p>
          {options.senseik_url && (
            <External href={options.senseik_url}>SenseİK’e git</External>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {options.development ? (
            <>
              <div className="dev-label">
                <span />
                Yerel demo · Örnek firmalar
              </div>
              <button
                disabled={busy}
                className="demo-account"
                onClick={() => void enter("/auth/demo", { account: "ayse" })}
              >
                <span className="avatar">AY</span>
                <span>
                  <b>Müşteri alanı</b>
                  <small>Ayşe Yılmaz · Atlas Teknoloji</small>
                </span>
                <ArrowRight size={19} />
              </button>
              <button
                disabled={busy}
                className="demo-account"
                onClick={() => void enter("/auth/demo", { account: "admin" })}
              >
                <span className="avatar purple">EA</span>
                <span>
                  <b>Destek yönetimi</b>
                  <small>Ece Arslan · Platform yöneticisi</small>
                </span>
                <ArrowRight size={19} />
              </button>
              <details className="other-accounts">
                <summary>Diğer demo hesapları</summary>
                <div className="demo-options">
                  {[
                    ["deniz", "Nova Lojistik müşterisi"],
                    ["manager", "Atlas firma yöneticisi"],
                    ["emre", "Atlas diğer müşteri"],
                    ["agent", "Destek görevlisi"],
                  ].map(([account, label]) => (
                    <button
                      key={account}
                      className="button secondary"
                      disabled={busy}
                      onClick={() => void enter("/auth/demo", { account })}
                    >
                      <Building2 size={14} />
                      {label}
                    </button>
                  ))}
                </div>
              </details>
            </>
          ) : null}
          <details className="staff-login" open={!options.development}>
            <summary>Destek ekibi girişi</summary>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void enter("/auth/login", { email, password });
              }}
            >
              <Field label="E-posta">
                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field label="Parola">
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <button className="button primary" disabled={busy}>
                {busy ? "Giriş yapılıyor…" : "Giriş yap"}
                <ArrowRight size={17} />
              </button>
            </form>
          </details>
          <div className="login-foot">
            <ShieldCheck size={14} /> Talepleriniz yalnız yetkili kişilerle
            paylaşılır.
          </div>
        </section>
      </main>
      <footer className="login-footer">
        SenseİK · Ürün destek portalı<span>AlgoSense</span>
      </footer>
    </div>
  );
}
