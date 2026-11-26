# FitAI Mobile

Ứng dụng di động của FitAI, viết bằng **Expo SDK 58** (React Native 0.88, TypeScript, expo-router). App chỉ gọi API backend hiện có, không có logic riêng.

## Cần có

- Node.js và npm. Không cần cài Expo CLI toàn cục, vì mọi lệnh đều chạy bằng `npx expo …`.
- Ứng dụng **Expo Go** trên điện thoại, bản hỗ trợ SDK 58 (tải từ App Store hoặc Google Play).
- Backend đang chạy bằng Docker ở thư mục gốc repo (`docker compose up -d`), mở cổng 8000.
- Điện thoại và máy Mac kết nối **cùng một mạng Wi-Fi**.

## Chạy thử

1. Lấy IP của máy Mac:

   ```bash
   ipconfig getifaddr en0
   ```

2. Tạo `mobile/.env` từ file mẫu, rồi điền IP vừa lấy (phải có `/api/v1` ở cuối):

   ```bash
   cd mobile
   cp .env.example .env
   # sửa dòng: EXPO_PUBLIC_API_URL=http://<IP-máy-Mac>:8000/api/v1
   ```

   File `.env` đã bị `.gitignore` chặn. Mọi biến `EXPO_PUBLIC_*` đều bị đóng vào bundle của app, nên chỉ đặt địa chỉ API ở đây, không bao giờ đặt khoá hay token.

3. Cài thư viện (chỉ cần lần đầu) và chạy:

   ```bash
   npm install
   npx expo start
   ```

   Nếu vừa đổi `.env`, chạy `npx expo start --clear` để Metro đọc lại.

4. Mở Expo Go trên điện thoại và đăng nhập tài khoản Expo.

5. Quét mã QR trên terminal. Trên iOS quét bằng app Camera; trên Android quét trong Expo Go.

6. Trên iOS, khi được hỏi quyền "Mạng cục bộ", chọn cho phép.

Nếu app báo không kết nối được, mở màn **"Kiểm tra kết nối máy chủ"** từ màn đăng nhập (màn này gọi `GET /health`). Có thể thử mở `http://<IP>:8000/health` bằng trình duyệt trên điện thoại. Nếu vẫn lỗi, kiểm tra tường lửa macOS và IP của máy (IP có thể đổi khi đổi mạng).

## Kiểm tra

```bash
npx tsc --noEmit    # kiểm kiểu
npx expo-doctor     # kiểm thư viện có khớp SDK không
```

Luôn cài thư viện bằng `npx expo install <tên-gói>` để có phiên bản khớp SDK 58.

## Đã có

- **Đăng nhập và đăng ký.** Phiên đăng nhập được giữ qua expo-secure-store. Token hết hạn thì app tự về màn đăng nhập.
- **Tổng quan:**
  - Cảnh báo bệnh lý về dinh dưỡng và cảnh báo chung, mỗi cảnh báo kèm dòng nguồn.
  - Thẻ hôm nay: đã ăn, mục tiêu, còn lại.
  - Thẻ tập luyện tuần này.
  - Nhận xét tuần hiện tại.
- **Ăn uống:**
  - Xem theo ngày.
  - Sửa số gam (từ 1 đến 5000, chấp nhận dấu phẩy).
  - Xoá món, có hỏi xác nhận.
  - Thêm món: tìm thực phẩm, chọn bữa, nhập số gam.
- **Tập luyện (chỉ xem):**
  - Cảnh báo bệnh lý về tập luyện và cảnh báo chung.
  - Gợi ý chương trình theo kinh nghiệm tập.
  - Thẻ "Đang tập".
  - Danh sách chương trình.

Mỗi khối dữ liệu tải riêng và có nút Thử lại. Kéo xuống để làm mới.

## Chưa có

- Hồ sơ: nhập và sửa trên web, kể cả khai báo bệnh lý.
- Chat.
- Chi tiết chương trình, ngày tập, xem video và đánh dấu hoàn thành.
- Số đo cơ thể và biểu đồ tiến độ.
- Refresh token.
- Chọn ngày theo lịch, đổi tuần ở phần nhận xét tuần, icon cho các tab.
- Test tự động và bản build phát hành (EAS).

## Giới hạn đã biết

- **Mật khẩu và token gửi đi dạng chữ thường.** App gọi backend bằng HTTP trong mạng LAN, nên chỉ dùng để thử ở nhà, không dùng trên Wi-Fi công cộng.
- **Phải đăng nhập lại sau 30 phút.** Token chỉ có hạn 30 phút và không có refresh token.
- **Kiểu dữ liệu có thể lệch với web và backend.** Các kiểu trong `src/api/types/` được chép tay từ `frontend/src/lib/` (đầu mỗi file ghi rõ nguồn). Khi web hoặc backend đổi kiểu dữ liệu, phải chép lại bằng tay.

## Cấu trúc

```
src/
  app/              # màn hình (expo-router): login, register, connection, add-meal, (tabs)/{index,meals,training}
  api/              # client.ts (fetch + Bearer + ApiError + 401), các hàm gọi API
  api/types/        # kiểu và hàm thuần chép tay từ frontend/src/lib/
  auth/             # AuthContext, lưu token
  components/       # giao diện dùng chung, ăn uống, tổng quan, tập luyện, HealthNotice
  lib/              # ngày, số gam, useLoader, nhãn trường hồ sơ
  config.ts         # đọc EXPO_PUBLIC_API_URL
```
