# Quản lý Văn bản & Công việc — PWA v3

Ứng dụng PWA dùng trên **điện thoại và máy tính**. Mỗi tài khoản Người dùng có một hệ thống dữ liệu riêng: văn bản, lịch công việc, báo cáo và cài đặt thông báo. **Admin chỉ quản lý tài khoản**, không xem/sửa dữ liệu văn bản, công việc hoặc báo cáo của người dùng.

## Thay đổi v3
- Không hiển thị gợi ý tài khoản/mật khẩu trên giao diện đăng nhập.
- Admin chỉ có màn hình quản trị tài khoản.
- Không lưu file công văn, file công việc hoặc file báo cáo. Chỉ lưu thông tin/danh sách văn bản và công việc.
- Nhắc hạn bằng tiếng Việt.
- PWA + Service Worker + Web Push: sau khi người dùng cấp quyền, thông báo chữ có thể đến khi cửa sổ App đã đóng.
- Thông báo khi App đóng dùng âm thanh do hệ điều hành/trình duyệt điều khiển; không thể ép trình duyệt phát một file âm thanh tùy ý khi App đã đóng.
- Đọc bằng giọng nói tiếng Việt (`speechSynthesis`) hoạt động khi App đang mở; khi App đóng, Web Push không được phép chạy TTS tùy ý.
- Có nút cài App trên thiết bị.
- Có API lưu Push Subscription theo từng tài khoản.
- Có `reminder_worker.py` để chạy nhắc hạn định kỳ.

## Tài khoản Admin
- Username: `NongVanHuy`
- Mật khẩu khởi tạo: `11011998Huy@`

Không hiển thị các thông tin này trên màn hình đăng nhập. Nên đổi mật khẩu trong phiên bản quản trị tài khoản nâng cao sau này.

## Dữ liệu
- PostgreSQL: users, docs, tasks, settings, push_subscriptions, notification_log.
- Không có bảng lưu file công văn/báo cáo trong phiên bản này.
- Backend luôn lọc `owner_id` theo tài khoản Người dùng.
- Admin bị chặn ở các API docs/tasks/settings/push.

## Web Push
Cần 3 biến môi trường trên Web Service và Cron Job:
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_EMAIL` (ví dụ `mailto:tenban@example.com`)

Tạo cặp khóa bằng:
```text
python generate_vapid.py
```
Sau đó đưa kết quả vào Environment Variables của Render. **Không đưa VAPID_PRIVATE_KEY vào GitHub.**

## Nhắc hạn khi App đã đóng
Web Push cần một tiến trình server chạy định kỳ để kiểm tra hạn và gửi push. Render Free Web Service có thể bị spin down, vì vậy không dùng `setInterval` trên trình duyệt làm cơ chế đảm bảo. `render.yaml` có sẵn Cron Job chạy mỗi phút; Cron Job hiện là compute trả phí trên Render. Nếu chưa muốn trả phí, có thể chạy `reminder_worker.py` từ một scheduler bên ngoài, nhưng thời gian chạy có thể có độ trễ.

## Render
- Web Service: Docker.
- PostgreSQL: dùng `DATABASE_URL`.
- Cron Job: `python reminder_worker.py`, mỗi phút.
- VAPID keys phải được khai báo riêng trên Web Service và Cron Job.

## Giao diện
- 🟨 Sắp đến hạn.
- 🟥 Quá hạn.
- 🟩 Đã hoàn thành.
- 🔔 Biểu ngữ cảnh báo trong App.
- 🔊 Âm thanh khi App đang mở.
- 🗣️ Lời nhắc tiếng Việt khi App đang mở.
- 📱/💻 Web Push khi App đã đóng và thiết bị/trình duyệt đã cấp quyền.
