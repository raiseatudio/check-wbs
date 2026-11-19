# Kiểm tra GDD

Tài liệu này là bộ luật duy nhất để review nội dung GDD lấy từ Google Sheet. Sửa file này khi đội muốn đổi tiêu chí. Không cần sửa code của GitHub Action.

## Cách đọc

Nội dung được gửi là các ô của Google Sheet, đã ghép thành CSV. Mỗi tab là một mục. Không giả định tên cột.

- Dòng header là dòng chứa tên cột, không phải lúc nào cũng là dòng đầu. Phía trên có thể là tên game hoặc link.
- Dòng 1 là dòng đầu của nội dung được gửi. Khi nêu một ô trong báo cáo, chỉ dùng khuôn `File [GDD-tênproject-dòng xx]`. Không ghi id spreadsheet, tên tab, hay `File <id>/GDD, dòng N`. Tên cột, nếu đọc được từ header, để trong phần nội dung.
- Trích đúng cụm chữ trong ô. Không bịa ô, câu, hoặc số liệu không có trong nội dung được gửi.
- Nếu một tab ghi chú đã bị cắt ký tự, chỉ kết luận trên phần còn đọc được và ghi rõ phần sau chưa được xem.
- Ô trống hoàn toàn thì bỏ qua, trừ khi cột đó đang mô tả nội dung cần có mà các dòng xung quanh đã có chữ.

## Chính tả

Đọc chữ trong từng ô như câu tiếng Việt.

- Từ sai chính tả, thiếu dấu, sai dấu, hoặc sai hòa hợp phụ âm cuối thì ghi là lỗi.
- Hoa thường sai ở đầu câu hoặc ở tên riêng thì ghi là lỗi.
- Giữ nguyên thuật ngữ tiếng Anh cố ý: tên class, tên API, tên file, tên nút trong game, và từ viết tắt của dự án. Không bắt các từ đó phải có dấu tiếng Việt.
- Không sửa văn phong chỉ vì câu có thể viết hay hơn. Chỉ ghi khi chữ sai.

## Dấu câu

- Câu hoàn chỉnh trong ô thiếu dấu kết (`.` `?` `!` hoặc `...`) thì ghi là lỗi.
- Dấu phẩy, dấu chấm, dấu hỏi, dấu chấm than dính vào chữ phía sau, hoặc có khoảng trắng phía trước dấu câu, thì ghi là lỗi.
- Liệt kê trong một ô dùng dấu phẩy hoặc dấu chấm phẩy cho đều. Trộn kiểu không đọc được thì ghi là lỗi.
- Ô chỉ có một nhãn ngắn, tên màn, hoặc một từ thì không bắt buộc dấu kết.

## Thông tin

- Ô đang mô tả luật chơi, số liệu, phần thưởng, hoặc điều kiện mà nội dung là `TBD`, `TODO`, `xxx`, `???`, `...`, hoặc chỉ có khoảng trắng thì ghi là thông tin chưa có.
- Cùng một tên tính năng, tên màn, hoặc con số xuất hiện nhiều lần trong sheet mà viết khác nhau hoặc mâu thuẫn nhau thì ghi rõ hai chỗ.
- Số liệu không cùng đơn vị mà không ghi đơn vị (giây với phút, xu với gem) thì ghi là thiếu thông tin.
- Không bịa giá trị đúng để thay vào ô trống. Chỉ nói ô nào cần người viết GDD điền.

## Khuôn báo cáo

Viết bằng tiếng Việt, theo đúng năm mục sau.

Mỗi lỗi hoặc việc sửa là một dòng, bắt đầu  đúng khuôn:

`File [GDD-tênproject-dòng 12] nội dung.`

- `tênproject` là mã project ghi ở đầu prompt, ví dụ `gsc02`. Không thay bằng id spreadsheet hay tên tab.
- `dòng` là số dòng trong nội dung được gửi. Dòng 1 là dòng đầu.
- Phần sau ngoặc trích cụm chữ sai, tên cột nếu đọc được từ header, và mô tả lỗi.

Ví dụ: `File [GDD-gsc02-dòng 12] cột Luật chơi: cụm "nguoi choi" thiếu dấu.`

### Kết luận

Một đoạn ngắn: GDD đọc được hay không, và có cần sửa trước khi dùng làm nguồn cho WBS hay không.

### Chính tả

Danh sách lỗi chính tả. Không có lỗi thì ghi "Không thấy lỗi chính tả trong phần đã đọc."

### Dấu câu

Danh sách lỗi dấu câu. Không có lỗi thì ghi "Không thấy lỗi dấu câu trong phần đã đọc."

### Thông tin

Danh sách chỗ thiếu thông tin hoặc mâu thuẫn. Không có thì ghi "Không thấy thông tin thiếu hoặc mâu thuẫn trong phần đã đọc."

### Danh sách sửa

Mỗi dòng là một việc sửa được, cùng khuôn `File [GDD-tênproject-dòng xx]`: cột, chữ hiện tại, và chữ hoặc thông tin cần điền. Không có việc sửa thì ghi "Không có mục cần sửa."
