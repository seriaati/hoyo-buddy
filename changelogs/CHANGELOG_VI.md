# Nhật ký thay đổi Hoyo Buddy

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
