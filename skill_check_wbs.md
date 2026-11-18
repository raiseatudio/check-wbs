# Kiểm tra WBS

Tài liệu này là bộ luật duy nhất để review WBS đối chiếu với GDD. Sửa file này khi đội muốn đổi tiêu chí. Không cần sửa code của GitHub Action.

## Cách đọc file

WBS là bảng CSV hoặc TSV, không có schema cố định. Cột do Google Sheet export quyết định. GDD có thể là bảng CSV/TSV hoặc văn bản TXT, MD, DOCX, RTF. Không giả định GDD có cột.

- Với WBS, dòng header là dòng chứa tên cột, không phải lúc nào cũng là dòng đầu file. Bảng có thể có vài dòng tiêu đề phía trên (tên game, link). Nếu không chắc dòng nào là header, nêu giả định rồi mới kết luận.
- WBS mẫu của dự án có header: `STT`, `TASK TITLE`, `ASSIGNEE`, `START DATE`, `END DATE`, `ESTIMATE TIME (Hour)`, `ACTUAL TIME (Hour)`, `STATUS`, `BUILD`, `Definition of Done`, `NOTE`. `STT` có thể trùng, nhận task bằng `TASK TITLE`. `BUILD` là mốc `1st Build`, `Full Build` hoặc `FT + Opt`. `STATUS` là `DROP` thì task đã bỏ khỏi phạm vi còn lại.
- Đọc tên cột đúng như header. Không đổi tên cột và không giả định một cột tồn tại nếu header không có.
- Với GDD dạng văn bản, đọc theo đoạn và dòng. Trích dẫn tên file, số dòng, và câu hoặc mục trong tài liệu.
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

- tên task phải thể hiện rõ output hoặc thông tin trong cột DOD phải thể hiện rõ output.
- Nêu output quan sát được: cái được tạo ra, hành vi đúng, dữ liệu đúng, hoặc điều kiện để coi task là xong.
- Mỗi ý kiểm được. Không chỉ lặp lại tên task.

DOD không đạt khi ô trống, hoặc nội dung không nói output là gì. Coi là chưa rõ nếu chỉ ghi "xong", "done", "hoàn thành", "TBD", "làm xong", hoặc một cụm chung không mô tả sản phẩm bàn giao.

Ngưỡng: đã chốt. Áp dụng cho mọi task, kể cả task đang để trạng thái chưa làm.

## Tính năng cần có

Mỗi mục dưới đây là một task cần có trong WBS, viết theo cùng format: tên tính năng, rồi các ý output. DOD của task phải phủ các ý đó. Thiếu task, thiếu ý, hoặc DOD không nói được output thì ghi vào lỗi cấu trúc và danh sách sửa. Dòng phase và dòng nhóm không nằm trong danh sách này.

### Tính năng Create WBS

- danh sách task chia nhỏ cho dự án
- xác định DoD cho từng task

### Tính năng Clone Project

- file mẫu chưa ghi output; không suy diễn DOD, vẫn bắt thiếu DOD nếu ô trống

### Tính năng Setup Project

- đối với WBS làm từ đầu:
    + dựng scenes: loading, main
    + add components resize canvas
- đối với WBS cho project reskin/clone từ 1 game khác
    + nhóm asset cũ (images, fonts, spines) sang thư mục Old
    + sửa tên scene, script
    + remove các phần không còn liên quan
    + chuyển đổi giữa landscape và portrait (nếu có)

### Tính năng Game Network & Data Parser 

- GameNetwork đăng ký đủ packet 
- parse payload server thành DataStore

### Tính năng BE Contract Integration 

- map đủ Command ID theo tài liệu Contract BE
- request và response đúng kiểu dữ liệu tiền, tỉ lệ, ID
- map Error Codes từ BE ra đúng Toast hoặc Dialog
- log request/response để đối soát DEV/STG

### Tính năng Core Game Loop 

- state chuyển INIT, BETTING, PLAYING, RESULT/POWERMODE
- event giữa Controller và View không leak state

### Tính năng Betting Logic 

- gửi request Bet, trừ pending wallet đúng số tiền
- chặn cược khi số dư ví nhỏ hơn bet value
- chặn spam click

### Tính năng Setup build iframe 

- setup game lên config build, sẵn sàng build game

### Tính năng Logic resize resolution 

- game resize khớp các resolution
- không mất UI ở các tỉ lệ màn hình

### Tính năng LoadingUI 

- layout đúng Logo và background art game mới
- progress bar từ 0% đến 100%
- tự chuyển sang Main.scene khi nạp xong và socket thành công

### Tính năng Background Layer 

- ráp các layer background tĩnh
- scale và widget vừa trên các tỉ lệ màn hình

### Tính năng CommonUI 

- hiển thị ID ván, tình trạng mạng, số dư ví
- số dư tự cập nhật khi cược, thắng, hoặc server push ví

### Tính năng BetUI 

- tăng giảm cược
- lưu BetAmount khi chọn mức cược

### Tính năng Start Button / Cashout Button 

- Start mở tương tác ở BettingState, khóa khi bắt đầu chơi
- chặn click liên tục và phát SFX click hoặc cược
- layout nút Cash out kèm label tiền thắng tạm tính

### Tính năng Jackpot & Bonus 

- hiển thị số tiền jackpot và bonus hiện có
- tự cập nhật khi server push

### Tính năng AutoPlay UI

- layout popup Auto Play
- thanh slider, nút Confirm, Clear, và ButtonStopAuto

### Tính năng PowerMode UI

- layout popup PowerMode
- toggle TogglePowerMode
- popup ConfirmPowerMode
- popup PowerModeResult

### Tính năng Promotion UI 

- tag số lượt Free Bet còn lại nằm trên nút cược

### Tính năng PopupPromotion 

- popup đúng 2 template text newPromotion/resetPromotion
- nhãn đếm số lượt free plays còn lại (labelRemainPromo) 

### Tính năng Promotion Flow Logic 

- khóa chuyển bet khi có promotion, hiện đúng số lượt promotion
- offline claim: vào game thì hiện popup
- online claim: xong ván hiện tại mới hiện popup
- bấm Confirm thì cược không trừ ví, khóa nút tăng giảm
- hết lượt thì mở khóa nút cược, quay về ví thật, lưu tag vào Bet History
- expired: hiện toast và nút Start về normal

### Tính năng PopupSetting

- bật tắt BGM và SFX độc lập
- HelpInfo, Bet History, Jackpot History, Exit mở đúng popup
- ẩn nút Exit trên Iframe

### Tính năng PopupHistory (must have)

- lịch sử cược phân trang và xem chi tiết, nút xóa lịch sử cược
- bấm một dòng xem được ô đã mở, tiền cược, tiền thắng

### Tính năng PopupJackpotHistory 

- danh sách lịch sử jackpot phân trang theo API

### Tính năng PopupHelpInfo (must have)

- đủ các trang luật chơi

### Tính năng Dialog (must have)

- dialog lỗi hệ thống: mất kết nối, force exit
- nút bấm có callback

### Tính năng Toast 

- toast đúng trạng thái mất mạng, cược lỗi

### Tính năng AutoPlay Logic

- nhận số ô mở ngẫu nhiên từ popup và tự chơi, không cần click
- chạy đúng theo logic của 1 lượt chơi
- ButtonStopAuto dừng auto ngay
- lưu lại thông tin auto, load khi mở lên lần đầu

### Tính năng PowerMode Logic 

- tính năng Powermode theo mô tả từ GDD
- có hiển thị thắng/thua rõ ràng
- tổng kết thông tin Powermode để hiển thị ở PowerModeResult
- PopupPowerModeResult hiện đúng tổng tiền thắng khi kết thúc hoặc bấm Stop

### Tính năng Reconnect & Resume Logic (must have)

- F5 hoặc reload khôi phục ván dở: render lại trạng thái game hiện tại theo data từ server
- ẩn tab hơn 60 giây rồi quay lại không kẹt game, tự đồng bộ session từ server
- ván kết thúc lúc mất mạng thì reconnect nhảy về màn Result

### Tính năng AFK/Idle

- không thao tác đến giây 40 thì toast cảnh báo nhấp nháy, kèm đếm ngược 10 giây ở giây 50 đến 60
- người chơi thao tác lại thì hủy cảnh báo và reset timer
- nội dung toast và thời gian khớp giữa client và server

### Tính năng BO Integration (must have)

- REST API BO đúng auth token, URL param và môi trường DEV/STG/PROD
- phân trang, format ngày giờ, tiền tệ, tag Promotion
- bấm dòng lịch sử cược mở đúng chi tiết ván
- có Loading và empty state "Không có dữ liệu"
- lỗi mạng hoặc timeout 4 giây thì tắt loading, không treo popup, vẫn đóng được popup

### Tính năng Gameplay Tutorial 

- hướng dẫn đủ và đúng cách chơi
- vào lại tutorial trong Help Info

### Tính năng AutoMode Tutorial 

- hướng dẫn đủ và đúng cách chơi automode
- vào lại tutorial trong Auto Popup

### Tính năng Exit Game & Lifecycle Cleanup (must have)

- thoát về Portal hoặc đóng game thì dừng tween và hủy các hàm đếm thời gian
- chuyển màn không crash

### Tính năng Bonus & Jackpot Presentation 

- Jackpot Spine chạy mượt
- số chạy tăng dần đúng tiền thắng
- có nút Skip hoặc tự đóng sau timeout

### Tính năng Win Result Popup (must have)

- Win Spine chạy mượt
- số chạy tăng dần đúng tiền thắng
- có nút Skip hoặc tự đóng sau timeout

### Tính năng Apply SFXs (must have)

- đủ BGM và SFX
- mute và unmute đúng cài đặt

### Tính năng Multi-Platform Build Setup (must have)

- Iframe 
- WebApp và Mobile fit tỉ lệ màn hình, né tai thỏ
- check các common theo orientation 

### Tính năng Platform Optimization (must have)

- khung hình ổn định, không giật khi bật hiệu ứng hoặc mở popup
- tối ưu dung lượng gói tải
- optimize draw call và auto atlas

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

