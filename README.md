# SenseİK Destek

FPHR marka dilinde sade müşteri ve destek yönetimi. Python/FastAPI API, React/TypeScript arayüz, PostgreSQL üretim veritabanı; yerel geliştirmede SQLite.

## Hızlı çalıştırma — Windows

Python 3.13+ ve Node.js 24+ ile repo kökünde:

```powershell
./start.ps1
```

[Yerel portal](http://localhost:5173): “Müşteri alanı” ve “Destek yönetimi” demo hesaplarıyla deneyin. “Diğer demo hesapları” altında ikinci firma, firma yöneticisi, aynı firmada diğer müşteri ve destek görevlisi vardır. Tüm veriler kurgusaldır. Demo girişleri yalnız development/test ortamında çalışır.

Manuel çalıştırma / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
npm ci --prefix frontend
export APP_ENV=development COOKIE_SECURE=false PUBLIC_URL=http://localhost:5173
export PYTHONPATH=backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# İkinci terminal:
npm run dev --prefix frontend
```

Windows manuel komutlarında `.venv/Scripts/python` kullanın ve değişkenleri `$env:APP_ENV='development'` biçiminde tanımlayın. Yerel SQLite `data/support.db` altında saklanır ve Git'e eklenmez. Yeniden başlatma verileri korur.

## Özellikler

- Talep açma; konu/numara, durum, kategori ve öncelik filtresi; sayfalama.
- Müşteri ve destek ekibi arasında kalıcı yazışma; okunmamış yanıtlar ve uygulama içi bildirimler.
- Mesajlarda kalın/italik/altı çizili metin, listeler, alıntı, bağlantılar ve geri alma; dosya seçme/sürükleme, Ctrl+V ile ekran görüntüsü yapıştırma ve gönderim öncesi önizleme.
- Dosya başına 10 MB, mesaj başına 5 dosya ve toplam 25 MB. PNG/JPG/WEBP/GIF, PDF, UTF-8 TXT/CSV ve makrosuz DOCX/XLSX. Dosyalar talep yetkisiyle indirilir; iç not ekleri yalnız destek ekibine açıktır.
- Açık, inceleniyor, yanıt bekleniyor, çözüldü, kapalı durumları; kapatma ve yeniden açma.
- Kişisel tarih/saat hatırlatmaları; tamamla/iptal; 24 saatte bir güncel durum isteme.
- Admin firma filtresi, sorumlu atama, öncelik/durum düzenleme, müşteriye görünmeyen iç notlar.
- Platform yöneticisi firma destek erişimini ve personel rol/aktiflik durumunu yönetir.
- Sıradan müşteri kendi taleplerini; firma yöneticisi yalnız firmasının taleplerini görür. Portal destek görevlisi tüm firmalara erişebilir. Her işlem sunucuda doğrulanır.
- FPHR Manrope, mor/turkuaz marka tokenları; mobil liste/detay; klavye odağı ve erişilebilir modal formlar.

## SenseİK bağlantısı

[Entegrasyon paketi](integrations/senseik/README.md) mevcut `/identity/me` API'siyle kullanıcı ve firma kimliğini doğrular. Bileşen, kaynak API için aktif kullanıcı kontrol yaması ve kurulum adımları birlikte teslim edilir. Gerçek SenseİK alan adları yapılandırılmadan canlı bağlantı kullanılamaz.

Giriş kodu 60 saniye geçerli ve tek kullanımlıktır; URL fragment'i hemen temizlenir. SenseİK JWT'si URL'ye veya veritabanına yazılmaz. Müşteri portal oturumu 15 dakika, destek personeli oturumu 8 saattir. Kaynak sistemdeki iptaller en geç müşteri oturum süresi sonunda yeni girişte uygulanır. Yerel personel ve firma erişim iptalleri her istekte denetlenir.

## Üretim — Docker

`.env.example` dosyasını `.env` olarak kopyalayın. Güçlü rastgele `POSTGRES_PASSWORD`, `ADMIN_EMAIL` ve en az 12 karakterlik `ADMIN_PASSWORD` belirleyin. `PUBLIC_URL` gerçek portal adresi olmalıdır. HTTPS için `COOKIE_SECURE=true` kullanın. SenseİK ayarları entegrasyon belgesindedir. Veritabanı bağlantı parolası URL'de kullanıldığından hex veya URL'de güvenli karakterlerden oluşturun.

```bash
docker compose up -d --build
docker compose ps
```

Docker demo girişlerini zorunlu olarak kapatır. İlk platform yöneticisi ortam değişkenlerinden bir kez oluşturulur; sonradan `.env` parolasını değiştirmek mevcut hesabın parolasını değiştirmez. Port `127.0.0.1:8080` üzerinde nginx gelir; API ve PostgreSQL dışarı yayınlanmaz. HTTPS sonlandıran reverse proxy bu porta bağlanmalıdır. Yerel HTTP Docker incelemesi için `PUBLIC_URL=http://localhost:8080` ve `COOKIE_SECURE=false` kullanın.

PostgreSQL ve `support-uploads` dosya volume’ları kalıcıdır. Veritabanı yedeğiyle birlikte dosya volume’unu da yedekleyin. Yerelde ekler `data/uploads` altında saklanır; `UPLOAD_DIR` ile değiştirilebilir. Migration ayrı serviste API'den önce çalışır. Hatırlatma işçisi her 30 saniyede vadesi gelen kayıtları kilitleyerek işler; benzersiz reminder bildirim anahtarı çift bildirimi önler. Web ve API aynı origin altındadır. Proxy IP başlığı nginx tarafından yeniden yazılır; API yalnız bu iç ağdaki proxy üzerinden yayınlanmalıdır. Auth hız sınırı süreç başına IP/uç bazında 30 deneme/dakikadır; mevcut tek API süreci için tasarlanmıştır.

İşçi veya API hataları `docker compose logs api worker` ile görülebilir. Loglarda mesaj/parola/JWT yer almaz; API yanıtlarında korelasyon ID bulunur. Üretimde API dokümantasyon uçları kapalıdır. SQL migration ve alınacak PostgreSQL yedekleri birlikte sürümlenmelidir; volume silen komutlar veriyi siler.

## Doğrulama

```powershell
.venv/Scripts/python -m pytest -q
npm run build --prefix frontend
npx --prefix frontend playwright install chromium
npm run test:e2e --prefix frontend
```

API testleri dosya indirme yetkisini, iç not eklerini, geçersiz/büyük dosyaları, HTML temizlemeyi, dosya kayıt hatasında geri almayı ve farklı firmayı ve aynı firmadaki başka kullanıcıyı, iç not gizliliğini, CSRF/çıkışı, sürüm çatışmasını, kapatma/yeniden açmayı, tekrar giriş kodunu, hatırlatmaları ve rol değişikliklerini doğrular. Playwright ayrı `data/e2e.db` kullanır; müşteri → admin yanıtı → hatırlatma → kapatma akışını, gerçek panodan görsel yapıştırmayı, sürüklenen dosyaları, biçimli metnin kalıcılığını, mobil taşmayı ve klavye modal davranışını kontrol eder. CI aynı komutları çalıştırır.

PostgreSQL testleri yalnız izole bir test veritabanında `TEST_DATABASE_URL` ile çalıştırılır; test fixture'ı bu veritabanının tablolarını temizler. Üretim veritabanıyla kullanmayın.

## Yapı

`backend/app`: ince API uçları, auth, iş servisleri, scoped repository ve modeller. `backend/alembic`: versiyonlu şema. `frontend/src`: müşteri/admin özellikleri ve ortak bileşenler. `integrations/senseik`: ürün bağlantısı. `deployment`: nginx ayarı.

E-posta/SMS gönderimi, SLA otomasyonu ve eski SenseİK taleplerinin aktarımı bu sürüme dahil değildir. Hatırlatmalar uygulama içinde bildirim üretir.
