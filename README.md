# Quản lý Văn bản & Công việc — Full-stack

- Mỗi tài khoản có dữ liệu văn bản/công việc/file riêng.
- Admin `NongVanHuy` xem toàn bộ và quản lý tài khoản.
- Mật khẩu mặc định: `11011998Huy@`.
- Backend kiểm tra owner_id ở API, không chỉ ẩn giao diện.

## Chạy Windows
`python -m venv .venv` → `.venv\Scripts\activate` → `pip install -r requirements.txt` → `uvicorn server:app --host 0.0.0.0 --port 8000` → mở http://localhost:8000

## Triển khai
Có Dockerfile và render.yaml để đưa lên Render. Bản production nên bật HTTPS, đặt APP_SECRET riêng, backup dữ liệu và cấu hình push VAPID.
