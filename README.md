# Quản lý Văn bản & Công việc — bản cập nhật

## Cập nhật có bảo toàn dữ liệu
- Bản cập nhật không xóa database, bảng người dùng, văn bản, công việc hay đăng ký thông báo.
- Khi khởi động, máy chủ chỉ bổ sung các cột `result`, `completed_at` và bảng `reports` nếu còn thiếu.
- Không thay `DATABASE_URL`, `APP_SECRET`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL` hoặc `REMINDER_SECRET` đang có trên Render.
- Giữ nguyên PostgreSQL hiện tại. Không xóa database và không tạo database mới.

## Chức năng
1. Quản lý văn bản: giữ nguyên chức năng cũ; bổ sung lưu kết quả thực hiện.
2. CV thực hiện: thêm/sửa/xóa công việc, thời gian, trạng thái và kết quả.
3. Báo cáo kết quả: tạo/sửa/xóa báo cáo; lọc theo ngày bắt đầu và ngày kết thúc tùy chỉnh.
4. Hạn văn bản: ngày nhập dạng YYYY-MM-DD được tính đến 23:59:59 giờ Việt Nam.
5. Thông báo: giữ Push API và Service Worker; thêm API kiểm tra trạng thái thông báo.

## Triển khai Render
1. Sao lưu PostgreSQL trước khi triển khai.
2. Thay mã nguồn GitHub bằng toàn bộ nội dung ZIP này (không xóa các biến môi trường hiện có).
3. Không thay `DATABASE_URL` hoặc xóa PostgreSQL.
4. Deploy Web Service. Kiểm tra `/healthz`.
5. Để gửi nhắc khi đóng ứng dụng, cần có Cron Job chạy `python reminder_worker.py` định kỳ mỗi phút, dùng cùng các biến môi trường với Web Service. Nếu đang có Cron Job cũ gọi `/api/internal/run-reminders`, có thể giữ nguyên và không tạo job trùng.
6. Trong ứng dụng, vào Cài đặt nhắc hạn → Bật thông báo khi đóng ứng dụng; cấp quyền thông báo trên trình duyệt/điện thoại.

## Lưu ý
- Trình duyệt phải hỗ trợ Push API và trang web phải chạy HTTPS (Render cung cấp HTTPS).
- Nếu VAPID chưa được cấu hình hoặc thiết bị chưa đăng ký Push, thông báo khi đóng ứng dụng sẽ không hoạt động. Thông báo nổi/âm thanh/giọng đọc trong trang chỉ hoạt động khi ứng dụng đang mở.
- Tài khoản Quản trị tiếp tục chỉ quản lý tài khoản; dữ liệu văn bản, công việc và báo cáo vẫn là riêng tư của từng tài khoản người dùng.

## Cập nhật quyền sử dụng tài khoản quản trị

Tài khoản `NongVanHuy` (vai trò Quản trị) hiện có thể quản lý văn bản, CV thực hiện,
báo cáo kết quả và cài đặt/thông báo đối với dữ liệu do chính tài khoản này tạo.
Các truy vấn đều giới hạn theo `owner_id` của tài khoản đang đăng nhập, vì vậy
quản trị không xem hoặc sửa dữ liệu văn bản/công việc/báo cáo của tài khoản khác.
Quyền quản lý danh sách tài khoản vẫn chỉ dành cho Quản trị.

Khi cập nhật trên Render, giữ nguyên PostgreSQL và biến `DATABASE_URL`.
