# Hoyo Buddy Changelog

## v1.15.3

Lỗi code trong phiên bản trước đã xẩy ra lỗi "nhiều yêu cầu quá, vui lòng thử lại" khi người dùng đăng nhập, vui lòng xem [bài đăng này](https://link.seria.moe/kky283) để biết thêm thông tin.

### Tính năng mới

- (`/profile zzz`) Thêm bộ chọn để chọn thuộc tính phụ mà bạn muốn tô đậm.
- (`/profile hsr`) Thêm dữ liệu thẻ Fugue và Sunday.

### Cải Tiến

- (`/redeem`) Ẩn link mã đổi bằng chính mã đó.
- (`/challenge genshin theater`, `/challenge genshin abyss`) Hiển thị nguyên tố Nhà Lữ Hành trong thẻ.
- (`/accounts`) Thêm thông báo lỗi tùy chỉnh cho lỗi "nhiều yêu cầu quá".

### Sữa lỗi

- Sữa lỗi nơi các lệnh không được dịch sang ngôn ngữ khác.
- Sữa lỗi nơi các cách thức hết thời gian chờ không được đóng đúng cách.
- Sữa API logic thử lại và logic xử lý lỗi.
- Sữa lỗi `ValueError` trong một số lệnh.
- Sữa lỗi cách thức hết thời gian chờ quá ngắn.
- Xử lý lỗi `KeyError` trong điểm cuối chuyển hướng máy chủ web.
- (`/profile`) Xử lý lỗi `EnkaAPIError` khi lấy dữ liệu từ Enka Network API.
- (`/profile`)  Xử lý lỗi Enka Network API hết thời gian chờ cổng kết nối một cách nhẹ nhàng.
- (`/profile`) Sữa lỗi `BadRequestError` khi tạo ảnh AI.
- (`/profile`) Sữa lỗi `BadRequestError` khi tải ảnh lên.