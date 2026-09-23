import asyncio
import json
import unittest
from unittest.mock import patch

from main import (
    PriceRequest,
    extract_price,
    extract_price_from_html,
    get_json_ld_blocks,
    is_valid_url,
    price,
)


class JsonLdPriceTests(unittest.TestCase):
    def test_collects_all_json_ld_blocks(self):
        html = """
        <html>
            <head>
                <script type="application/ld+json">
                    {"@type": "Product", "offers": {"price": "188"}}
                </script>
                <script type="application/ld+json">
                    {"@type": "Product", "offers": {"price": "999"}}
                </script>
            </head>
        </html>
        """

        json_ld_blocks = get_json_ld_blocks(html)

        self.assertEqual(len(json_ld_blocks), 2)
        self.assertEqual(extract_price(json.loads(json_ld_blocks[0])), "188")
        self.assertEqual(extract_price(json.loads(json_ld_blocks[1])), "999")

    def test_prefers_product_inside_graph(self):
        data = {
            "@graph": [
                {"@type": "BreadcrumbList", "price": "10"},
                {"@type": "Product", "offers": [{"price": 188}]},
            ]
        }

        self.assertEqual(extract_price(data), "188")

    def test_reads_aggregate_offer_low_price(self):
        data = {"@type": "Product", "aggregateOffer": {"lowPrice": "188"}}

        self.assertEqual(extract_price(data), "188")

    def test_rejects_invalid_urls(self):
        self.assertFalse(is_valid_url(""))
        self.assertFalse(is_valid_url("example.com/product"))
        self.assertFalse(is_valid_url("ftp://example.com/product"))

    def test_price_endpoint_searches_all_json_ld_blocks(self):
        html = """
        <script type="application/ld+json">
            {"@type": "BreadcrumbList", "itemListElement": []}
        </script>
        <script type="application/ld+json">
            {"@type": "Product", "offers": {"price": "188"}}
        </script>
        """

        with patch("main.fetch_html", return_value=html):
            response = asyncio.run(
                price(PriceRequest(Url="https://example.com/product"))
            )

        self.assertEqual(response, {"Price": "188"})

    def test_price_endpoint_skips_invalid_json_ld_blocks(self):
        html = """
        <script type="application/ld+json">
            {"@type": "Product", "offers": {
        </script>
        <script type="application/ld+json">
            {"@type": "Product", "offers": {"price": "188"}}
        </script>
        """

        with patch("main.fetch_html", return_value=html):
            response = asyncio.run(
                price(PriceRequest(Url="https://example.com/product"))
            )

        self.assertEqual(response, {"Price": "188"})

    def test_extracts_myntra_embedded_discounted_price(self):
        html = """
        <script>
            window.__myx = {
                "pdpData": {
                    "mrp": 2499,
                    "sizes": [
                        {
                            "sizeSellerData": [
                                {"mrp": 2499, "discountedPrice": 1499}
                            ]
                        }
                    ]
                }
            };
        </script>
        """

        self.assertEqual(extract_price_from_html(html), "1499")

    def test_price_endpoint_falls_back_to_embedded_product_state(self):
        html = """
        <script>
            window.__myx = {
                "pdpData": {
                    "sizes": [
                        {"sizeSellerData": [{"discountedPrice": 1499}]}
                    ]
                }
            };
        </script>
        """

        with patch("main.fetch_html", return_value=html):
            response = asyncio.run(
                price(PriceRequest(Url="https://www.myntra.com/product"))
            )

        self.assertEqual(response, {"Price": "1499"})


if __name__ == "__main__":
    unittest.main()
