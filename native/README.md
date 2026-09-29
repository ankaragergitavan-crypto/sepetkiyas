# Native kabuk (Capacitor) — ileride mağaza build'i için

Bu klasör/yapı, mevcut PWA arayüzünü Android ve iOS uygulamasına sarmak içindir.

## Önkoşullar

- Node.js 20+
- Android Studio (Android)
- Xcode (iOS, yalnızca macOS)

## Kurulum (ileride)

```bash
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npx cap init SepetKiyas tr.sepetkiyas.app --web-dir frontend
npx cap add android
npx cap add ios
```

API adresini production'da `capacitor.config.json` içindeki `server.url` ile güncelleyin
(ör. `https://api.sizin-domain.com`). Geliştirmede bilgisayarınızın LAN IP'sini kullanın.

```bash
npx cap sync
npx cap open android
npx cap open ios
```

Şimdilik **PWA yeterlidir**: Chrome / Safari / Edge üzerinden “Ana ekrana ekle” ile
telefon ve PC'de uygulama gibi açılır.
