from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

app = FastAPI()

# 核心修复：当 origins 是 ["*"] 时，allow_credentials 必须是 False
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/train/{train_number}/station/{station_code}", response_model=Dict)
async def get_train_station_info(train_number: str, station_code: str):
    """
    获取列车在特定车站的模拟信息。
    """
    # 修复：防止 train_number 包含字母时导致服务器崩溃
    is_even = False
    if train_number.isdigit():
        is_even = int(train_number) % 2 == 0

    # 模拟数据
    mock_data = {
        "trainNumber": train_number,
        "origin": "WAS",
        "destination": "BOS",
        "currentStation": station_code.upper(),
        "delayMinutes": 36,
        "status": "On Time" if is_even else "Delayed"
    }
    return mock_data
