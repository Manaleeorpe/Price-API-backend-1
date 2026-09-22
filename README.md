# JSON-LD Price API

Small FastAPI backend that returns a product price from JSON-LD script tags on a page.

## Behavior

- `POST /price` accepts a JSON body with a product `Url`.
- The API fetches the page HTML.
- It reads every `<script type="application/ld+json">...</script>` block in page order.
- It parses each block as JSON and returns the first price found from common JSON-LD fields such as `offers.price`, `offers[0].price`, `price`, `lowPrice`, `highPrice`, and `aggregateOffer.lowPrice`.
- It does not use CSS selectors, HTML price regexes, meta tags, Open Graph tags, browser automation, or fallback scraping.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

## Run With Docker

```powershell
docker build -t jsonld-price-api .
docker run --rm -p 8000:8000 jsonld-price-api
```

The API will run at:

```text
http://127.0.0.1:8000
```

## Example Request

```bash
curl -X POST "http://127.0.0.1:8000/price" \
  -H "Content-Type: application/json" \
  -d "{\"Url\":\"https://example.com/product\"}"
```

Successful response:

```json
{
  "Price": "188"
}
```

Errors return a clear JSON response:

```json
{
  "error": "No price found in any JSON-LD block"
}
```
