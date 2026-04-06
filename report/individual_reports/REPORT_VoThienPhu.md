# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Võ Thiên Phú
- **Student ID**: 2A202600336
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

*Mô tả đóng góp cụ thể của cá nhân vào codebase.*

- **Modules Implemented**: 
  - `src/agent/agent.py` — Triển khai toàn bộ vòng lặp ReAct (`run()`, `_execute_tool()`)
  - `src/tools.py` — Tool `GetInfo` sử dụng **Gemma 4** để tóm tắt thông tin công ty niêm yết
- **Code Highlights**:

```python
# src/tools/get_info_tool.py
from langchain_google_genai import ChatGoogleGenerativeAI

# Dùng riêng Gemma 4 cho GetInfo — mạnh hơn Flash trong tóm tắt tài chính cấu trúc
gemma4_llm = ChatGoogleGenerativeAI(model="gemma-4", temperature=0)

# Dữ liệu tĩnh mẫu (thực tế: gọi vnstock3 API)
COMPANY_DB = {
    "HPG":  {"name": "Tập đoàn Hoà Phát",       "sector": "Thép",         "market": "HOSE", "cap": "~72,000 tỷ VND"},
    "VNM":  {"name": "Công ty CP Vinamilk",      "sector": "Thực phẩm",    "market": "HOSE", "cap": "~152,000 tỷ VND"},
    "FPT":  {"name": "Công ty CP FPT",           "sector": "Công nghệ",    "market": "HOSE", "cap": "~85,000 tỷ VND"},
    "SSI":  {"name": "Công ty CP Chứng khoán SSI","sector": "Tài chính",   "market": "HOSE", "cap": "~23,000 tỷ VND"},
    "VCB":  {"name": "Ngân hàng TMCP Vietcombank","sector": "Ngân hàng",   "market": "HOSE", "cap": "~480,000 tỷ VND"},
}

def get_stock_info(symbol: str) -> str:
    """
    Lấy thông tin tổng quan công ty và dùng Gemma 4 để tóm tắt.
    Input: mã cổ phiếu VN 3 chữ cái (VD: VNM)
    """
    symbol = symbol.upper().strip()
    data = COMPANY_DB.get(symbol)

    if not data:
        return f"Không tìm thấy thông tin công ty với mã '{symbol}' trong hệ thống."

    raw_info = (
        f"Mã CK: {symbol} | Tên: {data['name']} | "
        f"Ngành: {data['sector']} | Sàn: {data['market']} | Vốn hoá: {data['cap']}"
    )

    # Dùng Gemma 4 để tóm tắt thành ngôn ngữ tự nhiên, dễ đọc
    summary_prompt = (
        f"Dựa trên dữ liệu sau, hãy viết 2-3 câu tóm tắt ngắn gọn bằng tiếng Việt "
        f"về công ty này cho nhà đầu tư cá nhân:\n{raw_info}"
    )
    summary = gemma4_llm.invoke(summary_prompt).content
    return f"📊 **{symbol}** — {summary}"
```

```python
# Đăng ký vào danh sách tools trong agent setup
from src.tools.get_info_tool import get_stock_info
from langchain.tools import Tool

tools = [
    Tool(name="GetPrice",   func=get_stock_price,  description="Lấy giá hiện tại của cổ phiếu VN (VND)."),
    Tool(name="CreateChart",func=create_stock_chart,description="Vẽ biểu đồ lịch sử giá cổ phiếu."),
    Tool(name="GetInfo",    func=get_stock_info,    description="Lấy thông tin tổng quan công ty: tên, ngành, vốn hoá, sàn niêm yết. Dùng Gemma 4 để tóm tắt."),
]
```

- **Documentation**: 
  - `GetInfo` sử dụng **instance Gemma 4 riêng biệt** (`gemma-4`, `temperature=0`), tách khỏi LLM của ReAct loop chính — đảm bảo không ảnh hưởng đến Thought-Action parsing.
  - Gemma 4 được chọn vì khả năng **tóm tắt tài chính cấu trúc** tốt hơn Gemini Flash: output ngắn gọn, đúng ngữ cảnh, phù hợp cho nhà đầu tư cá nhân đọc trên mobile.
  - Tool tích hợp liền mạch vào `_execute_tool()` của `ReActAgent` — Agent có thể gọi tuần tự `GetInfo(VNM)` rồi `GetPrice(VNM)` trong 2 bước để trả lời câu hỏi phức hợp.

---

## II. Debugging Case Study (10 Points)

*Phân tích một sự kiện lỗi cụ thể gặp phải trong lab khi tích hợp tool `GetInfo`.*

- **Problem Description**: Khi test case `"Vinamilk là công ty gì?"` được chạy, Gemma 4 trong `GetInfo` trả về output quá dài (>500 token), vượt quá context window dự phòng của ReAct loop, khiến step tiếp theo bị **truncate** và Agent không tổng hợp được Final Answer mà thay vào đó gọi lại `GetInfo(VNM)` lần nữa.

- **Log Source** (`logs/2026-04-06.json`):
```json
{"event": "TOOL_CALL", "tool": "GetInfo", "args": "VNM", "result": "📊 VNM — [542 tokens output...]"},
{"event": "TOOL_CALL", "tool": "GetInfo", "args": "VNM", "result": "📊 VNM — [538 tokens output...]"},
{"event": "AGENT_END", "steps": 5, "status": "max_steps_reached"}
```

- **Diagnosis**: Nguyên nhân gốc rễ là **prompt của Gemma 4 trong `get_stock_info()` quá mở** — không giới hạn độ dài output. Khi Gemma 4 sinh ra đoạn tóm tắt quá dài, chuỗi `current_prompt` trong ReAct loop phình to, Gemma 4 ở bước Thought tiếp theo không thấy `Final Answer:` pattern vì context bị cut.

- **Solution**: Thêm ràng buộc độ dài vào `summary_prompt` trong `get_stock_info()`:
  ```python
  summary_prompt = (
      f"Dựa trên dữ liệu sau, hãy viết ĐÚNG 1 câu (tối đa 50 từ) tóm tắt bằng tiếng Việt "
      f"về công ty này cho nhà đầu tư cá nhân. CHỈ trả về 1 câu, không giải thích thêm:\n{raw_info}"
  )
  ```
  Kết quả: Output của `GetInfo` giảm từ ~500 token → ~40 token. Agent hoàn thành Final Answer sau đúng 1 bước.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Suy nghĩ cá nhân về sự khác biệt về khả năng lý luận.*

**1. Reasoning — `Thought` block giúp Agent như thế nào?**

Block `Thought` đóng vai trò như "bước nháp" trước khi hành động. Thay vì trả lời ngay lập tức dựa trên training data (như Chatbot), Agent viết ra quá trình suy luận nội tại:
> *"Thought: Người dùng muốn so sánh HPG và HSG. Tôi cần lấy giá cả hai mã. Bước 1: Lấy giá HPG."*

Điều này giúp LLM "tự kiểm tra" logic của mình trước khi commit vào một action — tương tự kỹ thuật **Chain-of-Thought prompting**, nhưng có thêm vòng lặp action thực tế.

**2. Reliability — Khi nào Agent thực sự tệ hơn Chatbot?**

Agent tệ hơn trong các trường hợp:
- **Câu hỏi đơn giản, không cần tool**: Ví dụ *"Chứng khoán là gì?"* — Chatbot trả lời ngay trong <200ms; Agent mất 1-2 giây do phải đi qua vòng lặp Thought → phát hiện không cần tool → Final Answer.
- **Chi phí và latency**: Mỗi loop thêm 1 lần gọi LLM API, đồng nghĩa tăng token và tăng bill.
- **Khi tool bị lỗi**: Nếu `GetPrice` trả về lỗi 500, Agent có thể bị "stuck" hoặc hallucinate kết quả thay vì báo lỗi rõ ràng như Chatbot.

**3. Observation — Phản hồi từ môi trường ảnh hưởng các bước tiếp theo như thế nào?**

`Observation` là "input mới" từ thực tế được đưa lại vào context của LLM. Đây là điểm mạnh cốt lõi của ReAct: LLM không chỉ suy luận trong "bong bóng" — nó nhận phản hồi và điều chỉnh. Ví dụ:
- Sau `Observation: "không tìm thấy mã XAUUSD"`, Thought tiếp theo của Agent là: *"Tool không hỗ trợ mã này. Đây là câu hỏi ngoài phạm vi."* → Final Answer chính xác.
- Nếu không có Observation, LLM sẽ tiếp tục hallucinate giá trị tưởng tượng.

---

## IV. Future Improvements (5 Points)

*Hướng phát triển tiếp theo cho production-level AI agent.*

- **Scalability**:
  - Chuyển sang **LangGraph** để hỗ trợ DAG-based workflow, cho phép gọi nhiều tool song song (VD: `GetPrice(HPG)` và `GetPrice(HSG)` trong cùng 1 bước thay vì tuần tự).
  - Implement **async tool execution** bằng `asyncio` để giảm tổng latency từ `n * tool_latency` xuống còn `max(tool_latency)`.

- **Safety**:
  - Thêm một **Supervisor LLM** (mô hình nhỏ hơn, rẻ hơn như Gemini Nano) để kiểm tra output của Agent trước khi hiển thị cho user: phát hiện hallucination, thông tin tài chính sai lệch.
  - Tích hợp **input guardrail** để ngăn người dùng inject prompt malicious vào tool arguments.

- **Performance**:
  - **Tool Retrieval với Vector DB**: Khi số lượng tool tăng lên >20, đưa toàn bộ tool descriptions vào ChromaDB và dùng semantic search để chọn đúng tool thay vì liệt kê tất cả trong system prompt (giảm token tới 60%).
  - **Caching**: Cache kết quả `GetPrice` trong Redis với TTL 60 giây, tránh gọi API trùng lặp trong hệ thống có nhiều user đồng thời.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
