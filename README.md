# QUẢN LÝ VĂN BẢN CÁ NHÂN

Ứng dụng web/PWA cá nhân, dùng trên máy tính và điện thoại.

## Chức năng
- Quản lý văn bản với các trường: TT tự động, Ký hiệu, Trích yếu, Hạn, Trạng thái (Đã thực hiện/Chưa thực hiện), Kết quả.
- Thêm, sửa, xóa, tìm kiếm và lọc văn bản.
- Thống kê nhanh tổng số, đã thực hiện, chưa thực hiện, quá hạn.
- Cài đặt nhắc trước hạn; thông báo đẩy khi cửa sổ ứng dụng đóng (cần trình duyệt/hệ điều hành hỗ trợ và đã cấp quyền).
- Âm thanh và đọc tiếng Việt khi ứng dụng đang mở.
- Logo ứng dụng theo hình người dùng cung cấp; chân trang NVHuy 0356191555.
- Dữ liệu lưu trong PostgreSQL khi có DATABASE_URL; hỗ trợ SQLite khi chạy cục bộ.

## Triển khai Render
1. Đẩy toàn bộ nội dung thư mục này lên GitHub.
2. Tạo Web Service từ repository bằng Docker.
3. Gắn PostgreSQL và đặt `DATABASE_URL`.
4. Đặt `APP_SECRET` bằng chuỗi bí mật dài, riêng tư.
5. Đặt `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL` để bật Web Push.
6. Tạo Cron Job chạy `python reminder_worker.py` mỗi phút, dùng cùng `DATABASE_URL`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL`.
7. Dùng HTTPS, mở ứng dụng, đăng nhập tài khoản cá nhân đã có, vào Cài đặt nhắc hạn và cấp quyền thông báo trên từng thiết bị.

## Lưu ý
- Cập nhật schema tự động thêm cột `result`, không xóa dữ liệu văn bản hiện có.
- Ứng dụng không lưu file đính kèm.
- Trình duyệt không bảo đảm phát giọng đọc TTS sau khi đóng hoàn toàn; thông báo đẩy do hệ điều hành hiển thị.
- Tài khoản cá nhân cũ được giữ để tiếp tục đăng nhập; không còn giao diện tạo/quản lý nhiều tài khoản.
