# SenseİK Destek — BGYS (ISO/IEC 27001:2022) uyum eşlemesi

Tarih: 8 Ekim 2026. Bu belge destek portalının hangi teknik kontrolleri uyguladığını, hangi Annex A maddesine karşılık geldiğini ve denetimde nereden kanıt alınacağını özetler. Kurumsal politika, eğitim ve fiziksel güvenlik gibi uygulama dışı kontroller kapsam dışıdır; sorumlu süreç sahibi bunları BGYS el kitabında ayrıca tanımlar.

## Kapsam ve varlıklar

| Varlık | Sınıf | Saklama yeri |
| --- | --- | --- |
| Talep, mesaj ve olay kayıtları | Gizli (müşteri verisi) | PostgreSQL `tickets`, `messages`, `ticket_events` |
| Ekler | Gizli | `support-uploads` volume (dosya adı yerine UUID) |
| Personel hesapları ve parola özetleri | Gizli | `users` (scrypt, tuz ile) |
| Oturum ve giriş kodları | Gizli | `sessions`, `launch_codes` (yalnız SHA-256 özeti) |
| Denetim izi | İç kullanım, değiştirilemez | `audit_logs` |
| E-posta kuyruğu | İç kullanım | `outbound_emails` (kısa bildirim metni, mesaj gövdesi yok) |
| Asistan iş kuyruğu | İç kullanım | `ai_jobs` |

## Kontrol eşlemesi

| Annex A | Kontrol | Uygulama | Kanıt / doğrulama |
| --- | --- | --- | --- |
| 5.15, 5.18 | Erişim kontrolü ve erişim hakları | Rol tabanlı yetki (`customer`, `tenant_admin`, `support_agent`, `platform_admin`, `assistant`). Her sorgu kiracı kapsamından geçer; firma dışı kayıt 404 döner. Platform yöneticisi rol ve erişim verir, kendi yetkisini düşüremez. | `backend/app/repository.py` `ticket_scope`; `tests/test_portal.py` kiracı testleri; denetim kaydı `staff.update` |
| 5.16 | Kimlik yönetimi | Personel hesapları yalnız platform yöneticisi tarafından açılır; müşteri kimliği SenseİK'ten tek kullanımlık 60 sn kodla türetilir. Pasife alınan personelin tüm oturumları anında silinir. | `routes.py` `staff_create`, `staff_edit`; `test_security.py::test_staff_deactivation_ends_sessions...` |
| 5.17 | Kimlik doğrulama bilgisi | Parola politikası: ≥12 karakter, e-posta/ad içermez, tahmin edilebilir kalıp reddedilir. scrypt (n=16384) ile özet. Parola değişikliği diğer oturumları sonlandırır ve denetime yazılır. 5 hatalı denemede 15 dk hesap kilidi; IP başına 30/dk hız sınırı. | `auth.py` `password_problem`, `authenticate_staff`, `change_password`; `test_security.py` |
| 8.5 | Güvenli kimlik doğrulama | Oturum çerezi HttpOnly/Secure/SameSite=Lax; CSRF başlığı zorunlu; müşteri oturumu 15 dk, personel 8 saat mutlak + 60 dk boşta kalma süresi. | `auth.py` `current_user`; `test_security.py::test_idle_staff_session_expires` |
| 8.15 | Kayıt tutma (logging) | Değiştirilemez `audit_logs`: giriş/çıkış, hatalı giriş, kilit, parola değişikliği, personel ve firma yönetimi, dosya indirme, dışa aktarma, tercih değişikliği, asistan eylemleri, saklama silmeleri. Her kayıtta aktör, rol, hedef, sonuç, IP, kullanıcı aracısı, korelasyon ID ve UTC zaman. API'de güncelleme/silme ucu yoktur. | `audit.py`; `/api/v1/admin/audit`; CSV dışa aktarma kendisi de denetlenir |
| 8.16 | İzleme faaliyetleri | Platform yöneticisi denetim kaydını işlem, kullanıcı, tarih ve metinle filtreler; e-posta kuyruğundaki başarısız teslimatlar görünür ve yeniden denenir. Uygulama logları mesaj/parola/JWT içermez, hata tipi ve korelasyon ID yazar. | Yönetim → Güvenlik ekranı; `main.py` istisna işleyici |
| 8.10 | Bilgi silme | Saklama işçisi: süresi dolan oturum/giriş kodları, 180 gün sonra bildirimler, 30 gün sonra gönderilmiş e-postalar, 730 gün sonra denetim kaydı, isteğe bağlı `CLOSED_TICKET_RETENTION_DAYS` ile kapalı talepler ve ekleri. Her silme turu `retention.purge` olarak denetlenir. | `retention.py`; `test_security.py::test_retention_purge...` |
| 8.12 | Veri sızıntısı önleme | E-posta bildirimleri mesaj gövdesini ve ekleri taşımaz; yalnız talep numarası, konu ve portal bağlantısı. İç notlar ve ekleri müşteri DTO'suna hiç girmez. Asistana ekler ve iç notlar gönderilmez. | `mailer.py` `queue_email`; `ai.py` `transcript`; `test_notifications.py` |
| 8.24 | Kriptografi | Parola: scrypt; oturum ve giriş kodu: SHA-256 özeti; SMTP: STARTTLS/SSL; HTTPS sonlandırma ters proxy'de; çerez `Secure`. | `auth.py`, `mailer.py` `deliver`, `deployment/nginx.conf` |
| 8.20, 8.22 | Ağ güvenliği ve ağ ayrımı | API ve PostgreSQL dışa yayınlanmaz; yalnız nginx 127.0.0.1:8080. Proxy IP başlıkları nginx tarafından yeniden yazılır. CORS yalnız portal ve SenseİK origin'ine açık. | `docker-compose.yml`, `nginx.conf`, `main.py` CORS |
| 8.23 | Web filtreleme / güvenli başlıklar | API: `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'`, `Permissions-Policy`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, `X-Content-Type-Options`. Web: CSP, frame-ancestors 'none'. | `test_security.py::test_security_headers_present` |
| 8.26 | Uygulama güvenliği gereksinimleri | Girdi doğrulama (Pydantic, `extra="forbid"`), HTML temizleme (nh3/DOMPurify), dosya türü ve boyut doğrulama, idempotency, iyimser kilit (version). | `schemas.py`, `rich_text.py`, `attachments.py`, mevcut testler |
| 8.28 | Güvenli kodlama | CI'da API testleri, derleme ve tarayıcı testleri; bağımlılıklar sabit sürümlü. | `.github/workflows/ci.yml`, `requirements.txt`, `package-lock.json` |
| 8.13 | Bilgi yedekleme | PostgreSQL ve `support-uploads` volume'u birlikte yedeklenir; migration ve yedek birlikte sürümlenir. | README "Üretim" bölümü (uygulama dışı süreç) |
| 5.34, 8.11 | Gizlilik ve kişisel veri koruma, veri maskeleme | Formlarda "parola veya kişisel çalışan verisi paylaşmayın" uyarısı; asistan kişisel veri istemez ve tekrar etmez; denetim kaydı yalnız e-posta/ID gibi iş kimliklerini tutar. | `TicketForms.tsx`, `ai.py` sistem komutu |

## Yapay zekâ asistanı için ek kontroller

- **Mod denetimi.** Varsayılan mod `draft`: asistan yalnız destek ekibine iç not yazar, müşteriye hiçbir şey gitmez. `auto` mod firma bazında ve açıkça açılır; platform yöneticisi her değişikliği denetim kaydında görür (`tenant.update`).
- **İnsan devri.** Veri düzeltme, yetki, bordro/fatura tutarı, güvenlik ve şikâyet içeren talepler ile düşük güvenli yanıtlar her zaman destek ekibine düşer. Otomatik yanıt sayısı talep başına `AI_MAX_AUTO_REPLIES` ile sınırlıdır.
- **İzlenebilirlik.** Her asistan eylemi ayrı bir kullanıcı (`SenseİK Asistan`) adına kaydedilir, talep olaylarında ve denetim kaydında (`ai.reply`, `ai.draft`, `ai.resolve`, `ai.auto_close`) görünür. Müşteri arayüzünde asistan yanıtları açıkça etiketlenir.
- **Veri minimizasyonu.** Modele yalnız talep konusu, kategori, firma adı ve müşteri/destek mesaj metinleri gönderilir. Ekler, iç notlar, e-posta adresleri ve kimlik bilgileri gönderilmez. Bilgi bankası dosyası depoda sürümlenir; içine sır yazılmaz.
- **Tedarikçi.** Model sağlayıcısı Anthropic API'dir; işleme sözleşmesi ve veri saklama şartları tedarikçi değerlendirmesinde (5.19–5.21) kayıt altına alınmalıdır.

## Operasyonel ayarlar

| Ortam değişkeni | Varsayılan | Amaç |
| --- | --- | --- |
| `LOGIN_LOCK_THRESHOLD` / `LOGIN_LOCK_MINUTES` | 5 / 15 | Hesap kilitleme |
| `STAFF_IDLE_MINUTES` | 60 | Personel boşta kalma süresi |
| `AUDIT_RETENTION_DAYS` | 730 | Denetim kaydı saklama (0 = süresiz) |
| `NOTIFICATION_RETENTION_DAYS` | 180 | Uygulama içi bildirim saklama |
| `MAIL_RETENTION_DAYS` | 30 | Gönderilmiş/başarısız e-posta kaydı saklama |
| `CLOSED_TICKET_RETENTION_DAYS` | 0 (kapalı) | Kapalı talep ve eklerinin silinmesi |
| `SMTP_*`, `MAIL_FROM` | boş | E-posta bildirimi; boşsa özellik kapalı |
| `ANTHROPIC_API_KEY`, `AI_MODE`, `AI_MODEL` | boş / draft / claude-opus-5-5 | Asistan |
| `AI_MAX_AUTO_REPLIES`, `AI_MIN_CONFIDENCE` | 3 / 0.7 | Otomatik yanıt sınırları |
| `AUTO_CLOSE_DAYS` | 7 | Çözülen talebin otomatik kapanması |

## Denetimde sunulacak kanıtlar

1. `/api/v1/admin/audit/export` çıktısı (CSV, UTC).
2. `docker compose logs api worker` çıktısı: hata tipi ve korelasyon ID'leri, içerik yok.
3. Bu belge, `README.md` ve CI çalıştırma kayıtları.
4. Saklama ayarlarının `.env` değerleri ve `retention.purge` denetim satırları.
