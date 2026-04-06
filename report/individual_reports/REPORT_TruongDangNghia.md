# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Trương Đăng Nghĩa
- **Student ID**: 2A202600437
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

*Mô tả đóng góp cụ thể của cá nhân vào codebase.*

- **Modules Implemented**: 
  - `src/agent/tools.py` — Chịu trách nhiệm thiết kế và triển khai Component Tool `CreateChart` tích hợp thư viện Plotly và thư viện Vnstock để vẽ biểu đồ kỹ thuật (Candlestick) và truyền trực tiếp vào UI Streamlit.

- **Code Highlights**:

```python
# src/agent/tools.py
import plotly.graph_objects as go
import streamlit as st
import datetime
from vnstock import Quote

def CreateChart(symbol: str) -> str:
    """Creates a technical chart for a symbol. Returns a confirmation string for the UI."""
    # Xử lý loại bỏ khoảng trắng và chuẩn hóa mã (có thêm strip ngoặc để tránh lỗi LLM)
    symbol = symbol.upper().strip(" '\"")
    
    # Lấy thời gian hiện tại theo GMT+7
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))
    vn_now = datetime.datetime.now(vn_tz)
    end_date = vn_now.strftime("%Y-%m-%d")
    start_date = (vn_now - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
    
    try:
        quote = Quote(symbol=symbol, source='VCI')
        df = quote.history(start=start_date, end=end_date, interval='1H')
        if df.empty:
            return f"Không có dữ liệu để vẽ biểu đồ cho mã {symbol}."
            
        fig = go.Figure(data=[go.Candlestick(
            x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close']
        )])
        
        # Tùy chỉnh Layout biểu đồ và loại bỏ các thanh thời gian trống (Thứ 7, CN, giờ nghỉ qua đêm, nghỉ trưa)
        fig.update_layout(title=f'Biểu đồ nến theo giờ {symbol}', template='plotly_dark', xaxis_rangeslider_visible=False)
        fig.update_xaxes(rangebreaks=[
            dict(bounds=["sat", "mon"]),
            dict(bounds=[15, 9], pattern="hour"),
            dict(bounds=[11.5, 13], pattern="hour")
        ])
        
        # Luân chuyển Object Figure của Plotly ra UI thông qua session_state
        if "temp_charts" not in st.session_state:
            st.session_state.temp_charts = []
        st.session_state.temp_charts.append(fig)
        
        return f"Đã vẽ biểu đồ kỹ thuật mã {symbol} thành công. Tín hiệu Plotly đã được gửi tới UI."
    except Exception as e:
        raise ConnectionError(f"Lỗi khi vẽ biểu đồ: {str(e)}")
```

- **Documentation**: 
  - Tool `CreateChart` không chỉ trả về chuỗi văn bản thông thường (text) cho Agent mà còn xử lý state của UI. Nó tương tác trực tiếp với giao diện người dùng bằng cách ép biểu đồ (Plotly Figure) vào `st.session_state.temp_charts`.
  - Phía ReAct loop (`agent.py`) chỉ cần nhận confirmation `"Đã vẽ biểu đồ... thành công"` làm Observation để kết thúc quá trình suy luận và trả lời người dùng, trong khi vòng lặp ở `app.py` sẽ hiển thị Figure đó ra giao diện đồ họa.
  - Tích hợp thêm các logic che giấu khoảng thời gian ngừng giao dịch chứng khoán đặc thù của Việt Nam (Thứ 7, Chủ Nhật, nghỉ trưa, đóng cửa phiên chiều) qua mảng `rangebreaks` để biểu đồ không bị gãy nến.

---

## II. Debugging Case Study (10 Points)

*Phân tích chuỗi các sự kiện lỗi liên hoàn gặp phải khi nâng cấp hệ thống để vẽ từ 2 biểu đồ trở lên.*

**Vấn đề 1: Thoát vòng lặp sớm ngầm do thiếu định hướng đa nhiệm (LLM Laziness & Bypassing)**
- **Problem**: Khi yêu cầu hệ thống vẽ từ 2 sàn trở lên cùng lúc (ví dụ "Vẽ biểu đồ cho FPT và SSI"), thực tế không có biểu đồ nào được trả ra. Phân tích file log cho thấy từ `AGENT_START` nhảy thẳng tới `AGENT_END` chỉ tốn đúng 1 step, tuyệt nhiên không có dòng `TOOL_CALL` nào xuất hiện. Điều này minh chứng Agent đã lười biếng, chối bỏ việc gọi Action và nhảy thẳng đến thẻ lệnh `Final Answer` để báo thành công giả mạo.

- **Log Source** (`logs/2026-04-06.json`):
```json
{"timestamp": "2026-04-06T16:39:17.021403", "event": "AGENT_START", "data": {"input": "V\u1ebd bi\u1ec3u \u0111\u1ed3 ch\u1ee9ng kho\u00e1n FPT v\u00e0 VCI", "model": "gemma-4-31b-it"}}
{"timestamp": "2026-04-06T16:39:31.145041", "event": "AGENT_END", "data": {"steps": 1}}
```

- **Solution**: Sửa đổi triệt để bằng **System Prompt**. Tôi thiết lập thêm Rule cứng vào `agent.py`: *"Khi người dùng hỏi 2 mã trở lên, BẮT BUỘC phải gọi Action TUẦN TỰ nhiều lần. Nghiêm cấm chốt thẻ Final Answer nếu chưa chạy Action thành công cho từng mã"*. Kết quả log sau đó cho thấy LLM đã ngoan ngoãn bung ra nhiều vòng lặp để gọi code vẽ biểu đồ cho mọi mã được yêu cầu.

**Vấn đề 2: Lỗi phân tách tham số do rác Regex (Regex/Parsing Error)**
- **Problem**: Khi test độ bền bằng prompt `"Vẽ biểu đồ chứng khoán của VCI, FPT, H\P\G"`, dù đã có luật tuần tự nhưng do chuỗi nhiễu `H\P\G` (chứa dấu gạch chéo), biến `args` truyền qua Tool bị sai lệch hoàn toàn, khiến API vnstock không thể query hoặc cỗ máy Regex của ReAct Agent không bắt được đúng định dạng do có ký tự lạ.

- **Log Source** (`logs/2026-04-06.json`):
```json
{"timestamp": "2026-04-06T16:50:15.792164", "event": "AGENT_START", "data": {"input": "V\u1ebd bi\u1ec3u \u0111\u1ed3 ch\u1ee9ng kho\u00e1n c\u1ee7a VCI, FPT, H\\P\\G", "model": "gemma-4-31b-it"}}
{"timestamp": "2026-04-06T16:50:34.769911", "event": "AGENT_END", "data": {"steps": 1}}
```

- **Solution**: Nâng cấp bộ lọc (Sanitizer) tại cả 2 lớp. Một phần ở Regex Action parser dùng để đọc lệnh, và phần quan trọng là dùng lệnh `.replace("\\", "")` hoặc làm sạch chuỗi trực tiếp bên trong `tools.py` (`symbol = re.sub(r'[^A-Z0-9]', '', symbol.upper())`) để đảm bảo dù LLM có hallucinate ra ký tự rác gì đi nữa, chuỗi ném vào thư viện Vnstock luôn ở dạng thuần khiết nhất (chỉ gồm chữ và số).

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Một số đánh giá rút ra sau khi triển khai.*

**1. Reasoning — Block `Thought` hỗ trợ Agent như thế nào?**

Nhờ phải bắt buộc viết ra `Thought` (chuỗi suy nghĩ), ReAct Agent vượt trội hơn hẳn Chatbot ở khả năng "Step by step" giải quyết vấn đề đan xen. Khi được yêu cầu: "So sánh giá của FPT và vẽ biểu đồ của mã đó", Agent sẽ phân tách: Bước 1 gọi `GetPrice(FPT)`, Bước 2 gọi `CreateChart(FPT)` vì trong suy nghĩ nó tự lập kế hoạch cần bao nhiêu info. Chatbot truyền thống sẽ chỉ in ra lượng text "Nói suông" là sẽ đi so sánh, nhưng không ra được Action để lấy giá thật từ file script tool.

**2. Reliability — Khi nào Agent lại hoạt động tệ hơn Chatbot?**

Đối với luồng `CreateChart`, Agent lệ thuộc rất nặng vào việc Tool có thực thi chính xác không. Nếu Tool `VnStock` bị timeout hoặc mạng chậm, Agent phải chờ Observation từ tool xong mới có Token tiếp theo => Latency bị dội lên gấp 3 gấp 4 so với cấu trúc LLM stream thẳng (Chatbot). Trong trường hợp người dùng hỏi thứ rất chung chung như "Chào bạn, hôm nay thế nào?", ReAct loop sẽ cố gắng tìm cách dùng Tool (như tìm Action liên quan đến Thời tiết) nếu GuardRail không làm tốt nhiệm vụ, khiến hệ thống phản hồi cực kì rườm rà.

**3. Observation — Phản hồi môi trường định hướng Agent ra sao?**

Phản hồi từ Tool có sức mạnh "nắn gân" LLM ngay lập tức. Cụ thể, khi tool `CreateChart` báo: `"Tôi đã vẽ biểu đồ kỹ thuật thành công"`, dòng Observation string này chính là cơ sở cho Agent hiểu là: "À, nhiệm vụ đã hoàn tất. Tôi không cần phải vẽ lại, tôi có thể chuyển sang Final Answer được rồi." Nếu Observation không rõ ràng, LLM giống như bị bịt mắt và sẽ bị kẹt trong Action Loop (Tạo biểu đồ vô hạn lần).

---

## IV. Future Improvements (5 Points)

*Hướng phát triển tiếp theo cho production-level AI agent.*

- **Scalability (Khả năng mở rộng)**:
  - Hiện tại Tool `CreateChart` dùng Plotly và đẩy vào `session_state` rớt khá nặng tính phụ thuộc vào UI Streamlit (High Coupling). Nếu lên Production chạy Backend qua API, tôi đề xuất việc sinh file HTML của Plotly sau đó lưu ở Cloud Storage (AWS S3) và tool sẽ trả ra chuỗi `{ "url": "https://url-toi-bieu-do..." }`, giúp client nào (Mobile, Web) dùng ReAct kết quả đều có thể render mượt mà.

- **Safety (Tính bảo mật & An toàn)**:
  - Cần tích hợp Validation Type Checking như `Pydantic` cho đầu vào của mọi Tool thay vì Regex như hiện tại. Điều này hạn chế tối đa Prompt Injection khi LLM tìm cách đưa cú pháp nguy hiểm vào thay vì stock symbol (`CreateChart("../../etc/passwd")`).

- **Performance (Tối ưu hiệu suất)**:
  - ReAct Agent sinh `Thought` mất rất nhiều Token cho mỗi step. Trong Production, có thể đổi kiến trúc sang **Function Calling** native (sử dụng OpenAI Tools API hoặc Gemini Function Call) để bypass bớt việc nhai lại toàn bộ prompt dài, tốc độ xử lý Latency có thể giảm đến 40%.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
