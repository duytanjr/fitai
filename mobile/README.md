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

3. Cài thư viện (lần đầu, hoặc khi `package.json` đổi) và chạy:

   ```bash
   npm install --legacy-peer-deps
   npx expo start
   ```

   **Phải có `--legacy-peer-deps`** (xem mục "Cài thư viện"). Nếu vừa đổi `.env` hoặc vừa cài thêm gói, chạy `npx expo start --clear` để Metro đọc lại.

4. Mở Expo Go trên điện thoại và đăng nhập tài khoản Expo.

5. Quét mã QR trên terminal. Trên iOS quét bằng app Camera; trên Android quét trong Expo Go.

6. Trên iOS, khi được hỏi quyền "Mạng cục bộ", chọn cho phép.

Nếu app báo không kết nối được, mở màn **"Kiểm tra kết nối máy chủ"** từ màn đăng nhập (màn này gọi `GET /health`). Có thể thử mở `http://<IP>:8000/health` bằng trình duyệt trên điện thoại. Nếu vẫn lỗi, kiểm tra tường lửa macOS và IP của máy (IP có thể đổi khi đổi mạng).

## Kiểm tra

```bash
npx tsc --noEmit    # kiểm kiểu
npx expo-doctor     # kiểm thư viện có khớp SDK không (hiện 19/20, xem "Giới hạn đã biết")
```

## Cài thư viện

Luôn cài gói mới bằng `npx expo install` (để có phiên bản khớp SDK 58), kèm cờ `--legacy-peer-deps` cho npm:

```bash
npx expo install <tên-gói> -- --legacy-peer-deps
```

**Lý do:** expo-router kéo theo một phụ thuộc tuỳ chọn là `react-dom@19.3.1`, gói này đòi `react ^19.3.1`, trong khi SDK 58 ghim `react 19.3.0`. Không có cờ thì `npm install` và `npx expo install` dừng với lỗi `ERESOLVE`. Cờ này chỉ bỏ qua các phụ thuộc ngang hàng tuỳ chọn, không đổi phiên bản `react`. App không dùng `react-dom` hay các gói tuỳ chọn bị bỏ qua (reanimated, gesture-handler…), và `npx expo export` cho iOS lẫn Android vẫn chạy được.

Gói đã thêm sau bộ khung ban đầu (đều cài bằng lệnh trên):

| Gói | Dùng cho |
|---|---|
| `react-native-svg` | Biểu đồ calo theo ngày và biểu đồ cân nặng ở Tổng quan |
| `@react-native-community/datetimepicker` | Lịch chọn ngày ở tab Ăn uống |
| `@expo/vector-icons` | Icon cho các tab |
| `expo-font` | Phụ thuộc bắt buộc của `@expo/vector-icons` (thiếu thì expo-doctor báo lỗi) |

`datetimepicker` và `expo-font` có thêm plugin trong `app.json`. Cả bốn gói đều có sẵn trong Expo Go SDK 58, không cần bản build riêng.

## Đã có

- **Đăng nhập và đăng ký.** Phiên đăng nhập được giữ qua expo-secure-store. Token hết hạn thì app tự về màn đăng nhập.
- **Thiết lập hồ sơ (3 bước, như onboarding của web):** tự mở sau khi đăng ký trên app, và mở từ các link "Hoàn tất hồ sơ". Bước Sức khỏe giữ đúng quy tắc bệnh lý của web; không chạm phần bệnh thì không gửi trường bệnh lý nào.
- **Tổng quan:**
  - Thẻ chào: tên, ngày, calo đã ghi hôm nay hoặc nút "Ghi bữa ăn".
  - Cảnh báo bệnh lý về dinh dưỡng và cảnh báo chung, mỗi cảnh báo kèm dòng nguồn.
  - Thẻ hôm nay: đã ăn, mục tiêu, còn lại.
  - Calo theo ngày (7/30/90 ngày): biểu đồ cột kèm đường mục tiêu, chạm cột để xem số, luôn có số liệu dạng chữ.
  - Cân nặng: biểu đồ đường, thay đổi trong khoảng, nút "Ghi cân nặng".
  - Báo cáo tuần: mặc định tuần trước, đổi tuần bằng ‹ ›.
  - Thẻ tập luyện tuần này.
- **Cân nặng:** ghi cân nặng (vòng eo tuỳ chọn) theo ngày, ghi lại cùng ngày là cập nhật; sửa, xoá có hỏi xác nhận.
- **Ăn uống:**
  - Xem theo ngày: ‹ ›, "Về hôm nay", hoặc chạm vào ngày để mở lịch. **Lịch không cho chọn sau hôm nay** (giờ Việt Nam), giống nút ›.
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

- Trang xem và sửa hồ sơ đã đủ (web cũng chưa có): khi hồ sơ đã đủ thông tin, link "Hoàn tất hồ sơ" không hiện.
- Chat (đợt sau).
- Nút Dừng chương trình (dừng mà không chuyển sang chương trình khác), vì backend và web chưa có. Hiện chỉ đổi được bằng cách chuyển chương trình hoặc tập lại.
- Refresh token.
- Trang quản trị: chủ ý không làm trên app (công cụ dùng trên máy tính).
- Test tự động và bản build phát hành (EAS).

## Giới hạn đã biết

- **Mật khẩu và token gửi đi dạng chữ thường.** App gọi backend bằng HTTP trong mạng LAN, nên chỉ dùng để thử ở nhà, không dùng trên Wi-Fi công cộng.
- **Phải đăng nhập lại sau 30 phút.** Token chỉ có hạn 30 phút và không có refresh token.
- **Ảnh xem trước gửi IP tới Google.** App tải ảnh xem trước video trực tiếp từ `i.ytimg.com` (giống web), nên khi mở màn ngày tập, IP của điện thoại được gửi tới Google. Ảnh chỉ được tải khi link video hợp lệ.
- **expo-doctor báo 19/20.** Check lỗi là phiên bản gói: Expo đã ra bản vá mới (`expo` 58.1.x, `expo-router` 58.0.33), app chưa nâng. Khi rảnh, nâng bằng `npx expo install --check -- --legacy-peer-deps`, rồi chạy lại các lệnh kiểm tra.
- **Kiểu dữ liệu có thể lệch với web và backend.** Các kiểu trong `src/api/types/` được chép tay từ `frontend/src/lib/` (đầu mỗi file ghi rõ nguồn). Khi web hoặc backend đổi kiểu dữ liệu, phải chép lại bằng tay.

## Cấu trúc

```
src/
  app/              # màn hình (expo-router): login, register, connection, onboarding, add-meal, body-metrics,
                    #   (tabs)/{index,meals,training}, program/[slug], program/[slug]/day/[n]
  api/              # client.ts (fetch + Bearer + ApiError + 401), các hàm gọi API
  api/types/        # kiểu và hàm thuần chép tay từ frontend/src/lib/
  auth/             # AuthContext, lưu token
  components/       # giao diện dùng chung, ăn uống (kèm lịch chọn ngày), tổng quan (kèm biểu đồ), tập luyện, hồ sơ
  lib/              # hàm thuần (ngày, số gam, onboarding, số đo, biểu đồ), useLoader, useWriteAction, useScreenReload
  config.ts         # đọc EXPO_PUBLIC_API_URL
```
