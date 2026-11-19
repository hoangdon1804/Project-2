# Production checklist

Ứng dụng giữ nguyên API contract hiện tại, nhưng backend chưa đủ an toàn để public.

- [ ] Bắt buộc JWT trên mọi endpoint cần đăng nhập bằng `Authorization: Bearer`.
- [ ] Kiểm tra role và quyền sở hữu `sales_id` ở server; không tin id do client gửi.
- [ ] Đưa JWT secret vào secret manager/environment variable, thay secret hiện tại và thêm `exp`, issuer, audience.
- [ ] Kiểm tra `is_approved` khi đăng nhập và khi gọi API.
- [ ] Chỉ chạy HTTPS; cấu hình CORS theo domain, không wildcard khi có credentials.
- [ ] Thay SQLite bằng PostgreSQL/MySQL cho nhiều thiết bị; bổ sung migration, backup và index.
- [ ] Thêm rate limiting, audit log, giới hạn payload và che lỗi nhạy cảm.
- [ ] Dùng domain production trong cấu hình app, không log token/mật khẩu.
- [ ] Kiểm thử token hết hạn, request không token, tài khoản chưa duyệt và phân quyền Sales.
