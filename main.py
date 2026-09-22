from html.parser import HTMLParser
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse


app = FastAPI(title="JSON-LD Price API")


class PriceRequest(BaseModel):
    Url: str | None = None


class JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_json_ld = False
        self._content_parts: list[str] = []
        self.json_ld_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._inside_json_ld:
            return

        if tag.lower() != "script":
            return

        attributes = {name.lower(): value for name, value in attrs if value is not None}
        script_type = attributes.get("type", "").split(";", 1)[0].strip().lower()
        if script_type == "application/ld+json":
            self._inside_json_ld = True
            self._content_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_json_ld:
            self._content_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._inside_json_ld and tag.lower() == "script":
            self.json_ld_blocks.append("".join(self._content_parts).strip())
            self._inside_json_ld = False


def error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def is_valid_url(url: str | None) -> bool:
    if not url or not url.strip():
        return False

    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; JSON-LD-Price-API/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        raise ValueError(f"Page could not be fetched: HTTP {exc.code}") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise ValueError(f"Page could not be fetched: {reason}") from exc
    except TimeoutError as exc:
        raise ValueError("Page could not be fetched: request timed out") from exc


def get_json_ld_blocks(html: str) -> list[str]:
    parser = JsonLdParser()
    parser.feed(html)
    return parser.json_ld_blocks


def normalize_type(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.lower()]
    if isinstance(value, list):
        return [item.lower() for item in value if isinstance(item, str)]
    return []


def stringify_price(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def direct_price_from_object(item: dict[str, Any]) -> str | None:
    offers = item.get("offers")
    if isinstance(offers, dict):
        price = stringify_price(offers.get("price"))
        if price:
            return price

        price = stringify_price(offers.get("lowPrice"))
        if price:
            return price

        price = stringify_price(offers.get("highPrice"))
        if price:
            return price

    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                price = stringify_price(offer.get("price"))
                if price:
                    return price

                price = stringify_price(offer.get("lowPrice"))
                if price:
                    return price

                price = stringify_price(offer.get("highPrice"))
                if price:
                    return price

    for key in ("price", "lowPrice", "highPrice"):
        price = stringify_price(item.get(key))
        if price:
            return price

    aggregate_offer = item.get("aggregateOffer")
    if isinstance(aggregate_offer, dict):
        for key in ("lowPrice", "highPrice", "price"):
            price = stringify_price(aggregate_offer.get(key))
            if price:
                return price

    return None


def walk_json_ld(value: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(value, dict):
        objects.append(value)
        for child in value.values():
            objects.extend(walk_json_ld(child))
    elif isinstance(value, list):
        for item in value:
            objects.extend(walk_json_ld(item))
    return objects


def extract_price(json_ld: Any) -> str | None:
    candidates = walk_json_ld(json_ld)
    product_candidates = [
        item for item in candidates if "product" in normalize_type(item.get("@type"))
    ]

    for item in product_candidates + candidates:
        price = direct_price_from_object(item)
        if price:
            return price

    return None


@app.post("/price")
async def price(payload: PriceRequest):
    if not is_valid_url(payload.Url):
        return error("Url is required and must be a valid http or https URL")

    url = payload.Url.strip()

    try:
        html = await run_in_threadpool(fetch_html, url)
    except ValueError as exc:
        return error(str(exc), status_code=502)

    json_ld_blocks = get_json_ld_blocks(html)
    if not json_ld_blocks:
        return error("No JSON-LD script tag found on the page", status_code=404)

    parse_error_found = False
    for json_ld_text in json_ld_blocks:
        try:
            json_ld = json.loads(json_ld_text)
        except json.JSONDecodeError:
            parse_error_found = True
            continue

        price_value = extract_price(json_ld)
        if price_value is not None:
            return {"Price": price_value}

    if parse_error_found:
        return error("No parseable JSON-LD block with a price was found")

    return error("No price found in any JSON-LD block", status_code=404)
