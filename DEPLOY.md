# SepetKıyas — kart gerekmeden yayın

Hugging Face Docker Spaces artık PRO istiyor.

## Render.com (ücretsiz deneme — çoğu hesapta kart yok)

1. https://github.com/signup — ücretsiz GitHub
2. Bu klasörü GitHub’a yükle
3. https://render.com → Sign up with GitHub
4. **New → Web Service** → bu repo
5. Ayarlar:
   - Runtime: Python
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
6. Create Web Service → link: `https://sepetkiyas.onrender.com`

Not: Render free uyku moduna girebilir (15 dk işlem yoksa); ilk açılış ~30 sn sürebilir.
