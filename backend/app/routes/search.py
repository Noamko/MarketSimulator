from fastapi import APIRouter, Query

from ..finnhub_client import search_symbols

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=1, max_length=40)):
    results = await search_symbols(q)
    return {"query": q, "results": results}
