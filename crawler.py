from dataclasses import dataclass
from typing import List
import enum
from asyncio import Queue
import asyncio
import re

import aiohttp
import aiohttp
from bs4 import BeautifulSoup


class Category(enum.Enum):
    STORE_DESIGN = "STORE_DESIGN"
    SALES_AND_CONVERSION = "SALES_AND_CONVERSION"
    MARKETING = "MARKETING"
    ORDER_AND_SHIPPING = "ORDER_AND_SHIPPING"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    INVENTORY_MANAGEMENT = "INVENTORY_MANAGEMENT"
    REPORTING = "REPORTING"
    FINDING_PRODUCT = "FINDING_PRODUCT"
    PRODUCTIVITY = "PRODUCTIVITY"
    FINANCES = "FINANCES"
    TRUST_AND_SECURITY = "TRUST_AND_SECURITY"
    PLACE_TO_SELL = "PLACE_TO_SELL"


class TaskType(enum.Enum):
    LIST = 1
    DETAIL = 2


@dataclass
class App:
    name: str
    description: str
    tags: List[str]
    category: Category
    avg_rating: float
    total_reviews: int
    rating_map: dict
    is_paid: bool
    pricing_plans: List[float]
    developer_name: str
    developer_website: str = None


class ShopifyAppCrawler:
    ROOT_URL = "https://apps.shopify.com/browse"
    AVG_RATING_RE = re.compile("([\d.]+) of")
    REVIEW_COUNT_RE = re.compile(r"\(([\d.]+) reviews\)")

    def __init__(self, loop, max_workers):
        self.loop = loop
        self.q = Queue(loop=loop)
        self.max_workers = max_workers
        self.app_list = []
        self.failed = []

    async def start(self):
        print("Starting Crawler")
        workers = [asyncio.Task(self.crawl()) for _ in range(self.max_workers)]
        await self.q.put((TaskType.LIST, {"page_no": 1}))
        await self.q.join()
        print("Done with all items inqueue")
        for w in workers:
            w.cancel()

    async def crawl(self):
        while True:
            task_type, metadata = await self.q.get()
            if task_type == TaskType.LIST:
                await self._crawl_list_page(metadata["page_no"])
            else:
                await self._crawl_detail_page(metadata["url"])

            self.q.task_done()

    async def _crawl_list_page(self, page_no):
        params = {"page": page_no}
        async with aiohttp.ClientSession(loop=self.loop) as session:
            async with session.get(self.ROOT_URL, params=params) as resp:
                if resp.status != 422:
                    self.q.put_nowait((TaskType.LIST, {"page_no": page_no + 1}))
                    self._parse_list_page(page_no, await resp.text())
                    print(f"Parsed List Page: {page_no + 1}")
                else:
                    print("Reached End of App list")

    def _parse_list_page(self, page_no, html):
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", class_="ui-app-card"):
            self.q.put_nowait((TaskType.DETAIL, {"url": link.get("href")}))

        print(f"Added all detail page from list page:{page_no}")

    async def _crawl_detail_page(self, detail_url):
        async with aiohttp.ClientSession(loop=self.loop) as session:
            async with session.get(detail_url) as resp:
                if resp.status == 200:
                    try:
                        self._parse_detail_page(await resp.text())
                    except Exception as ex:
                        self.failed.append(detail_url)
                        print(f"Failed to parse  detail page: {detail_url}", ex)
                else:
                    print("Failed while crawling detail page", detail_url)

    def _parse_detail_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        name = soup.find("h2", class_="ui-app-store-hero__header__app-name").text
        developer_name = (
            soup.find("span", class_="ui-app-store-hero__header__subscript")
            .find_next("a")
            .text
        )
        description = soup.find(class_="ui-app-store-hero__description").text
        avg_rating_str = soup.find(class_="ui-star-rating__rating").text
        avg_rating = float(self.AVG_RATING_RE.match(avg_rating_str).group(1))
        total_reviews = int(
            self.REVIEW_COUNT_RE.match(
                soup.find(class_="ui-review-count-summary").text
            ).group(1)
        )

        pricing_detail = soup.find(class_="ui-app-pricing--format-detail").text
        is_paid = pricing_detail != "Free"
        tags = []
        for tag in soup.find("div", class_="ui-app-store-hero__kicker").find_all("a"):
            tags.append(tag.text)

        category = tags[0]

        rating_map = [0] * 5
        for i, review_tag in enumerate(
            soup.find_all(class_="reviews-summary__review-count")
        ):
            rating_map[5 - i - 1] = int(
                review_tag.text.replace("(", "").replace(")", "")
            )

        pricing_plans = []
        for plan_tag in soup.find_all(class_="pricing-plan-card__title-header"):
            pricing_plans.append(plan_tag.text.trim())

        dev_website_tag = soup.find(text="Developer website")
        developer_website = (
            dev_website_tag.parent.get("href") if dev_website_tag else None
        )

        app = App(
            name=name,
            description=description,
            category=category,
            tags=tags,
            avg_rating=avg_rating,
            total_reviews=total_reviews,
            is_paid=is_paid,
            rating_map=rating_map,
            developer_name=developer_name,
            pricing_plans=pricing_plans,
            developer_website=developer_website,
        )
        print("Found New App", app)
        self.app_list.append(app)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    crawler = ShopifyAppCrawler(loop, 10)
    loop.run_until_complete(crawler.start())
    print(f"No of apps found: {len(crawler.app_list)}")
