# Nhật ký thay đổi Hoyo Buddy

## v1.15.6

### New Features

- (`/mimo`) Thêm hỗ trợ cho Genshin Du Lịch Mimo (sự kiện đã kết thúc từ thời điểm viếtviết).
- (`/mimo`) Đã thêm tính năng rút thưởng tự động.
- (`/challenge zzz`) Thêm hỗ trợ cho Tập Kích Nguy Cấp.
- (`/profile hsr`) Thêm Mẫu thẻ 2.
- (`/notes`) Thêm thông tin Tiến Độ Ủy Thác Treo Thưởng và Điểm Số Ridu Hàng Tuần cho ZZZZZZ

## Improvements

- (`/check-in`) Giảm các yêu cầu API điểm danh trùng lặp.

## Bug Fixes

- (`/mimo`) Sửa lỗi gửi thông báo khi không có nhiệm vụ nào được hoàn thành và không có điểm nào được nhận.
- (`/mimo`) Sửa lỗi cách xác định các vật phẩm có giá trị.
- (`/mimo`) Xử lý lỗi -510001.
- (`/mimo`) Đã khắc phục sự cố trong đó các vật phẩm có giá trị được tính làm đồ trang trí cho HSR.
- (`/mimo`) Vô hiệu hóa nút rút thăm xổ số khi đạt đến giới hạn.
- (`/challenge zzz`) Sửa lỗi icon Bangboo sai trong thẻ.
- (`/events`) Sửa lỗi tiến trình của La Hoàn Thâm Cảnh.
- (`/gacha-log view`) Đã sửa lỗi số lần quay gacha từ độ hiếm cuối cùng.
- Đã sửa lỗi logic tạo thư mục hình ảnh tĩnh.

## v1.15.5

### Tính năng mới

- (`/mimo`) Tự động hoàn thành tác vụ yêu cầu bình luận trên một bài viết.
- (`/mimo`) Tự động hoàn thành tác vụ yêu cầu theo dõi một đề mục.
- (`/mimo`) Thêm tính năng rút thưởng.
- (`/mimo`) Thêm cài đặt thông báo.
- (`/profile zzz`) Added an image setting to use Mindscape 3 arts for build cards.
- (`/profile zzz`) Thêm cài đặt hình ảnh để sử dùng ảnh Phim Ý Cảnh cho thẻ nhân vật.
- (`/profile zzz`) Thêm dử liệu nhân vật Harusama và Miyabi
- (`/search`) Ẩn mục "nội dung chưa phát hành" trong một số máy chủ.

### Cải Tiến

- (`/mimo`) Hiển thị tiến độ tác vụ cho một số tác vụ nhất định.
- (`/mimo`) Hiển thị tên các tác vụ đã hoàn thành trong thông báo.
- (`/mimo`) Cải thiện hiệu suất của các tác vụ tự động.
- (`/challenge zzz shiyu`) Cập nhật bố cục của thẻ.
- (`/challenge zzz shiyu`) Avoid fetching agent data twice.
- (`/challenge zzz shiyu`) Tranh lấy dữ liệu người đại diện hai lần.
- Hiển thị liên kết mời máy chủ Discord trong phần chân trang bị lỗi.
- Bỏ đặt trạng thái tải mục khi có lỗi.
- Thêm nhãn bật/tắt cho các nút chuyển đổi.
- Logic yêu cầu API proxy được cải thiện.
- Cải thiện logic xử lý lỗi tác vụ tự động.

### Sửa Lỗi

- (`/mimo`) Đã thêm khoảng thời gian ngủ sau khi đổi mã quà tặng phần thưởng MMimo.
- (`/mimo`) Sửa lỗi tác vụ bị thiếu trong danh sách tác vụ.
- (`/mimo`) Sửa lỗi nhiệm vụ bình luận không được hoàn thành.
- (`/mimo`) Sửa lỗi gửi thông báo khi không có nhiệm vụ nào được hoàn thành.
- (`/mimo`) Chỉ hiển thị tài khoản HoYoLAB trong phần tự động điền.
- (`/mimo`) Sửa lỗi `QuerySetError` trong các tác vụ tự động.
- (`/mimo`) Đã sửa lỗi bình luận bài viết không bị xóaa.
- (`/mimo`) Xử lý các trường hợp Mimo Du Lịch không có sẵn cho trò chơi.
- (`/profile zzz`) Sửa lỗi điểm nổi bật của chỉ số phụ không được thêm vào thẻ.
- (`/profile zzz`) Sửa lỗi người đại diện được xác định là được lưu trong bộ nhớ đệm trong khi thực tế không được lưu.
- (`/characters zzz`) Sữa lỗi đếm sai số lượng người đại diệndiện.
- (`/gacha-log upload`) Đã khắc phục sự cố khi nhập Nhật ký Gacha từ zzz.rng.moe.
- (`/redeem`) Sửa lỗi tài khoản Miyoushe được hiển thị trong tự động điền.
- (`/build genshin`) Xử lý tỷ lệ sử dụng bị thiếu đối với một số ký tự.
- (`/events`) Đã sửa lỗi các banner Bước Nhảy HSR trong tương lai được hiển thị là "chưa có sẵn".
- Thích ứng với các khóa ZenlessData mới.
- Đã khắc phục sự cố với API Hakushin.
- Nắm bắt các ngoại lệ chung trong phương thức `dm_user`.

## v1.15.4

### Tính năng mới

- (`/build genshin`) Hiển thị thông tin về sức mạnh tổng hợp của một nhân vật.
- (`/mimo`) Thêm lênh quản lý Mimo Du Lịch

### Cải Tiến

- (`/build genshin`) Cải thiện thiết kế thẻ nhân vật
- (`/notes`) Sử dụng API Lịch Sự Kiện để kiểm tra Sự kiện Vị Diện Nứt Vỡ.

### Sửa lỗi

- (`/build genshin`) Sửa một số vấn đề về UI.
- (`/events`) Sửa một số vấn đề làm cho lệnh không thể truy cập đượcđược.
- (`/gacha-log upload`) Sửa lỗi `ValidationError` với dữ liệu UIGF.
- (`/gacha-log upload`) Sửa lỗi `KeyError` với UIGF phiên bản cũ hơnhơn 3.0.
- (`/search`) Sửa các lựa chọn tự động hoàn thành trùng lặp.


## v1.15.3

Lỗi code trong phiên bản trước đã xẩy ra lỗi "nhiều yêu cầu quá, vui lòng thử lại" khi người dùng đăng nhập, vui lòng xem [bài đăng này](https://link.seria.moe/kky283) để biết thêm thông tin.

### Tính năng mới

- (`/profile zzz`) Thêm bộ chọn để chọn thuộc tính phụ mà bạn muốn tô đậm.
- (`/profile hsr`) Thêm dữ liệu thẻ Fugue và Sunday.

### Cải Tiến

- (`/redeem`) Ẩn link mã đổi bằng chính mã đó.
- (`/challenge genshin theater`, `/challenge genshin abyss`) Hiển thị nguyên tố Nhà Lữ Hành trong thẻ.
- (`/accounts`) Thêm thông báo lỗi tùy chỉnh cho lỗi "nhiều yêu cầu quá".

### Sửa lỗi

- Sửa lỗi nơi các lệnh không được dịch sang ngôn ngữ khác.
- Sửa lỗi nơi các cách thức hết thời gian chờ không được đóng đúng cách.
- Sửa API logic thử lại và logic xử lý lỗi.
- Sửa lỗi `ValueError` trong một số lệnh.
- Sửa lỗi cách thức hết thời gian chờ quá ngắn.
- Xử lý lỗi `KeyError` trong điểm cuối chuyển hướng máy chủ web.
- (`/profile`) Xử lý lỗi `EnkaAPIError` khi lấy dữ liệu từ Enka Network API.
- (`/profile`)  Xử lý lỗi Enka Network API hết thời gian chờ cổng kết nối một cách nhẹ nhàng.
- (`/profile`) Sửa lỗi `BadRequestError` khi tạo ảnh AI.
- (`/profile`) Sửa lỗi `BadRequestError` khi tải ảnh lên.

## v1.15.2 và trước đó

Previous changelogs were written in the #updates channel in our [Discord server](https://link.seria.moe/hb-dc).
