# SalesMobileApp

Ứng dụng .NET MAUI/XAML/MVVM dành riêng cho vai trò Sales. JWT được lưu bằng `SecureStorage`.

## Windows

Chạy backend tại `0.0.0.0:8000`, sau đó:

```powershell
cd frontend-mobileApp
dotnet restore
dotnet build -f net10.0-windows10.0.19041.0
dotnet run -f net10.0-windows10.0.19041.0
```

## Android Emulator

Android Emulator dùng `http://10.0.2.2:8000/`. Điện thoại thật dùng IP LAN của máy chạy backend và cần mở firewall port 8000. Production dùng URL HTTPS. Các URL cấu hình trong `Resources/Raw/backend-settings.json` hoặc nhập trực tiếp ở màn hình đăng nhập.

```powershell
dotnet restore
dotnet build -f net10.0-android
dotnet build -t:Run -f net10.0-android
```

## Luồng Sales

Đăng nhập → xem ca/zone → ghi nhận hóa đơn → xem lịch sử → cập nhật hồ sơ. Role khác `sales` bị từ chối; không có route Admin.

## Kiểm thử

```powershell
dotnet restore
dotnet build
dotnet test
```
