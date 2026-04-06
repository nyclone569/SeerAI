import datetime
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any, List
from vnstock import Vnstock

# In a real environment, vnstock fetches from VNDirect/TCBS/SSI.
# We will use vnstock for real data, but allow simulating an error for testing.

SIMULATE_API_ERROR = False

def GetPrice(symbol: str) -> str:
    """Gets the latest close price for a VN stock symbol."""
    if SIMULATE_API_ERROR:
        raise ConnectionError("API VNDirect bị bảo trì / Timeout")
    
    symbol = symbol.upper().strip()
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    
    try:
        df = Vnstock().stock(symbol=symbol, source='VCI').quote.history(start=start_date, end=end_date)
        if df.empty:
            return f"Không tìm thấy dữ liệu giá cho mã {symbol}."
        latest_price = df.iloc[-1]["close"] * 1000 # vnstock trả về giá x1000
        return f"Giá hiện tại của {symbol} là {latest_price:,.0f} VND"
    except Exception as e:
        raise ConnectionError(f"API VNDirect lỗi: {str(e)}")

def CreateChart(symbol: str) -> str:
    """Creates a technical chart for a symbol. Returns a confirmation string for the UI."""
    if SIMULATE_API_ERROR:
        raise ConnectionError("API VNDirect bị bảo trì / Timeout")

    symbol = symbol.upper().strip()
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    try:
        df = Vnstock().stock(symbol=symbol, source='VCI').quote.history(start=start_date, end=end_date)
        if df.empty:
            return f"Không có dữ liệu để vẽ biểu đồ cho mã {symbol}."
        return f"Đã vẽ biểu đồ kỹ thuật mã {symbol} thành công. Tín hiệu Plotly đã được gửi tới UI."
    except Exception as e:
        raise ConnectionError(f"Lỗi khi vẽ biểu đồ: {str(e)}")

def GetStockID(company_name: str) -> str:
    """Tra cứu mã cổ phiếu từ tên công ty."""
    if SIMULATE_API_ERROR:
        raise ConnectionError("API VNDirect bị bảo trì / Timeout")

    # A mock dictionary for demonstration, or we can use vnstock if it has a fuzzy search.
    # vnstock's listing feature retrieves all stocks, but we'll mock a few for speed.
    companies = {
        "fpt": "FPT",
        "hòa phát": "HPG",
        "hoa sen": "HSG",
        "vietcombank": "VCB",
        "ssi": "SSI"
    }
    
    for key in companies:
        if key in company_name.lower():
            return f"Mã cổ phiếu của {company_name} là {companies[key]}"
            
    return f"Không tìm thấy mã cổ phiếu hợp lệ cho công ty: {company_name}."

# Define the tool schemas for the Agent
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "GetPrice",
        "description": "Dùng để lấy giá cổ phiếu hiện tại của một mã chứng khoán (nội địa Việt Nam). Đầu vào là 1 mã chứng khoán (VD: FPT, HPG)."
    },
    {
        "name": "CreateChart",
        "description": "Dùng để vẽ biểu đồ kỹ thuật cho một mã chứng khoán. Đầu vào là mã chứng khoán (VD: SSI, VCB)."
    },
    {
        "name": "GetStockID",
        "description": "Dùng để tra cứu mã cổ phiếu khi người dùng chỉ cung cấp tên công ty. Đầu vào là tên công ty."
    }
]

def execute_tool_logic(tool_name: str, args: str) -> str:
    """Helper method to map tool names to Python functions."""
    if tool_name == "GetPrice":
        return GetPrice(args)
    elif tool_name == "CreateChart":
        return CreateChart(args)
    elif tool_name == "GetStockID":
        return GetStockID(args)
    else:
        # Action Error Handler scenario will catch this if the LLM hallucinates
        raise ValueError(f"Sai tên Tool: {tool_name}")
