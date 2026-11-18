# check-wbs

GitHub Action kiểm tra WBS và GDD từ file trong repo hoặc từ URL Google Sheet, rồi gửi báo cáo vào Discord.

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

Sửa [`skill_check_wbs.md`](skill_check_wbs.md) khi đổi tiêu chí đối chiếu WBS với GDD. Sửa [`skill_check_gdd.md`](skill_check_gdd.md) khi đổi cách chấm chính tả, dấu câu và thông tin của GDD. Prompt của Action chỉ yêu cầu bám đúng file luật của lệnh đang chạy và trả lời tiếng Việt. Các ngưỡng trong `skill_check_wbs.md` đang là khung, cần điền trước khi xem kết luận là chấm điểm chính thức.

## Secret và model

Trong repo trên GitHub:

1. Vào Settings → Secrets and variables → Actions → New repository secret.
2. Tên: `GEMINI_API_KEY`. Giá trị là auth key tạo trong Google AI Studio. Không dán key vào file trong repo.
3. Tên: `DISCORD_WEBHOOK_URL`. Giá trị là URL webhook của kênh Discord. Không dán URL vào file trong repo.
4. Khi check bằng URL Google Sheet, thêm ba secret: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`. Cách lấy refresh token nằm ở mục bên dưới. Không dán client JSON hay token vào file trong repo.
5. Tùy chọn: biến `GEMINI_MODEL`. Nếu có, model này được thử trước, rồi mới đến danh sách mặc định.

Action gọi Gemini theo thứ tự từ cao xuống thấp. Model gặp lỗi quá tải, hết quota tạm thời, hoặc không tồn tại thì chuyển sang model kế tiếp:

1. `gemini-3.5-flash`
2. `gemini-3.5-flash-lite`
3. `gemini-3.1-flash-lite`
4. `gemini-2.5-flash`
5. `gemini-2.5-flash-lite`

Báo cáo Discord ghi model đã dùng khi không phải model đầu tiên.

## Đăng nhập Google một lần

Action không mở trang đăng nhập. Tài khoản Google đăng nhập trên máy của bạn, rồi refresh token được lưu vào secret.

1. Trên Google Cloud, bật Google Sheets API và Google Docs API.
2. Màn hình consent để **Internal** nếu dùng Google Workspace, hoặc **Production**. Để **Testing** thì refresh token hết hạn sau 7 ngày.
3. Tạo OAuth client loại **Desktop app**.
4. Trên máy local, xuất `GOOGLE_OAUTH_CLIENT_ID` và `GOOGLE_OAUTH_CLIENT_SECRET`, rồi chạy `python scripts/google_login.py`.
5. Đăng nhập tài khoản có quyền xem Sheet và Doc. Script in refresh token. Dán token vào secret `GOOGLE_OAUTH_REFRESH_TOKEN`.
6. Scope là quyền đọc Google Sheet và Google Doc. Không commit client JSON, client secret, hay refresh token. Token cũ chỉ có quyền Sheet thì chạy lại script sau khi thêm scope Doc trong mục Data Access.

Token của app Internal hoặc Production còn dùng được khi Action chạy ít nhất một lần trong 6 tháng. Thu hồi quyền trên tài khoản Google hoặc tạo quá nhiều refresh token sẽ làm token cũ chết. Khi đó chạy lại `scripts/google_login.py`.

## Khi nào chạy

Workflow chạy khi push lên nhánh, khi pull request được mở, cập nhật, mở lại, hoặc khi bấm chạy tay sau khi file workflow đã có trên nhánh mặc định. Gate đọc message của commit mới nhất. Commit không có lệnh thì dừng, không gọi test, không gọi Gemini, không gửi Discord.

- `[check]` đứng riêng: đọc file WBS và GDD trong repo, đối chiếu theo `skill_check_wbs.md`.
- `[check-wbs]` kèm hai URL có nhãn: tải Google Sheet của WBS và Google Sheet hoặc Google Doc của GDD, đối chiếu theo `skill_check_wbs.md`.
- `[check-gdd]` kèm một URL có nhãn `gdd:`: tải Google Sheet hoặc Google Doc của GDD, chấm chính tả, dấu câu và thông tin theo `skill_check_gdd.md`.

`[check-wbs]` không bị hiểu thành `[check]`. Một commit có cả hai lệnh thì chạy cả hai và gửi hai báo cáo. Nhãn nhận `wbs:` / `gdd:` hoặc `wbs=` / `gdd=`. URL `wbs` phải là Google Sheet. URL `gdd` được là Google Sheet hoặc Google Doc. `gid` trong query hoặc `#gid=` chọn đúng tab Sheet. `tab=` chọn đúng tab Doc. Không có `gid` hoặc `tab` thì lấy mọi tab.

```text
[check-wbs] wbs: https://docs.google.com/spreadsheets/d/.../edit#gid=0 gdd: https://docs.google.com/document/d/.../edit
[check-gdd] gdd: https://docs.google.com/document/d/.../edit
```

Thiếu URL hoặc nhãn sai thì Discord nhận hướng dẫn và job thất bại.

Job review cần `GEMINI_API_KEY` và `DISCORD_WEBHOOK_URL`. Lệnh đọc Google Sheet cần thêm ba secret OAuth. Pull request từ fork không có các secret này nên bước review được bỏ qua.

## Đọc kết quả

Sau khi check xong, báo cáo được gửi vào kênh Discord của webhook. Dòng đầu là `[Check WBS - GameID]` hoặc `[Check GDD - GameID]`, rồi đến nội dung review. GameID lấy từ nhãn `game:` trong commit, từ mã `gsc` kèm số trong tên file hoặc tên Google Sheet, hoặc từ cụm trong ngoặc vuông như `[gsc00002 - FODB]`. Tin dài được cắt thành nhiều tin nhắn. Token không xuất hiện trong báo cáo.

Bản sao của báo cáo cũng nằm ở phần Summary của lần chạy Action.

Khi commit thiếu hẳn WBS hoặc GDD, Action gửi hướng dẫn cách đặt file vào Discord và không gọi Gemini.
