# SenseİK ürün destek portalı — tasarım ve kapsam

Tarih: 8 Ekim 2026. Durum: Kullanıcı incelemesine hazır öneri; uygulama henüz yazılmadı.

## Amaç

Müşteri SenseİK içindeki Destek bağlantısından kendi firması için destek talebi açar, durumunu takip eder, destek ekibiyle yazışır, hatırlatma oluşturur ve talebini kapatır. AlgoSense destek ekibi aynı ürünün admin ekranından tüm firmaların taleplerini yönetir. Ürün Python ve React ile geliştirilir; görünüm yerel FPHR projesinin marka dilini izler.

## İncelenen kaynaklar

- `https://github.com/celikonline/urundestek.git`: boş depo; çalışma klasörüne klonlandı.
- `../fphr/src/styles.css` ve `typography.css`: Manrope, mor `#362DAE`, turkuaz `#08B9B1`, beyaz yüzey ve açık nötr zemin.
- `../senseik/web/src/config/navigation.ts`: mevcut Destek menüsü `/app/support` adresine gidiyor.
- `../senseik/web/src/services/support.service.ts`: mevcut ürün içinde talep oluşturma ve kullanıcının taleplerini listeleme var. Durumlar `open`, `answered`, `closed`; yeni portalın yazışma ve hatırlatma kapsamı daha geniş.
- `../senseik/web/src/store/auth.store.ts`: mevcut oturum kullanıcı ve firma/tenant bağlamı içeriyor.
- `../senseik/src/Modules/Identity/Sense.Modules.Identity.Infrastructure/Security/TokenAndSecretServices.cs`: mevcut ürün RSA imzalı JWT kullanıyor. Ayrı portal için standart OIDC girişinin mevcut olduğu varsayılmıyor.
- Ortak bilgi deposundaki `patterns/2026-08-self-signed-tls-spa-api-keycloak.md`: React ve API aynı origin altında, `/api` reverse proxy üzerinden yayınlanacak. Keycloak kurulması önerilmiyor; yalnız tek-origin yerleşim deseni uygulanıyor.

## Mimari seçimi

Öneri: React/TypeScript/Vite istemci, Python/FastAPI API, SQLAlchemy ve Alembic ile PostgreSQL. API, iş kuralları ve veri erişimi ayrı modüllerde tutulur; ilk sürüm tek uygulamadır.

Alternatifler:

1. SenseİK içine doğrudan eklemek mevcut oturumu kolay kullanır; fakat ürün API'si .NET olduğu için bağımsız Python ürün hedefiyle uyuşmaz.
2. Her firma için ayrı uygulama ve veritabanı kurmak güçlü fiziksel izolasyon verir; ilk sürümde kurulum ve bakım yükünü artırır.
3. Önerilen ortak uygulama ve firma anahtarlı PostgreSQL, sade müşteri/admin deneyimi ve tek dağıtım sağlar. Sunucu tarafındaki tenant sınırları kabul testleriyle korunur.

## Sade tasarım

FPHR'nin pazarlama sayfasındaki büyük hero yerine destek işine uygun kompakt uygulama kabuğu kullanılır. Marka renkleri ve tipografi korunur. Animasyon, grafik ve büyük sayaç kartları gerekli değil.

Tokenlar:

| Rol | Değer |
| --- | --- |
| Ana eylem / seçili öğe | `#362DAE` |
| İkincil marka vurgusu | `#08B9B1` |
| Metin | `#202348` |
| İkincil metin | `#454E65` |
| Zemin | `#F7F8FC` |
| Yüzey | `#FFFFFF` |

Başlık ve gövde Manrope ailesinden; başlıklar 750/800, gövde 450/500. Talep numarası tabular rakamlarla gösterilir. Yazı boyutu gövdede en az 14px; belirgin klavye odağı ve metinli durum etiketleri bulunur. Durum renkleri tek başına anlam taşımaz. Dekoratif gradyan kullanılmaz.

İki yerleşim değerlendirildi:

```text
A — Önerilen: aynı ekranda liste ve konuşma
┌ SenseİK · Destek                       Firma / Kullanıcı ┐
├ Taleplerim | Hatırlatmalar              + Yeni talep      ┤
├ Arama / durum filtresi ┬ Talep #1042 · İnceleniyor         ┤
│ Seçili talep          │ Konu ve kısa bilgiler            │
│ Diğer talepler        │ Müşteri / destek yazışma geçmişi │
│                      │ Mesaj alanı                      │
│                      │ Hatırlatma · Talebi kapat        │
└──────────────────────┴──────────────────────────────────┘

B — Alternatif: tam genişlik liste, ayrı detay sayfası
┌ Firma · Destek                        + Yeni talep       ┐
├ Arama / durum / kategori                                 ┤
│ Talep tablosu                                            │
│ Seçilen talep ayrı sayfada açılır                         │
└─────────────────────────────────────────────────────────┘
```

A seçilir: takip ve yazışma arasında geçiş gerekmez. Dar ekranlarda liste veya detay tek sütunda gösterilir; geri düğmesiyle listeye dönülür. İmza öğesi, her talebin üstündeki sade durum çizgisidir: Açık → İnceleniyor → Yanıtınız bekleniyor → Çözüldü → Kapalı. Çizgi bir süreç göstergesidir; gerçek durum dışında ilerleme üretmez.

## Müşteri akışları

### Talepler

Liste varsayılan olarak açık talepleri gösterir; tümü, kapalı, kategori ve metin araması vardır. Her satırda numara, konu, durum, son hareket zamanı ve okunmamış yanıt işareti bulunur. Firma bağlamı üst çubukta sürekli görünür.

Yeni talep formu: konu (5–160 karakter), kategori, öncelik (normal/yüksek/acil), açıklama (10–10.000 karakter). Kategoriler: Genel, İzin ve fazla mesai, Bordro, Veri aktarımı, Onaylar, Erişim ve yetkiler, Faturalandırma, Diğer. İlk sürüm SenseİK ürünüyle sınırlıdır; gereksiz ürün seçimi gösterilmez.

İlk sürümde dosya eki yoktur. Müşteri mesajları düz metindir; HTML çalıştırılmaz. Başarılı oluşturma yeni talebi açar. Hatalı formda girilen içerik korunur. Tekrar gönderim aynı idempotency anahtarıyla ikinci talep oluşturmaz.

### Yazışma ve durum

Konuşmada ilk açıklama, müşteri mesajları, destek yanıtları ve durum olayları tarih sırasıyla görünür. Mesaj göndermek müşteri için talebi `open`, destek için `waiting_customer` durumuna getirir. Admin bir talebi `in_progress` veya `resolved` durumuna alabilir. Müşteri ve admin açık bir talebi kapatabilir. Kapalı talep okunabilir; mesaj veya yeni hatırlatma eklemek için açıkça yeniden açılır.

Müşteri kendi taleplerini görür. Firma yöneticisi ayrıca firmasının tüm taleplerini görür ve yanıtlayabilir. Bu varsayım ilk sürümün erişim kuralıdır; sıradan kullanıcı aynı firmadaki diğer kişilerin yazışmalarını göremez.

### Hatırlatma ve takip isteme

“Hatırlatma oluştur” tarih/saat ve kısa not ister. Gelecek zaman zorunludur; kullanıcı görüntüleme bölgesi Europe/Istanbul, veritabanı UTC'dir. Zamanı gelen hatırlatma portalın Hatırlatmalar bölümünde görünür ve uygulama içi bildirim oluşturur. Kullanıcı kendi hatırlatmasını tamamlayabilir veya iptal edebilir. Hatırlatma kişiseldir; başka müşterilere ve destek ekibine gösterilmez.

“Güncel durum iste” destek ekibine kayıtlı bir takip mesajı ekler. Aynı talepte 24 saat içinde yeniden gönderilemez. Bu eylem takvim hatırlatmasından ayrıdır. Talep kapanınca bekleyen hatırlatmaları iptal edilir. İlk sürüm e-posta veya SMS teslimatı içermez; bildirimler portalda görünür.

## Admin ekranı

`/admin` yalnız destek görevlisi ve platform yöneticisine açıktır. Üst çubukta açık talep ve zamanı geçmiş hatırlatmalar için kompakt bağlantılar bulunur. Ana ekran müşteriyle aynı liste/konuşma düzenini kullanır.

- Tüm firmalar / firma filtresi, durum, öncelik, sorumlu ve metin araması.
- Talebi destek görevlisine atama veya atamayı kaldırma.
- Müşteriye açık yanıt yazma ve yalnız destek ekibine görünen iç not ekleme; bu iki eylem farklı etiketlenir.
- Durum değiştirme, öncelik belirleme, kapatma ve yeniden açma.
- Firma listesi: SenseİK firma kimliği, ad, aktif/pasif destek erişimi ve açık talep sayısı.
- Destek görevlileri: yalnız platform yöneticisi rol atar veya erişimi iptal eder.
- Müşteri ve iç not görünürlüğü API yanıtlarının kendisinde ayrılır. İç notlar müşteri DTO'suna hiç eklenmez.

Destek personelinin firmalar arası erişimi ayrı yetkiyle sağlanır; firma parametresi göndermek bu erişimi sağlamaz. Firma yöneticisi portal admini sayılmaz.

## SenseİK'ten doğrudan bağlantı

Firma slug'ı içeren düz bağlantı oturum olmadan yetki sağlamaz. SenseİK access/refresh token'ları URL'ye koyulmaz.

Önerilen köprü:

1. SenseİK'in mevcut Destek menüsüne portalı açan eylem eklenir.
2. Mevcut SenseİK oturumu ile backend'den en fazla 60 saniye geçerli, tek kullanımlık destek giriş kodu alınır. Kullanıcı ve firma sunucu oturumundan türetilir.
3. Destek portalı `/giris#code=...` adresinde açılır; fragment hemen temizlenir. Kod support API'ye POST edilir.
4. Support API kodu güvenilir SenseİK sunucu ucunda tüketir. Süre, tek kullanım, aktif kullanıcı, firma ve hedef uygulama doğrulanır. Destek rolü, portalın kendi personel kaydından gelir.
5. Support API kendi HttpOnly/Secure/SameSite oturum çerezini üretir ve `/firma/{slug}/talepler` adresine yönlendirir. Çerez oturumu ve aktif firma her istekte doğrulanır.

SenseİK tarafında bu kod verme/tüketme uçlarının varlığı görülmedi. Bu nedenle doğrudan giriş için küçük bir Identity entegrasyonu gereklidir. Ürün değişikliği ayrı, incelenebilir bir patch ve README olarak `integrations/senseik/` altında teslim edilir; mevcut SenseİK depodaki başka çalışmalarına karıştırılmaz. Mevcut SenseİK destek kayıtları otomatik kopyalanmaz; yeni portalın kaydı ayrı tutulur. Bağlantı açıldığında hangi sistemde talep oluşturulduğu kullanıcıya açık olur.

Yerel geliştirme için yalnız açıkça etkinleştirilen geliştirme modu, iki sentetik firma ve ayrı müşteri/admin oturumları sağlar. Üretimde geliştirme girişi bulunmaz. Canlı alan adı ve SenseİK güvenilir bağlantı ayarları ortam değişkenleriyle verilir; repoya sır yazılmaz.

## Veri modeli ve izolasyon

- Tenant: UUID, benzersiz external SenseİK tenant ID, slug, ad, aktiflik.
- User: external user ID, tenant ID, ad; aynı kişinin farklı firma üyelikleri ayrıdır.
- Staff: user ID, support_agent/platform_admin rolü, aktiflik.
- Session: hash'lenmiş token, kullanıcı, tenant, sona erme, iptal bilgisi.
- Ticket: tenant ID, oluşturan üyelik, firma içinde sıra numarası, konu, kategori, öncelik, durum, sorumlu, version, UTC tarihler.
- Message: tenant ID, ticket ID, yazar, düz metin, müşteri/destek/iç not türü, UTC tarih.
- Reminder: tenant ID, ticket ID, sahibi, hedef UTC zaman, not, tamamlanma/iptal bilgisi.
- TicketEvent: tenant ID, ticket ID, actor, olay türü ve eski/yeni durum; değişmez denetim izi.
- Notification: tenant ID, alıcı, ticket ID, tür, okunma ve oluşturulma zamanı.

Veri erişimi yetkili tenant kapsamını zorunlu alır. Mesaj ve hatırlatmalarda ticket/tenant birleşik ilişki doğrulaması yapılır. Müşteri tarafından gelen tenant ID oturumun yerine geçmez. Firma dışında talep, mesaj, hatırlatma ve kullanıcı kimliği 404 döner. SQL parametrelidir; tenant+durum+son hareket ve reminder+hedef zaman indeksleri migration ile eklenir.

Her yazışma/durum olayı tek işlemde kayıt ve bildirim oluşturur. Version ile eşzamanlı güncelleme çatışması 409 döner; yeni durum ekranda yüklenir. Hatırlatma işçisi her dakika çalışır; çoklu işçi aynı kaydı iki kez bildiremez. Önceden due olmuş hatırlatmalar yeniden başlatma sonrası işlenir. UTC çıktılar ISO-8601 ve zaman bölgesi belirteciyle döner.

## API yüzeyi

`/api/v1` altında:

| İşlem | Uç |
| --- | --- |
| Giriş kodunu tüket / çıkış / oturum | `POST /auth/exchange`, `POST /auth/logout`, `GET /me` |
| Talepleri filtrele / oluştur | `GET /tickets`, `POST /tickets` |
| Detay | `GET /tickets/{id}` |
| Mesaj | `POST /tickets/{id}/messages` |
| Kapat / yeniden aç / durum iste | `POST /tickets/{id}/close`, `/reopen`, `/follow-up` |
| Hatırlatma oluştur | `POST /tickets/{id}/reminders` |
| Kendi hatırlatmaları / tamamla / iptal | `GET /reminders`, `POST /reminders/{id}/complete`, `DELETE /reminders/{id}` |
| Bildirimler / okundu | `GET /notifications`, `POST /notifications/{id}/read` |
| Admin liste / değişiklik / iç not | `GET /admin/tickets`, `PATCH /admin/tickets/{id}`, `POST /admin/tickets/{id}/notes` |
| Firmalar / destek personeli | `GET/PATCH /admin/tenants`, `GET/POST/PATCH /admin/staff` |

Liste uçları sayfalıdır; sayfa boyutu en fazla 100. İstemci aktif konuşmayı 15 saniyede yeniler; sekme görünmüyorsa yenileme durur. WebSocket ilk sürüm için gerekli değildir. Yazma işlemlerinde CSRF koruması ve origin doğrulaması vardır; giriş ve takip uçları hız sınırlıdır. Kullanıcıya Türkçe hata, loglara PII içermeyen korelasyon ID ve hata kodu döner.

## Çalıştırma ve teslim

Önerilen dizinler: `backend/app/{api,services,repositories,models}`, `backend/alembic`, `backend/tests`, `frontend/src/{components,features,lib}`, `integrations/senseik`, `docs`.

Docker Compose: PostgreSQL, Python API, hatırlatma işçisi ve React build'ini sunan nginx. Nginx `/api` isteklerini API'ye iletir. Yerel geliştirmede Vite proxy aynı yolu korur. Kurulum ve migration komutları README'de; örnek ortam dosyası sır içermez. CI backend testleri ve frontend typecheck/build çalıştırır.

## Kabul ve doğrulama

1. Müşteri formdan talep açar; sayfa yenilenince ve API yeniden başlatılınca veri kalır.
2. İki sentetik firma arasında liste, detay, mesaj, bildirim ve hatırlatma erişimi denenir; ID değiştirmekle veri sızmaz.
3. Aynı firmadaki sıradan kullanıcı yalnız kendi taleplerini; firma yöneticisi firmanın taleplerini görür.
4. Admin firma filtresiyle talep bulur, atar ve yanıtlar; müşteri yanıtı görür. İç not API'de ve UI'da müşteri için görünmez.
5. Müşteri mesaj gönderir, durum değişir; kapalı talebe yazma reddedilir; yeniden açma sonrası yazışma sürer.
6. Geleceğe hatırlatma oluşturulur; zamanı gelince tek bildirim oluşur. Yeniden başlatma ve iki işçi senaryosu aynı bildirimi çoğaltmaz.
7. Aynı giriş kodu ikinci kez kullanılamaz; süresi geçmiş kod, başka hedef, pasif kullanıcı ve firma reddedilir. Firma parametresi değiştirmek oturum kapsamını değiştirmez.
8. Masaüstü ve mobil müşteri/admin akışları tarayıcıda doğrulanır; klavyeyle form, konuşma, modal ve filtre kullanılabilir. Yatay sayfa taşması olmaz.
9. API entegrasyon testleri, React typecheck/build ve temel uçtan uca talep–yanıt–kapatma testi geçer.

## İlk sürüm sınırı

Talep yönetimi, yazışma, kişisel hatırlatma, uygulama içi bildirim, çok firma izolasyonu, destek admini ve SenseİK giriş köprüsü bu tasarımın kapsamıdır. Ek dosya yükleme, e-posta/SMS bildirimi, SLA otomasyonu, AI yanıt üretimi, bilgi bankası ve eski taleplerin aktarımı sonraki çalışmalardır.
