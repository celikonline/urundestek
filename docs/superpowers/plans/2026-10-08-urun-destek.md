# Ürün Destek Implementation Plan

> Execution: superpowers:executing-plans, bu oturumda. Kullanıcı tasarımı onayladı ve ek soru olmadan hızlı uygulama istedi.

**Goal:** Firma bazlı müşteri desteği ve platform yönetimi için çalışan Python/React ürünü.
**Architecture:** FastAPI, SQLAlchemy, versiyonlu migration; React ve API aynı origin. PostgreSQL üretim, SQLite yerel geliştirme.
**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, React 19, TypeScript, Vite.
**Spec:** ../specs/2026-10-08-urun-destek-design.md

## Global constraints
FPHR marka tokenları, Türkçe metin, sunucuda firma/rol kontrolü, UTC kayıt, müşteri API'sinde iç not yok, URL'de ürün JWT'si yok.

## Review focus
Farklı firma ID'si; aynı firmada başka kullanıcı; kapalı talebe yazma; aynı hatırlatma/giriş kodunun tekrar kullanılması; eşzamanlı sürüm çatışması.

## Tasks
- [x] 1. `backend/tests/test_portal.py`: talep açma, izolasyon, rol, kapatma, hatırlatma, giriş ve CSRF testleri.
- [x] 2. `backend/app/`: config, DB modelleri, auth, repository, servis ve API. `backend/alembic/`: migration. SQLite/PostgreSQL testleri yeşil.
- [x] 3. `frontend/src/`: müşteri/admin kabuğu, liste, konuşma, talep formu, hatırlatmalar, bildirimler, firmalar/personel. Typecheck ve build geçti.
- [x] 4. `integrations/senseik/`: launch bileşeni, server-side /identity/me doğrulaması, tek kullanımlık giriş kodu ve zorunlu aktif kullanıcı kontrol yaması. Yama kaynak depoya git apply --check ile doğrulandı; canlı bağlantı adres yapılandırmasına bağlı.
- [x] 5. Docker Compose, start.ps1, README, CI. Yerel API/UI ve PostgreSQL/nginx üretim yığını doğrulandı. 2 tarayıcı senaryosu geçti.
- [x] 6. Bağımsız incelemenin 4 bulgusu giderildi; rol düşürme ve pasif görevli regresyon testleri eklendi.

## Rulings
- Kullanıcının ek soru istememesi plan inceleme sorularının yerine doğrudan yürütme talimatıdır.
- SQLite sadece hızlı yerel çalıştırma içindir; üretim Compose PostgreSQL kullanır.
- Mevcut SenseİK /identity/me doğrulaması sayesinde Identity API'ye yeni giriş-kodu ucu eklemek gerekmez; tek kullanımlık kodu support API üretir/tüketir. Bu bir tasarım iyileştirmesidir.
- İnceleme: kaynak /me yalnız kullanıcı varlığını doğruluyordu. Normal ve impersonation dalında UserStatus.Active kontrolü zorunlu yama olarak teslim edildi.
- İnceleme: bildirim/hatırlatma listelerine güncel talep görünürlüğü uygulanır; pasif görevliye atanan talepler aktif ekibe bildirilir. Nginx IP başlığını yeniden yazar, yalnız iç ağdaki API forwarded header'a güvenir.
