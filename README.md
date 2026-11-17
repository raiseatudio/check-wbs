# check-wbs

GitHub Action đọc file WBS (CSV hoặc TSV) và GDD (CSV, TSV, TXT, MD, DOCX hoặc RTF), đối chiếu với bộ luật trong [`SKILL.md`](SKILL.md), rồi gửi báo cáo vào Discord.

## Cách đặt file

Action không cố định tên cột. Chỉ cần phân biệt được đâu là WBS, đâu là GDD:

- Đặt file trong thư mục `wbs/` hoặc `gdd/` (đúng tên thư mục), hoặc
- Đặt token trong tên file, tách bằng ký tự không phải chữ: `WBS_export.csv`, `my-gdd.docx`, `GDD.txt`.

WBS chỉ nhận `.csv` và `.tsv`. GDD nhận thêm `.txt`, `.text`, `.md`, `.markdown`, `.docx`, `.rtf`.

`mywbs.csv` không được nhận vì `wbs` không đứng thành một token. File nằm trong thư mục `my-wbs/` cũng không được nhận nếu tên file không có token.

File khớp cả WBS và GDD (ví dụ `wbs-gdd.csv`, hoặc file trong `wbs/` mà tên có `gdd`) bị bỏ qua và được liệt kê trong tin nhắn Discord.

Excel (`.xlsx`, `.xls`, `.xlsm`, `.ods`), PDF và Word cũ (`.doc`) không được gửi cho model. Tin nhắn nhắc export WBS sang CSV hoặc TSV, và GDD sang DOCX hoặc TXT.

Mỗi lần chạy đọc toàn bộ file trên commit của pull request, không chỉ phần vừa sửa. File dài hơn 120.000 ký tự bị cắt; phần gửi cho model ghi rõ số dòng gốc.

## Bộ luật

Sửa [`SKILL.md`](SKILL.md) khi đổi tiêu chí. Prompt của Action chỉ yêu cầu bám file này và trả lời tiếng Việt. Các ngưỡng trong `SKILL.md` đang là khung, cần điền trước khi xem kết luận là chấm điểm chính thức.

## Secret và model

Trong repo trên GitHub:

1. Vào Settings → Secrets and variables → Actions → New repository secret.
2. Tên: `GEMINI_API_KEY`. Giá trị là auth key tạo trong Google AI Studio. Không dán key vào file trong repo.
3. Tên: `DEEPSEEK_API_KEY`. Key DeepSeek. Dùng khi Gemini không gọi được, hoặc khi không có key Gemini. Không dán key vào file trong repo.
4. Tên: `DISCORD_WEBHOOK_URL`. Giá trị là URL webhook của kênh Discord. Không dán URL vào file trong repo.
5. Tùy chọn: biến `GEMINI_MODEL`, mặc định `gemini-3.5-flash`. Biến `DEEPSEEK_MODEL`, mặc định `deepseek-chat`.

Action gọi Gemini trước. Nếu Gemini lỗi, Action gọi DeepSeek tại `https://api.deepseek.com/chat/completions` và ghi một dòng ở đầu báo cáo Discord. Cần ít nhất một trong hai key.

## Khi nào chạy

Workflow được kích hoạt trên pull request (`opened`, `synchronize`, `reopened`) khi đổi file WBS, file GDD, `SKILL.md`, script, hoặc chính workflow. Có thể chạy tay bằng workflow dispatch.

Test và review chỉ chạy khi commit mới nhất trên nhánh có chuỗi `[check]` dính liền với một đoạn ký tự, không có khoảng trắng ở giữa. Ví dụ message `update wbs [check]xxxxxxxx`. Commit không có chuỗi này thì workflow dừng, không gọi test, không gọi Gemini, không gửi Discord.

Job review cần `DISCORD_WEBHOOK_URL` và ít nhất một trong `GEMINI_API_KEY` hoặc `DEEPSEEK_API_KEY`. Pull request từ fork không có các secret này nên bước review được bỏ qua.

## Đọc kết quả

Sau khi check xong, báo cáo được gửi vào kênh Discord của webhook. Tin dài được cắt thành nhiều tin nhắn. Mỗi tin có link pull request hoặc link lần chạy Action.

Bản sao của báo cáo cũng nằm ở phần Summary của lần chạy Action.

Khi commit thiếu hẳn WBS hoặc GDD, Action gửi hướng dẫn cách đặt file vào Discord và không gọi Gemini.
