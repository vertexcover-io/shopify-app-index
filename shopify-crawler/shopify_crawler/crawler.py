import logging
from asyncio import Queue
import asyncio
import re
import traceback
import sys

import aiohttp
from bs4 import BeautifulSoup

from shopify_crawler.model import App, Category, TaskType
from shopify_crawler.datastore import DataStore, FireStore


class ShopifyAppCrawler:
    ROOT_URL = "https://apps.shopify.com/browse"
    AVG_RATING_RE = re.compile(r"([\d.]+) of")
    REVIEW_COUNT_RE = re.compile(r"\(([\d.]+) reviews?\)")
    # AIRTABLE_API_KEY = "keyqnICzoZugUKcjE"

    def __init__(self, *, db: DataStore, max_workers: int):
        self.q = Queue()
        self.max_workers = max_workers
        self.app_list = []
        self.failed_apps = []
        self.failed_urls = []
        self.session = None
        self.db = db

    async def run(self):
        print("Starting Crawler")
        self.session = aiohttp.ClientSession()
        workers = [asyncio.Task(self.crawl()) for _ in range(self.max_workers)]
        await self.q.put((TaskType.LIST, {"page_no": 1}))
        await self.q.join()
        print("Done with all items inqueue")
        self.session.close()
        for w in workers:
            w.cancel()

    async def crawl(self):
        while True:
            task_type, metadata = await self.q.get()
            try:
                if task_type == TaskType.LIST:
                    await self._crawl_list_page(metadata["page_no"])
                else:
                    await self._crawl_detail_page(metadata["url"])
            except Exception:
                traceback.print_exc()

            self.q.task_done()

    async def _crawl_list_page(self, page_no):
        params = {"page": page_no}
        async with self.session.get(self.ROOT_URL, params=params) as resp:
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
        async with self.session.get(detail_url) as resp:
            if resp.status == 200:
                try:
                    app = self._parse_detail_page(await resp.text())
                except Exception:
                    print(f"Failed to parse detail page for app: {detail_url}:")
                    traceback.print_exc()
                    self.failed_urls.append(
                        {"url": detail_url, "error": traceback.format_exc()}
                    )
                else:
                    await self.db.save(app)
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
        review_count_match = self.REVIEW_COUNT_RE.match(
            soup.find(class_="ui-review-count-summary").text
        )

        total_reviews = int(review_count_match.group(1)) if review_count_match else 0

        pricing_detail = soup.find(class_="ui-app-pricing--format-detail").text
        is_paid = pricing_detail != "Free"
        tags = []
        for tag in soup.find("div", class_="ui-app-store-hero__kicker").find_all("a"):
            tags.append(tag.text)

        category = Category(tags[0])
        tags = tags[1:]

        rating_map = [0] * 5
        for i, review_tag in enumerate(
            soup.find_all(class_="reviews-summary__review-count")
        ):
            rating_map[5 - i - 1] = int(
                review_tag.text.replace("(", "").replace(")", "")
            )

        pricing_plans = []
        for plan_tag in soup.find_all(class_="pricing-plan-card__title-header"):
            pricing_plans.append(plan_tag.text.strip())

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
        return app

