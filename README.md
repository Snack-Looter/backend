# KopQuest Backend

Backend API untuk **KopQuest** — platform gamifikasi untuk *Player* (kasir/pengurus muda koperasi desa/KopDes) dengan target demografis **Gen Alpha & Gen Z**, dibangun dengan Django + Django REST Framework. Backend ini menyediakan autentikasi, sistem misi & level (gamifikasi), katalog produk, pencatatan transaksi, serta chatbot berbasis AI (Gemini).

## Daftar Isi

- [Arsitektur & Teknologi](#arsitektur--teknologi)
- [Struktur Proyek](#struktur-proyek)
- [Panduan Instalasi](#panduan-instalasi)
- [Menjalankan Aplikasi](#menjalankan-aplikasi)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)

## Arsitektur & Teknologi

| Layer | Teknologi |
|---|---|
| Bahasa & Framework | Python 3.12, Django 5.0, Django REST Framework 3.15 |
| Autentikasi | JWT via `djangorestframework-simplejwt` |
| Database | PostgreSQL (di-hosting di [Neon](https://neon.tech)) |
| AI / LLM | Google Gemini API (chatbot) + Random Forest & TOPSIS (`scikit-learn`, `pandas`, `numpy`) untuk mesin rekomendasi misi |
| CORS | `django-cors-headers` |
| Server produksi | Gunicorn |
| Containerization | Docker |
| CI/CD | GitHub Actions → Google Cloud Run |

**Alur data singkat:** aplikasi Next.js (frontend) memanggil REST API di backend ini. Data disimpan di satu database Postgres yang dipisah menjadi dua schema logis:

- `kopquest` — entitas gamifikasi: `role`, `level`, `mission`, `battle_pass`, dsb.
- `kopdes` — entitas bisnis koperasi: `product`, `transaction`, `transaction_detail`, dsb.

Kedua schema tetap bisa saling ber-*foreign key* karena berada di database yang sama; pemetaan schema per tabel diatur lewat `db_table` di masing-masing model Django.

### Modul aplikasi (`apps/`)

| App | Tanggung jawab |
|---|---|
| `accounts` | User & Player (ekstensi gamifikasi 1:1 dari User), autentikasi (register/login/JWT), profil, data wilayah (provinsi/kota) & koperasi |
| `gamification` | Role, Level, Mission, Battle Pass, serta mesin AI penentu prioritas produk misi (`product_targeting_engine.py`) |
| `catalog` | Data produk koperasi |
| `transactions` | Pencatatan transaksi kasir & validasi transaksi via kode referral misi |
| `chatbot` | Endpoint chat yang diteruskan ke Gemini API |
| `core` | App utilitas/dasar bersama |

## Struktur Proyek

```
backend/
├── apps/
│   ├── accounts/       # User, auth, wilayah, koperasi
│   ├── catalog/        # Produk
│   ├── chatbot/        # Integrasi Gemini
│   ├── core/           # Utilitas bersama
│   ├── gamification/   # Role, Level, Mission, Battle Pass, AI engine
│   └── transactions/   # Transaksi & validasi referral
├── config/
│   ├── settings.py     # Konfigurasi Django (env-driven)
│   ├── urls.py         # Root URL routing
│   ├── asgi.py / wsgi.py
├── manage.py
├── requirements.txt
├── Dockerfile
└── .github/workflows/deploy.yml   # CI/CD ke Cloud Run
```

## Panduan Instalasi

### Prasyarat

- Python 3.12+
- PostgreSQL (lokal, atau gunakan connection string Neon)
- pip / virtualenv

### 1. Clone repository

```bash
git clone <url-repo-ini>
cd backend
```

### 2. Buat & aktifkan virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi environment variables

Buat file `.env` di root folder `backend/` dengan isi berikut:

```env
DEBUG=True
SECRET_KEY=ganti-dengan-secret-key-anda
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:password@localhost:5432/kopquest_db
FRONTEND_ORIGIN=http://localhost:3000
GEMINI_API_KEY=isi-dengan-api-key-gemini-anda
GEMINI_MODEL=gemini-3.1-flash-lite
```

| Variabel | Keterangan |
|---|---|
| `DEBUG` | `True` untuk development, `False` untuk production |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Daftar host yang diizinkan, dipisah koma |
| `DATABASE_URL` | Connection string PostgreSQL (mendukung format Neon) |
| `FRONTEND_ORIGIN` | Origin frontend yang diizinkan CORS |
| `GEMINI_API_KEY` | API key Google Gemini untuk fitur chatbot |
| `GEMINI_MODEL` | (opsional) nama model Gemini, default `gemini-3.1-flash-lite` |

### 5. Jalankan migrasi database

```bash
python manage.py migrate
```

### 6. (Opsional) Buat superuser untuk akses Django Admin

```bash
python manage.py createsuperuser
```

## Menjalankan Aplikasi

### Development

```bash
python manage.py runserver
```

API akan berjalan di `http://localhost:8000/`, dan Django Admin di `http://localhost:8000/admin/`.

### Menggunakan Docker

```bash
docker build -t kopquest-backend .
docker run --env-file .env -p 8080:8080 kopquest-backend
```

Container menjalankan Gunicorn di port `8080` (lihat `Dockerfile`).

## API Endpoints

Base path API: `/api/`

| Prefix | App | Contoh endpoint |
|---|---|---|
| `/api/auth/` | accounts | `register/`, `login/`, `login/refresh/`, `logout/`, `profile/`, `change-password/`, `provinces/`, `cities/<id>/koperasi/` |
| `/api/` | gamification | `roles/`, `roles/<id>/summary/`, `missions/generate/`, `missions/<id>/verify/`, `progress/battle-pass/` |
| `/api/` | catalog | `products/`, `products/<id>/` |
| `/api/` | transactions | `transactions/`, `transactions/validate-referral/` |
| `/api/chat/` | chatbot | `/` (kirim pesan ke Gemini) |

Autentikasi endpoint yang membutuhkan login menggunakan header:

```
Authorization: Bearer <access_token>
```

## Deployment

Push ke branch `development` akan otomatis men-*trigger* GitHub Actions (`.github/workflows/deploy.yml`) yang:

1. Build Docker image.
2. Push image ke Google Artifact Registry.
3. Deploy ke **Google Cloud Run** (region `asia-southeast2`) menggunakan Workload Identity Federation (tanpa service account key).

Environment variables production (`SECRET_KEY`, `DATABASE_URL`, dll.) dikelola lewat GitHub Secrets.

## AI Acknowledgement

Beberapa bagian pengembangan KopQuest dibantu dengan tools AI, dengan penggunaan terbatas pada:

- **Generative image AI** — untuk membuat 3 desain maskot (aset visual) yang digunakan sebagai kebutuhan konten di aplikasi.
- **AI coding assistant** — untuk membantu proses debugging error, penulisan dokumentasi (termasuk README ini), dan eksplorasi kode.

Logika bisnis, arsitektur, dan keputusan desain produk tetap dikerjakan dan divalidasi oleh tim pengembang.