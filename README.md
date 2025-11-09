# 🧩 FastAPI MongoDB REST API

API sederhana berbasis **FastAPI + MongoDB**, dengan fitur:
- Autentikasi JWT (Login, Logout)
- Role-based access (Admin & User)
- CRUD Users (dengan foto profil)
- CRUD Products (dengan upload multiple images)
- CRUD Categories
- Pagination, filtering, dan sorting (ASC/DESC)
- Upload & serve image files
- Database MongoDB (nama: `pms`)
- Menggunakan struktur folder rapi dan scalable

---

## 📂 Struktur Folder
```
fastapi-mongo-api/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   ├── products.py
│   │   │   │   └── categories.py
│   │   │   └── api.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   └── mongodb_config.py
│   ├── models/
│   │   ├── user.py
│   │   ├── product.py
│   │   └── category.py
│   └── main.py
├── uploads/
│   ├── users/
│   └── products/
├── database.zip          # Export data MongoDB
├── requirements.txt
└── .env
```

---

## ⚙️ Instalasi & Konfigurasi

### 1️⃣ Clone Project
```bash
git clone https://github.com/yudistiragani/sharing_session_be.git
cd sharing_session_be
```

### 2️⃣ Buat Virtual Environment & Install Dependensi
```bash
python -m venv venv
source venv/bin/activate  # di Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Setup Environment Variable
Pastikan file `.env` sejajar dengan `requirements.txt`, berisi:

```ini
PROJECT_NAME=FastAPI Mongo API
API_V1_STR=/api/v1
MONGODB_URI=mongodb+srv://:@/admin
MONGODB_DB=pms
JWT_SECRET_KEY=super-secret-key-change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
UPLOAD_DIR=uploads
USER_UPLOAD_SUBDIR=users
PRODUCT_UPLOAD_SUBDIR=products
```

### 4️⃣ Jalankan Server
```bash
python main.py --no-reload
```

Server berjalan di:
👉 **http://127.0.0.1:8000**  
Swagger UI: **http://127.0.0.1:8000/docs**

---

## 🧠 Endpoint Overview

### 🔐 Auth
| Method | Endpoint | Deskripsi |
|---------|-----------|-----------|
| POST | `/api/v1/auth/login` | Login user (return JWT Token) |
| POST | `/api/v1/auth/logout` | Logout user |

### 👥 Users
| Method | Endpoint | Deskripsi |
|---------|-----------|-----------|
| GET | `/api/v1/users` | List all users (pagination, sorting, filtering) |
| GET | `/api/v1/users/{id}` | Detail user |
| GET | `/api/v1/users/me` | Profil user saat ini |
| POST | `/api/v1/users` | Tambah user baru (dengan foto profil) |
| PUT | `/api/v1/users/{id}` | Update user |
| DELETE | `/api/v1/users/{id}` | Hapus user (hapus juga foto profil) |

### 📦 Products
| Method | Endpoint | Deskripsi |
|---------|-----------|-----------|
| GET | `/api/v1/products` | List all products (pagination, filter, sorting) |
| GET | `/api/v1/products/{id}` | Detail produk |
| POST | `/api/v1/products` | Tambah produk (upload multiple image) |
| PUT | `/api/v1/products/{id}` | Update produk |
| DELETE | `/api/v1/products/{id}` | Hapus produk & gambar |
| DELETE | `/api/v1/products/{id}/images` | Hapus gambar produk tertentu |

### 🗂️ Categories
| Method | Endpoint | Deskripsi |
|---------|-----------|-----------|
| GET | `/api/v1/categories` | List kategori |
| POST | `/api/v1/categories` | Tambah kategori |
| PUT | `/api/v1/categories/{id}` | Update kategori |
| DELETE | `/api/v1/categories/{id}` | Hapus kategori |

---

## 🧰 Catatan Teknis

- Password disimpan dalam bentuk **hashed (base64 simple hash)**.  
- Upload image tersimpan di folder `uploads/` sesuai subdir.  
- Saat user/product dihapus, file gambar juga ikut dihapus.  
- Pagination default: 10 item per halaman.  
- Sorting: gunakan query `?sort_by=nama_field&order=asc|desc`.  
- Filter: gunakan query `?status=active` atau field lain.

---

## 📦 Database
Nama database: **`pms`**  
Sudah diekspor ke file `database.zip` (letakkan di root project).  
Cukup restore ke MongoDB Atlas atau lokal dengan:
```bash
mongorestore --archive=database.zip --gzip --nsInclude=pms.*
```

---

## 👤 Role Access
| Role | Hak Akses |
|------|------------|
| **Admin** | CRUD semua data (user, produk, kategori) |
| **User** | Hanya akses `/users/me` dan lihat produk |

---
