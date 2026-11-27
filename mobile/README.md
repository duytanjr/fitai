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
npx expo-doctor     # kiểm thư viện có khớp SDK không (hiện 19/20, xem "Giới hạn đã biết")
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
- **Tập luyện:**
  - Cảnh báo bệnh lý về tập luyện và cảnh báo chung, cùng hộp lưu ý an toàn, trên mọi màn tập luyện. Người có bệnh không bị chặn.
  - Gợi ý chương trình theo kinh nghiệm tập.
  - Thẻ "Đang tập" có nút "Tập ngày n".
  - Danh sách chương trình. Bấm vào một thẻ để mở chi tiết chương trình và danh sách ngày (✓ đánh dấu ngày đã xong).
  - Ngày tập: các bài kèm ảnh xem trước và nút "Xem video". Video chỉ mở (bằng Linking) khi link qua `isSafeYoutubeUrl`.
  - Bắt đầu chương trình. "Chuyển sang chương trình này" và "Tập lại chương trình" có hỏi xác nhận.
  - Đánh dấu hoàn thành một ngày và bỏ đánh dấu.
  - Sau mỗi thao tác ghi, kể cả khi lỗi, app tải lại trạng thái thật trước khi mở khoá nút.

Mỗi khối dữ liệu tải riêng và có nút Thử lại. Kéo xuống để làm mới.

## Chưa có

- Hồ sơ: nhập và sửa trên web, kể cả khai báo bệnh lý.
- Chat.
- Nút Dừng chương trình (dừng mà không chuyển sang chương trình khác), vì backend và web chưa có. Hiện chỉ đổi được bằng cách chuyển chương trình hoặc tập lại.
- Số đo cơ thể và biểu đồ tiến độ.
- Refresh token.
- Chọn ngày theo lịch, đổi tuần ở phần nhận xét tuần, icon cho các tab.
- Test tự động và bản build phát hành (EAS).

## Giới hạn đã biết

- **Mật khẩu và token gửi đi dạng chữ thường.** App gọi backend bằng HTTP trong mạng LAN, nên chỉ dùng để thử ở nhà, không dùng trên Wi-Fi công cộng.
- **Phải đăng nhập lại sau 30 phút.** Token chỉ có hạn 30 phút và không có refresh token.
- **Ảnh xem trước gửi IP tới Google.** App tải ảnh xem trước video trực tiếp từ `i.ytimg.com` (giống web), nên khi mở màn ngày tập, IP của điện thoại được gửi tới Google. Ảnh chỉ được tải khi link video hợp lệ.
- **expo-doctor báo 19/20.** Check lỗi là phiên bản gói: Expo đã ra bản vá mới (`expo` 58.1.x, `expo-router` 58.0.33), app chưa nâng. Khi rảnh, nâng bằng `npx expo install --check`.
- **Kiểu dữ liệu có thể lệch với web và backend.** Các kiểu trong `src/api/types/` được chép tay từ `frontend/src/lib/` (đầu mỗi file ghi rõ nguồn). Khi web hoặc backend đổi kiểu dữ liệu, phải chép lại bằng tay.

## Cấu trúc

```
src/
  app/              # màn hình (expo-router): login, register, connection, add-meal, (tabs)/{index,meals,training},
                    #   program/[slug] (chi tiết chương trình), program/[slug]/day/[n] (ngày tập)
  api/              # client.ts (fetch + Bearer + ApiError + 401), các hàm gọi API
  api/types/        # kiểu và hàm thuần chép tay từ frontend/src/lib/
  auth/             # AuthContext, lưu token
  components/       # giao diện dùng chung, ăn uống, tổng quan, tập luyện, HealthNotice
  lib/              # ngày, số gam, useLoader, useWriteAction, useScreenReload, nhãn trường hồ sơ
  config.ts         # đọc EXPO_PUBLIC_API_URL
```
