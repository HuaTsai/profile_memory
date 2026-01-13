import subprocess
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Memory Monitor API")


@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {"status": "healthy", "service": "memory-monitor"}


@app.get("/available-memories")
async def get_available_memories():
    """
    讀取系統記憶體資訊（從 /proc/meminfo）
    """
    try:
        mem_info = {}
        
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1])  # 單位是 kB
                    
                    if key == 'MemTotal':
                        # 轉換為 GB (kB -> GB)
                        mem_info['total_memory'] = round(value / 1024 / 1024, 2)
                    elif key == 'MemAvailable':
                        # 轉換為 GB (kB -> GB)
                        mem_info['available_memory'] = round(value / 1024 / 1024, 2)
                
                # 當找到兩個需要的值後就可以停止
                if 'total_memory' in mem_info and 'available_memory' in mem_info:
                    break
        
        # 計算已使用記憶體
        if 'total_memory' in mem_info and 'available_memory' in mem_info:
            mem_info['used_memory'] = round(
                mem_info['total_memory'] - mem_info['available_memory'], 
                2
            )
        
        return JSONResponse(content=mem_info)
    
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="找不到 /proc/meminfo 檔案"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"讀取記憶體資訊時發生錯誤: {str(e)}"
        )


@app.get("/memories")
async def get_memories():
    """
    執行 docker stats 並回傳容器記憶體使用狀況
    """
    try:
        # 執行 docker stats 指令
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Docker stats 執行失敗: {result.stderr}"
            )
        
        # 解析每一行的 JSON 資料
        output_lines = result.stdout.strip().split('\n')
        stats_data = []
        
        for line in output_lines:
            if line.strip():
                try:
                    stats_data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    # 如果某一行解析失敗，記錄但繼續處理其他行
                    print(f"無法解析 JSON: {line}, 錯誤: {e}")
        
        return JSONResponse(content=stats_data)
    
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Docker stats 執行逾時"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="找不到 Docker 指令，請確認 Docker 已安裝"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"發生錯誤: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=60001)
