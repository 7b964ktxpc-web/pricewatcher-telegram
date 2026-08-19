from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import requests

from feed_adapters import FEED_ADAPTERS
from normalizer import normalize_product

UA = os.getenv("PARSER_USER_AGENT", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36")
TIMEOUT = float(os.getenv("PARSER_TIMEOUT", "12"))

@dataclass
class ProviderResult:
    source: str
    marketplace: str
    items: list[dict[str, Any]]
    status: str
    error: str | None = None

class PublicProvider:
    name = "public"
    marketplace = "unknown"
    def search(self, query: str, limit: int = 20) -> ProviderResult:
        raise NotImplementedError
    @staticmethod
    def session() -> requests.Session:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8", "Referer": "https://www.google.com/"})
        return s

class WildberriesProvider(PublicProvider):
    name = "wildberries-public"
    marketplace = "wildberries"
    def search(self, query: str, limit: int = 20) -> ProviderResult:
        candidates = [("https://search.wb.ru/exactmatch/ru/common/v9/search", {"resultset":"catalog","sort":"popular","suppressSpellcheck":"false"}), ("https://search.wb.ru/exactmatch/ru/common/v7/search", {"resultset":"catalog","sort":"popular"})]
        common = {"appType":1,"curr":"rub","dest":int(os.getenv("WB_DEST","-1257786")),"page":1,"query":query,"spp":30}
        s = self.session(); last = None
        for url, extra in candidates:
            try:
                r = s.get(url, params={**common, **extra}, timeout=TIMEOUT); last = f"HTTP {r.status_code}"
                if r.status_code != 200: continue
                products = r.json().get("data",{}).get("products",[]); items=[]
                for p in products[:limit]:
                    nm=p.get("id") or p.get("nmId"); price=p.get("salePriceU"); old=p.get("priceU")
                    if isinstance(price,(int,float)): price/=100
                    if isinstance(old,(int,float)): old/=100
                    items.append(normalize_product(source=self.name, marketplace=self.marketplace, product_id=nm, title=p.get("name"), price=price, old_price=old, url=f"https://www.wildberries.ru/catalog/{nm}/detail.aspx" if nm else None, category=p.get("subjectName"), available=True, extra={"brand":p.get("brand"),"rating":p.get("rating"),"feedbacks":p.get("feedbacks")}))
                return ProviderResult(self.name,self.marketplace,items,"ok")
            except (requests.RequestException, ValueError) as e: last=str(e)
        return ProviderResult(self.name,self.marketplace,[],"blocked",last or "no response")

class OzonProvider(PublicProvider):
    name="ozon-public"; marketplace="ozon"
    def search(self, query: str, limit: int=20) -> ProviderResult:
        try:
            r=self.session().get(f"https://www.ozon.ru/search/?text={quote_plus(query)}",timeout=TIMEOUT,allow_redirects=True)
            if r.status_code!=200: return ProviderResult(self.name,self.marketplace,[],"blocked",f"HTTP {r.status_code}")
            return ProviderResult(self.name,self.marketplace,[],"html_only","catalog page reachable; structured extraction requires an approved feed/adapter")
        except requests.RequestException as e: return ProviderResult(self.name,self.marketplace,[],"error",str(e))

class YandexMarketProvider(PublicProvider):
    name="yandex-market-public"; marketplace="yandex_market"
    def search(self, query: str, limit: int=20) -> ProviderResult:
        try:
            r=self.session().get(f"https://market.yandex.ru/search?text={quote_plus(query)}",timeout=TIMEOUT,allow_redirects=True)
            if r.status_code!=200: return ProviderResult(self.name,self.marketplace,[],"blocked",f"HTTP {r.status_code}")
            return ProviderResult(self.name,self.marketplace,[],"html_only","search page reachable; structured extraction requires an approved feed/adapter")
        except requests.RequestException as e: return ProviderResult(self.name,self.marketplace,[],"error",str(e))

class SimaLandProvider(PublicProvider):
    name="simaland-public"; marketplace="simaland"
    def search(self, query: str, limit: int=20) -> ProviderResult:
        try:
            r=self.session().get(f"https://www.sima-land.ru/search/?q={quote_plus(query)}",timeout=TIMEOUT,allow_redirects=True)
            if r.status_code!=200: return ProviderResult(self.name,self.marketplace,[],"blocked",f"HTTP {r.status_code}")
            return ProviderResult(self.name,self.marketplace,[],"html_only","search page reachable; use an approved catalog/feed for structured import")
        except requests.RequestException as e: return ProviderResult(self.name,self.marketplace,[],"error",str(e))

PROVIDERS={"wildberries":WildberriesProvider(),"ozon":OzonProvider(),"yandex_market":YandexMarketProvider(),"simaland":SimaLandProvider(),**FEED_ADAPTERS}

def search_sources(query: str, limit: int=20, sources: list[str]|None=None) -> dict[str,Any]:
    selected=sources or list(PROVIDERS); results=[]
    for name in selected:
        provider=PROVIDERS.get(name)
        if not provider:
            results.append({"source":name,"status":"unknown_source","items":[],"error":"Unknown provider"}); continue
        if name in FEED_ADAPTERS:
            adapter=FEED_ADAPTERS[name]; result=adapter.search(query,limit)
            results.append({"source":name,"marketplace":adapter.marketplace,**result}); continue
        result=provider.search(query,limit)
        results.append({"source":result.source,"marketplace":result.marketplace,"status":result.status,"items":result.items,"error":result.error})
    items=[x for r in results for x in r["items"]]
    return {"query":query,"count":len(items),"items":items,"sources":results}
