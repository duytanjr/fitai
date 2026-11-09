# Nguồn số liệu các món chế biến nhập thủ công (nguồn ADMIN_MANUAL)

Ngày tra: 08/11/2026. File này gộp ghi chú nguồn của ba đợt nhập (đợt 1: `dishes.csv`; đợt 2 và 3: `dishes_all.csv`). Đây chỉ là tài liệu, script `import_admin_foods.py` không đọc file này; nguồn từng món còn nằm trong cột `source_note` của file CSV và trong database.

Tất cả số liệu là ước tính tham khảo, không phải bảng thành phần chính thức.

## 1. Quy tắc tính
- Quy đổi số trên mỗi khẩu phần về 100 g (đồ uống coi 1 ml ≈ 1 g). Năng lượng kJ chia 4,184 để ra kcal.
- Cột carb của hệ thống là glucid KHÔNG gồm xơ: carb = carbohydrate trên nhãn trừ xơ (khi nguồn có ghi xơ).
- Món có nhiều nguồn: lấy trung bình các nguồn dùng được (có đủ năng lượng, khối lượng và macro). Hai món có carb suy ra từ năng lượng (bún chả, cà phê sữa đá) đã ghi rõ trong ghi chú nguồn.
- Khẩu phần "1 tô, 1 đĩa, 1 ly" trong tên món là giả định của nhóm đồ án, không phải số của nguồn.

## 2. Đợt 1: 8 món, nguồn từ các bảng dinh dưỡng và ứng dụng công khai
| Món | Nguồn dùng | Khối lượng | Số trên 100 g |
|---|---|---|---|
| Phở bò | Roll'd (Úc), phở bò tô 738 g: rolld.com.au/?p=1335 (năng lượng, đạm, béo) và rolld.com.au/?p=3048 (carb, xơ) | 738 g | 65,5 / 2,6 / 1,2 / 9,7 |
| | FatSecret mục chung phở bò: m.fatsecret.com.sg/calories-nutrition/generic/oriental-style-beef-and-rice-noodle-soup-(vietnamese-pho-bo) và bản m.fatsecret.co.uk cùng mục | 244 g | 72,1 / 7,11 / 1,58 / 6,48 |
| | Tham khảo (không dùng để tính): Livestrong livestrong.com/article/440591-is-pho-soup-good-for-you (≈ 99 kcal/100 g); spice.alibaba.com/spice-basics/pho-noodle-soup-nutrition (≈ 44-57 kcal/100 g) | | |
| Bún bò Huế | Roll'd bún bò Huế: rolld.com.au/menu/noodle-soups/spicy-beef-bbh | 865 g | 63,6 / 3,1 / 0,7 / 11,0 |
| | Roll'd bún bò Huế: rolld.com.au/?p=3782 | 825 g | 67,4 / 2,2 / 2,1 / 8,8 |
| | Tham khảo: welling.ai/calories-nutrition-facts/bun-bo-hue (90 kcal/100 g, chỉ có năng lượng và đạm) | | |
| Cơm tấm sườn | Arise (dữ liệu người dùng ứng dụng): arise-app.com/dish/Vietnamese-Grilled-Pork-with-Broken-Rice-(Com-Tam) | ≈ 700 g suy ra | 141,0 / 7,42 / 6,71 / 12,56 |
| | Đối chiếu: en.myauris.vn/?p=87236 (527 kcal/đĩa sườn, 627 kcal/đĩa có bì, không rõ khối lượng) | | |
| Bánh mì thịt | Roll'd bánh mì heo quay: rolld.com.au/?p=3619 | 300 g | 198,1 / 13,0 / 5,9 / 20,6 |
| | CalorieKing, Roll'd bánh mì heo quay: calorieking.com/au/en/foods/f/calories-in-burgers-sandwiches-roast-pork-crackling-banh-mi-baguette/x0pqoTwlSVGh1ZHbWIQGJw | 265 g | 246,0 / 12,42 / 12,19 / 18,79 |
| Bún chả | FatSecret mục chung: fatsecret.co.nz/calories-nutrition/generic/bun-cha?frc=True (carb suy ra từ năng lượng) | 500 g | 153,0 / 7,12 / 5,29 / 19,23 |
| | Arise bún chả kèm nem rán: arise-app.com/dish/Vietnamese-Bun-Cha-with-Spring-Rolls | 490 g | 157,0 / 6,9 / 7,2 / 16,6 |
| Cơm gà | Roll'd cơm gà sả ớt: rolld.com.au/?p=3762 | 380 g | 182,4 / 8,3 / 3,9 / 25,9 |
| | Roll'd cơm gà nướng: rolld.com.au/menu/com/bbq-chicken-rice (xơ lấy từ rolld.com.au/?p=15756) | 512 g | 131,0 / 5,9 / 1,8 / 19,5 |
| Trà sữa trân châu | CalorieKing, Chatime Premium Pearl Milky Iced Tea: calorieking.com/au/en/foods/f/calories-in-teas-premium-pearl-milky-iced-tea/yYoWxaUjQ1CGkdqUUM7Yuw | 500 ml | 74,8 / 0,2 / 2,2 / 13,4 |
| | FatSecret, Gong Cha Pearl Milk Tea: mobile.fatsecret.com.sg/calories-nutrition/gong-cha/pearl-milk-tea/1-serving (protein ghi 0 g) | 425 g | 80,0 / 0,0 / 3,29 / 12,47 |
| Cà phê sữa đá | Roll'd Vietnamese iced coffee: rolld.com.au/?p=3444 (carb suy ra từ năng lượng) | 334 ml | 71,2 / 1,59 / 1,41 / 13,05 |
| | Công thức carmyy.com/wprm_print/vietnamese-coffee (200 ml nước + 2 muỗng sữa đặc, khối lượng ước đoán ≈ 220 g) | ≈ 220 g | 58,2 / 1,36 / 1,36 / 10,0 |

Sáu món trong đợt này (phở bò, bún bò Huế, bún chả, bánh mì thịt, cơm tấm sườn, trà sữa trân châu) sau đó được thêm nguồn Tu Farm vào trung bình, xem mục 5. Số trên 100 g ghi trong bảng trên là số gốc của từng nguồn, không phải số cuối cùng trong hệ thống.

## 3. Bảng Tu Farm (nguồn của đợt 2 và 3): đánh giá
Nguồn: bảng "Bảng Calo Các Món Ăn Việt Nam Phổ Biến Nhất" trên blog Tu Farm: https://www.tu-farm.com/blog/post/bang-calo-cac-mon-an-viet-nam-chi-tiet-va-chinh-xac
Trang ghi chú "nguồn tổng hợp: Viện Dinh dưỡng Quốc gia 2020-2026 và các đo lường tại phòng lab uy tín" và "biến động ±10%". Không nêu tài liệu hay phòng lab cụ thể nên đây là NGUỒN THỨ CẤP CHƯA KIỂM CHỨNG.

- Số của 43 món trong bảng chế biến tự khớp công thức 4/9/4 (kcal so với 4 đạm + 9 béo + 4 carb) trong khoảng 9%, trừ 4 món bị loại (bên dưới).
- Hai số (cơm tấm bì chả 600 kcal, cơm chiên dương châu 530 kcal) trùng với bảng của FPT Shop (fptshop.com.vn/tin-tuc/dien-may/cach-tinh-calo-trong-thuc-an-174152): nhiều khả năng bảng được chép lại từ nơi khác, không phải đo riêng.
- Số liệu tròn (macro 15, 20, 25...) và kcal gần như bằng đúng công thức 4/9/4, gợi ý kcal được tính từ macro đã làm tròn chứ không đo.
- Chỉ phở bò có ghi khối lượng (1 tô = 500 g). Các món khác ghi "1 tô, 1 phần, 1 suất, 1 ổ, 1 cái" không kèm gam; khối lượng trong tên món là GIẢ ĐỊNH của nhóm đồ án.
- Cột "Tinh bột" được coi là carbohydrate (có thể gồm xơ).
- Một ô trà sữa trân châu bị lỗi hiển thị "5-Feb" (khoảng "2-5" bị đổi thành ngày tháng), cho thấy bảng được sao chép từ bảng tính.

## 4. Đợt 2: 21 món đã nhập
Món nước 1 tô ≈ 500 g: bún riêu cua, bánh canh cua, miến gà, hủ tiếu Nam Vang, mì Quảng. Bún thịt nướng 1 suất ≈ 400 g. Cơm chiên dương châu 1 phần ≈ 400 g. Bánh mì chả lụa, bánh mì pate 1 ổ ≈ 200 g. Bánh cuốn 1 suất ≈ 200 g. Bánh bao nhân thịt, bánh giò 1 cái ≈ 150 g. Cháo gà, cháo lòng 1 tô ≈ 400 g. Xôi mặn, xôi xéo 1 đĩa ≈ 250 g. Chè đậu xanh 1 chén ≈ 250 g. Sinh tố bơ 1 ly 350 ml. Gà rán, cánh gà chiên nước mắm, khoai tây chiên: bảng ghi sẵn trên 100 g.

Hai món lấy tầm trung với nguồn khác (chỉ có kcal, nên macro nhân theo tỉ lệ của bảng Tu Farm):
- Hủ tiếu Nam Vang: bảng 520 kcal/tô; Vinmec (vinmec.com/eng/blog/how-many-calories-in-1-bowl-of-noodle-soup-en) và Pharmacity (pharmacity.vn/hu-tieu-bao-nhieu-calo.htm) khoảng 400 kcal/tô. Dùng 460 kcal.
- Mì Quảng: bảng 420 kcal/tô; MyFitnessPal qua azcuisines.com/dishes/mi-quang ghi 541 kcal/tô. Dùng 480,5 kcal.

## 5. Đợt 3: nhập toàn bộ phần còn lại của bảng Tu Farm
Đợt 3 nhập cả các món từng bị loại ở đợt 2 (bánh xèo, nem chua rán, chả giò, cơm sườn nướng, bánh tét; riêng trà sữa trân châu được gộp vào mục 5.1) kèm cảnh báo.

### 5.1 Cập nhật 6 món đợt 1 (nằm trong dishes_all.csv, chạy với --update-existing)
Thêm bảng Tu Farm làm nguồn thứ ba (hoặc thứ hai) vào trung bình, thay vì tạo bản sao cùng tên khác số.
| Món | Số cũ (kcal/100 g) | Số mới | Nguồn trong trung bình |
|---|---|---|---|
| Phở bò | 68,8 | 75,9 | Roll'd, FatSecret, Tu Farm (450 kcal/500 g) |
| Bún bò Huế | 65,5 | 80,9 | Roll'd (TB 2 bảng), Tu Farm (482 kcal/tô giả định 500 g) |
| Bún chả | 155,0 | 136,7 | FatSecret, Arise, Tu Farm (400 kcal/suất giả định 400 g) |
| Bánh mì thịt | 222,1 | 223,1 | Roll'd, CalorieKing, Tu Farm bánh mì thịt nướng (450 kcal/ổ giả định 200 g) |
| Cơm tấm sườn | 141,0 | 143,0 | Arise, Tu Farm cơm tấm sườn bì (580 kcal/phần giả định 400 g) |
| Trà sữa trân châu | 77,4 | 84,9 | Chatime, Gong Cha, Tu Farm (khoảng 400-600 kcal/ly, lấy giữa khoảng, đạm "2-5" lấy 3,5) |

### 5.2 Món chế biến mới (17 món, nằm trong dishes_all.csv)
Khối lượng trong tên món là giả định của nhóm đồ án (bảng chỉ ghi "1 tô, 1 phần, 1 suất, 1 cái"). Nem chua rán và bánh tét: bảng ghi sẵn trên 100 g.
- Hủ tiếu xào (1 đĩa ≈ 400 g), cơm gà xối mỡ, cơm gà luộc, cơm rang thập cẩm, cơm hến, cơm sườn nướng, cơm tấm bì chả (1 phần ≈ 400 g).
- Bánh xèo (1 suất ≈ 200 g), chả giò (1 cái ≈ 50 g), bánh bột lọc (5 cái ≈ 150 g), bánh flan (1 cái ≈ 120 g).
- Cháo trắng (1 tô ≈ 400 g), bánh canh ghẹ (1 tô ≈ 500 g), canh chua cá (1 tô ≈ 300 g), lẩu thái (1 suất ≈ 500 g).
- Nem chua rán, bánh tét (trên 100 g).

### 5.3 Thực phẩm cơ bản (24 món, tên có hậu tố "(Tu Farm)")
Bảng III của nguồn, số trên 100 g. Đặt tên có hậu tố để không trùng tên với bảng thành phần VN 2007 và USDA (nhiều món đã có ở đó: chuối, táo, cam, đu đủ, bơ, khoai lang, khoai tây, cà chua, dưa chuột, cà rốt...). Trạng thái sống/chín ghi "unknown" vì bảng không nêu (nhiều giá trị trùng số của thực phẩm đã nấu); chỉ cơm trắng và rau muống luộc ghi "cooked", bánh mì nguyên cám ghi "processed".

## 6. Cảnh báo và hạn chế
- Bánh tét: 408 kcal/100 g cao bất thường (món thường khoảng 200 kcal/100 g); ghi cảnh báo trong ghi chú nguồn.
- Kcal lệch hơn 15% so với đạm/béo/carb ghi cùng bảng (hệ thống gắn cờ lệch Atwater): bánh xèo (23,5%), nem chua rán (16,7%). Ba loại rau (rau muống luộc, rau bina, dưa chuột) lệch 16 đến 22% vì carb trong bảng gồm cả xơ.
- Chả giò, bánh flan, bánh bột lọc, bánh giò... có khối lượng giả định, số trên 100 g có thể lệch nhiều.
- Với nhiều thực phẩm cơ bản đã có số từ nguồn tốt hơn (VN 2007, USDA), nên ưu tiên các nguồn đó khi dùng.
- Phần lớn nguồn của đợt 1 là bảng của chuỗi nhà hàng ở Úc và dữ liệu ứng dụng đếm calo, không phải món bán ở Việt Nam; món ở mỗi quán khác nhau nên số chỉ để ước lượng.
- Cơm tấm sườn chỉ có hai nguồn, trong đó một nguồn là dữ liệu người dùng ứng dụng (độ tin cậy thấp), và chưa gồm bì, chả.
- Hủ tiếu Nam Vang và mì Quảng lấy "tầm trung" với nguồn chỉ có kcal, macro nhân theo tỉ lệ của bảng Tu Farm.
- Bảng Tu Farm đã bị đối chiếu: hai số trùng với bảng của FPT Shop, macro tròn và kcal gần bằng đúng công thức 4/9/4, nên có thể được tính chứ không đo. Nhiều thực phẩm cơ bản đã có số từ nguồn tốt hơn (bảng thành phần VN 2007, USDA): ưu tiên các nguồn đó.
