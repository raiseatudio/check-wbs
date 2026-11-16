# Kiểm tra WBS

Tài liệu này là bộ luật duy nhất để review WBS đối chiếu với GDD. Sửa file này khi đội muốn đổi tiêu chí. Không cần sửa code của GitHub Action.

## Cách đọc bảng

File CSV hoặc TSV không có schema cố định. Cột do Google Sheet export quyết định.

- Dòng header là dòng chứa tên cột, không phải lúc nào cũng là dòng đầu file. Bảng có thể có vài dòng tiêu đề phía trên (tên template, link). Nếu không chắc dòng nào là header, nêu giả định rồi mới kết luận.
- Đọc tên cột đúng như header. Không đổi tên cột và không giả định một cột tồn tại nếu header không có.
- Một dòng là task khi có tên việc và đó là việc phải bàn giao. Dòng đầu mục (phase, nhóm) chỉ gom các task con: thường chỉ có mã và tên, các cột việc để trống, và có dòng con bên dưới. Đầu mục không phải task. Mã dạng chữ (A, B) hoặc số La Mã (I, II) có thể là đầu mục hoặc task; phân biệt bằng cột việc và việc có dòng con hay không.
- Khi trích dẫn một dòng, ghi tên file và số dòng trong file (dòng 1 là dòng đầu tiên của file, kể cả header). Nếu suy ra được cột mã hoặc ID, ghi thêm giá trị đó.
- Không bịa dòng, số liệu, hoặc cột không có trong nội dung được gửi.
- Nếu một file ghi chú đã bị cắt ký tự, chỉ kết luận trên phần còn đọc được và ghi rõ phần sau chưa được xem.

## Tiêu chí

Mục Definition of Done là luật đã chốt. Các mục còn lại là khung. Ngưỡng ghi "chưa chốt" là chỗ đội cần điền trước khi dùng làm luật thật. Khi ngưỡng vẫn là "chưa chốt", hãy nhận xét theo mục đó nhưng ghi rằng mục này chưa đủ luật để chấm đạt hay không đạt.

### Độ phủ GDD

Mỗi hạng mục phạm vi trong GDD cần có việc tương ứng trong WBS. Hạng mục GDD không thấy việc nào bao phủ thì liệt kê là thiếu.

Ngưỡng: chưa chốt. Đội ghi cách nhận ra một hạng mục GDD, ví dụ tên cột và mức độ chi tiết.

### Task đủ nhỏ

Một task lá nên giao được cho một người trong một khoảng thời gian ngắn.

Ngưỡng: chưa chốt. Đội ghi số ngày hoặc giờ tối đa của một task lá.

### Ước lượng

Task lá cần có ước lượng ở cột mà header cho thấy là effort, giờ, ngày, hoặc điểm.

Ngưỡng: chưa chốt. Đội ghi cột nào là ước lượng và khi nào được phép để trống.

### Phụ thuộc

Task có thứ tự bắt buộc phải chỉ ra việc đi trước, nếu bảng có cột phụ thuộc hoặc quan hệ cha con.

Ngưỡng: chưa chốt. Đội ghi cột phụ thuộc và quy tắc task cha.

### Người phụ trách

Task lá cần một người hoặc một vai phụ trách, nếu bảng có cột owner, assignee, hoặc role.

Ngưỡng: chưa chốt. Đội ghi cột người phụ trách và việc có bắt buộc hay không.

### Trùng lặp

Hai task lá không được mô tả cùng một việc đã có trong GDD, trừ khi bảng ghi rõ chúng khác phạm vi.

Ngưỡng: chưa chốt. Đội ghi cách phân biệt việc trùng.

### Task mơ hồ

Tên task phải nói được việc bàn giao, không chỉ một từ chung như "làm", "hỗ trợ", "khác", "TBD".

Ngưỡng: chưa chốt. Đội ghi danh sách từ cấm hoặc ví dụ tên không đạt.

### Definition of Done

Mỗi task phải có Definition of Done để xác định rõ output. Cột thường có header `Definition of Done`. Nếu header dùng tên khác nhưng cùng nghĩa (DoD, DOD, tiêu chí hoàn thành), dùng cột đó.

Luật này chỉ áp dụng cho task. Dòng đầu mục không bắt buộc DOD.

DOD đạt khi:

- Ô không trống.
- Nêu output quan sát được: cái được tạo ra, hành vi đúng, dữ liệu đúng, hoặc điều kiện để coi task là xong.
- Mỗi ý kiểm được. Không chỉ lặp lại tên task.

DOD không đạt khi ô trống, hoặc nội dung không nói output là gì. Coi là chưa rõ nếu chỉ ghi "xong", "done", "hoàn thành", "TBD", "làm xong", hoặc một cụm chung không mô tả sản phẩm bàn giao.

Ngưỡng: đã chốt. Áp dụng cho mọi task, kể cả task đang để trạng thái chưa làm.

## Khuôn báo cáo

Trả lời bằng tiếng Việt, dùng đúng các mục sau. Không thêm mục khác.

### Kết luận

Một trong ba giá trị: hợp lý, cần chỉnh, thiếu dữ liệu. Một câu nêu lý do chính.

Dùng "thiếu dữ liệu" khi bảng bị cắt, thiếu cột để áp tiêu chí, hoặc không đọc được header.

### Đối chiếu GDD sang WBS

Liệt kê hạng mục GDD chưa có việc tương ứng trong WBS. Mỗi ý gồm file GDD, số dòng hoặc mã, và việc còn thiếu. Nếu không thấy lỗ hổng, ghi "Không thấy hạng mục GDD nào thiếu việc."

### Lỗi cấu trúc WBS

Liệt kê task không đạt các tiêu chí ở trên. Mỗi ý gồm file WBS, số dòng hoặc mã, tiêu chí, và mô tả lỗi. Nếu không có, ghi "Không thấy lỗi cấu trúc."

### Danh sách sửa

Mỗi mục là một việc cần sửa: file, dòng hoặc mã, đề xuất sửa cụ thể. Nếu không cần sửa, ghi "Không có mục cần sửa."
