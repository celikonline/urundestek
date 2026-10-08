# SenseİK doğrudan bağlantısı

Mevcut SenseİK kullanıcı doğrulama ucu `GET /api/v1/identity/me` kullanılır. Support API kullanıcı/firma bilgisini bu güvenilir sunucuya gönderdiği bearer token ile doğrular; tarayıcıdan gelen firma ID'sini kabul etmez.

**Zorunlu önkoşul:** Kaynak SenseİK sürümünde `/identity/me` pasif/kilitli kullanıcının henüz süresi dolmamış JWT'sini reddetmelidir. İncelenen sürüm yalnız kullanıcının varlığını kontrol ediyor. Bu nedenle paket içindeki `active-user.patch` uygulanıp Identity API yeniden derlenmelidir. Yama hem normal hem impersonation dalında `UserStatus.Active` kontrolü ekler. Bu koruma zaten kaynakta varsa tekrar uygulanmaz.

```powershell
git -C C:/path/to/senseik apply --check C:/path/to/urundestek/integrations/senseik/active-user.patch
git -C C:/path/to/senseik apply C:/path/to/urundestek/integrations/senseik/active-user.patch
```

1. `SupportPortalButton.tsx` dosyasını SenseİK `web/src/components/support-portal-button.tsx` olarak kopyalayın.
2. `web/src/pages/support.tsx` içindeki mevcut `SupportPage` başlığının yanına `<SupportPortalButton />` ekleyin ve bileşeni import edin.
3. SenseİK frontend ortamına `VITE_SUPPORT_PORTAL_URL=https://destek.example.com` ekleyin ve yeniden derleyin.
4. Destek API ortamında `SENSEIK_API_URL=https://senseik-api.example.com/api`, `SENSEIK_WEB_ORIGIN=https://senseik.example.com`, `PUBLIC_URL=https://destek.example.com`, `COOKIE_SECURE=true` tanımlayın.
5. SenseİK'te Destek sayfasını açıp butonu kullanın. Aynı firma içindeki yalnız `announcements.support_tickets.manage` izni firma yöneticisi görünümü sağlar. SenseİK rolü portal destek personeli yetkisi vermez.

Token yalnız Authorization başlığında support API'ye ve doğrulama için SenseİK API'ye gönderilir. Token URL'ye yazılmaz veya support DB'de tutulmaz. Portal kodu 60 saniyelik, hash'lenmiş ve atomik tek kullanımlıktır; URL fragment'i girişte hemen temizlenir. Portal müşteri oturumu 15 dakika sürer. Süre sonunda SenseİK'teki bağlantıdan tekrar açılır; kaynak sistemdeki kullanıcı iptalleri yeni girişte doğrulanır, mevcut portal oturumuna en geç 15 dakika içinde yansır.

Bu bileşen mevcut yerel SenseİK deposunu değiştirmeden ayrı teslim edilir; canlı adresler henüz verilmediği için gerçek SenseİK oturumuyla entegrasyon doğrulanmadı. Kaynak API yanıtlarıyla otomatik sözleşme testleri support deposunda çalışır. Mevcut SenseİK destek kayıtları yeni portala otomatik aktarılmaz.
