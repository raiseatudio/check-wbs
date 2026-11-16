# check-wbs

GitHub Action đọc file WBS và GDD (CSV hoặc TSV export từ Google Sheet), đối chiếu với bộ luật trong [`SKILL.md`](SKILL.md), rồi ghi một nhận xét trên pull request.

## Cách đặt file

Action không cố định tên cột. Chỉ cần phân biệt được đâu là WBS, đâu là GDD:

- Đặt file trong thư mục `wbs/` hoặc `gdd/` (đúng tên thư mục), hoặc
- Đặt token trong tên file, tách bằng ký tự không phải chữ: `WBS_export.csv`, `my-gdd.tsv`.

`mywbs.csv` không được nhận vì `wbs` không đứng thành một token. File nằm trong thư mục `my-wbs/` cũng không được nhận nếu tên file không có token.

File khớp cả WBS và GDD (ví dụ `wbs-gdd.csv`, hoặc file trong `wbs/` mà tên có `gdd`) bị bỏ qua và được liệt kê trong comment.

Excel (`.xlsx`, `.xls`, `.xlsm`, `.ods`) không được gửi cho model. Comment nhắc export CSV hoặc TSV từ Google Sheet.

Mỗi lần chạy đọc toàn bộ file trên commit của pull request, không chỉ phần vừa sửa. File dài hơn 120.000 ký tự bị cắt; phần gửi cho model ghi rõ số dòng gốc.

## Bộ luật

Sửa [`SKILL.md`](SKILL.md) khi đổi tiêu chí. Prompt của Action chỉ yêu cầu bám file này và trả lời tiếng Việt. Các ngưỡng trong `SKILL.md` đang là khung, cần điền trước khi xem kết luận là chấm điểm chính thức.

## Secret và model

Trong repo trên GitHub:

1. Vào Settings → Secrets and variables → Actions → New repository secret.
2. Tên: `OPENAI_API_KEY`. Giá trị là API key của OpenAI.
3. Tùy chọn: thêm biến `OPENAI_MODEL`. Nếu bỏ trống, Action dùng `gpt-4.1`.

Nội dung bảng được gửi tới OpenAI.

## Khi nào chạy

Workflow chạy trên pull request (`opened`, `synchronize`, `reopened`) khi đổi CSV, TSV, file bảng tính, `SKILL.md`, script, hoặc chính workflow. Có thể chạy tay bằng workflow dispatch.

Job test kiểm tra cách phân loại đường dẫn. Job review chỉ gọi OpenAI khi secret có giá trị. Pull request từ fork không có secret này nên bước review được bỏ qua.

## Đọc kết quả

Trên pull request, tìm comment có dấu `<!-- check-wbs -->`. Lần push sau cập nhật cùng comment đó, không tạo comment mới.

Nếu chạy tay mà không gắn với pull request, báo cáo nằm ở phần Summary của lần chạy Action.

Khi commit thiếu hẳn WBS hoặc GDD, Action chỉ comment hướng dẫn cách đặt file và không gọi API.
