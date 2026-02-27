from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

app = FastAPI()

# 配置 CORS 中间件，允许所有来源跨域访问
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/train/{train_number}/station/{station_code}", response_model=Dict)
async def get_train_station_info(train_number: str, station_code: str):
    """
    获取列车在特定车站的模拟信息。
    """
    # 模拟数据
    mock_data = {
        "trainNumber": train_number,
        "origin": "WAS",
        "destination": "BOS",
        "currentStation": station_code,
        "delayMinutes": 36,
        "status": "On Time" if int(train_number) % 2 == 0 else "Delayed"
    }
    return mock_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
