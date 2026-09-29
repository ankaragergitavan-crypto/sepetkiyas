# SepetKıyas

Ankara odaklı canlı market fiyat karşılaştırması.

**Kaynak:** [marketfiyati.org.tr](https://marketfiyati.org.tr) (resmi açık veri) + Getir Çarşı (konumlu).

## Marketler
A101 · Migros · Şok · BİM · Tarım Kredi · Getir Çarşı

## Özellikler
- Canlı fiyat, en ucuz → pahalı sıralama
- Ankara ilçe seçimi (Keçiören varsayılan)
- Gramaj süzgeci
- Market bazlı ayrı sepetler
- PWA (telefon / PC ana ekrana ekle)

## Çalıştırma (PC)

```bash
cd market-karsilastir
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Tarayıcı: http://127.0.0.1:8000

Telefonda (aynı Wi‑Fi): `http://<PC-IP>:8000`  
veya masaüstündeki `Telefon-Baslat.bat` / Cloudflare tüneli.

## API
- `GET /api/health`
- `GET /api/markets`
- `POST /api/search` — `{ "query": "kaşar peynir", "latitude": 39.9777, "longitude": 32.8670 }`
- `GET /api/aktuel`

## Not
Getir Büyük depo API’si giriş ister; uygulama Getir Çarşı ağını kullanır.
