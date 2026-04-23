from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import database
import pyth_client
import tracker_engine

app = FastAPI(title="Pyth Price Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await database.init_db()
    await pyth_client.init_feeds_cache()
    tracker_engine.start_background_task()

class TrackerCreate(BaseModel):
    url: str
    target_price: float
    
@app.post("/api/trackers")
async def create_tracker(req: TrackerCreate):
    symbol, pyth_id = pyth_client.get_pyth_id_from_url(req.url)
    if not pyth_id:
        raise HTTPException(status_code=400, detail="Geçersiz Pyth URL'si veya desteklenmeyen sembol.")
    
    # Let's get the current price to determine if the condition is 'above' or 'below'
    try:
        prices = await pyth_client.get_latest_prices([pyth_id])
    except Exception:
         raise HTTPException(status_code=500, detail="Pyth API'ye bağlanılamadı. Lütfen tekrar deneyin.")

    if pyth_id not in prices:
        raise HTTPException(status_code=400, detail="Sembolün güncel fiyatı bulunamadı.")
    
    current_price = prices[pyth_id]
    condition = 'above' if req.target_price >= current_price else 'below'
    
    tracker_id = await database.add_tracker(
        url=req.url,
        symbol=symbol,
        pyth_id=pyth_id,
        target_price=req.target_price,
        condition=condition
    )
    
    return {"message": "Takip eklendi.", "id": tracker_id, "current_price": current_price, "condition": condition}

@app.get("/api/trackers")
async def get_trackers():
    trackers = await database.get_all_trackers()
    
    # We optionally attach current_price for active ones
    active_ids = list(set([t['pyth_id'] for t in trackers if t['status'] == 'active']))
    current_prices = {}
    if active_ids:
        try:
             current_prices = await pyth_client.get_latest_prices(active_ids)
        except Exception:
             pass # silently fail for viewing

    for t in trackers:
        if t['status'] == 'active':
            t['current_price'] = current_prices.get(t['pyth_id'])
    
    return trackers

@app.delete("/api/trackers/{tracker_id}")
async def delete_tracker(tracker_id: int):
    await database.delete_tracker(tracker_id)
    return {"message": "Silindi."}

@app.get("/api/market-info")
async def get_market_info():
    import wti_rollover_checker
    from datetime import datetime
    now = datetime.now()
    
    # Calculate for current month first
    alert_date_str = wti_rollover_checker.get_wti_alert_date(now.year, now.month)
    alert_date = datetime.strptime(alert_date_str, '%Y-%m-%d').date()
    
    display_date = alert_date_str
    display_month = now.strftime("%B")
    
    # If the alert date for this month has passed, calculate for the next month
    if alert_date < now.date():
        next_month = now.month + 1
        next_year = now.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        display_date = wti_rollover_checker.get_wti_alert_date(next_year, next_month)
        display_month = datetime(next_year, next_month, 1).strftime("%B")

    return {
        "wti_alert_date": display_date,
        "current_month": display_month,
        "instruction": f"WTI {display_month} aktif ay değişimi uyarısı."
    }
