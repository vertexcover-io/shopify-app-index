import logging
from asyncio import Queue
import asyncio
import re
import traceback
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


import aiohttp
from aiohttp import ClientError
from bs4 import BeautifulSoup

from shopify_crawler.model import App, Category, TaskType
from shopify_crawler.datastore import DataStore, FireStore
from shopify_crawler import config


@dataclass
class CrawlTask:
    type: TaskType
    url: str = field(default=config.shopify_root_url())
    page: int = field(default=None)
    retries: int = field(default=0)

    @classmethod
    def create_list_crawl(cls, page_no):
        return CrawlTask(type=TaskType.LIST, page=page_no)

    @classmethod
    def create_detail_crawl(cls, url):
        return CrawlTask(type=TaskType.DETAIL, url=url)

    def retry(self):
        return CrawlTask(type=self.type, url=self.url, page=self.page, retries=self.retries + 1)


class StopCrawler(Exception):
    pass


class ShopifyAppCrawler:

    AVG_RATING_RE = re.compile(r"([\d.]+) of")
    REVIEW_COUNT_RE = re.compile(r"\(([\d.]+) reviews?\)")
    # AIRTABLE_API_KEY = "keyqnICzoZugUKcjE"

    def __init__(self, *, db: DataStore, max_workers: int):
        self.q = Queue()
        self.max_workers = max_workers
        self.app_list = []
        self.failed_tasks = []
        self.session: aiohttp.ClientSession = None
        self.db = db
        self.throttler = asyncio.Semaphore(max_workers)

    async def run(self):
        print("Starting Crawler")
        self.session = aiohttp.ClientSession()
        workers = [asyncio.Task(self.crawl()) for _ in range(self.max_workers)]
        await self.q.put(CrawlTask(TaskType.LIST, page=1))
        await self.q.join()
        print("Done with all items inqueue")
        await self.session.close()
        for w in workers:
            w.cancel()

    async def crawl(self):
        while True:
            task = await self.q.get()
            try:
                if task.type == TaskType.LIST:
                    await self._crawl_list_page(task)
                else:
                    await self._crawl_detail_page(task)
            except Exception:
                traceback.print_exc()

            self.q.task_done()

    @asynccontextmanager
    async def _get_url(self, url, *args, **kwargs):
        async with self.throttler:
            async with self.session.get(url, *args, **kwargs) as resp:
                yield resp

    def _handle_connection_error(self, task, ex):
        print(f"Connection failure while fetching {task.url}: {ex}")
        if task.retries < config.max_crawl_retry():
            retry_task = task.retry()
            self.q.put_nowait(retry_task)
            print(f"Retrying {retry_task}")
        else:
            self.failed_tasks.append({
                'task': task,
                'error': ex
            })
            print(f"Max Retries reached for {task}. Ignoring")

    async def _crawl_list_page(self, task: CrawlTask):
        params = {"page": task.page}
        try:
            async with self._get_url(task.url, params=params) as resp:
                if resp.status in (200, 422):
                    try:
                        self._parse_list_page(await resp.text())
                    except StopCrawler as s:
                        print(s)
                    else:
                        self.q.put_nowait(CrawlTask.create_list_crawl(task.page + 1))
                        print(f"Parsed List Page: {task.page + 1}")

                else:
                    resp.raise_for_status()

        except ClientError as ex:
            self._handle_connection_error(task, ex)

    def _parse_list_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("a", class_="ui-app-card")
        if not cards:
            raise StopCrawler('Completed crawling all pages')

        for link in cards:
            self.q.put_nowait(CrawlTask.create_detail_crawl(link.get("href")))

    async def _crawl_detail_page(self, task: CrawlTask):
        try:
            async with self._get_url(task.url, raise_for_status=True) as resp:
                try:
                    app = self._parse_detail_page(await resp.text())
                    await self.db.save(app)
                except Exception as err:
                    print(f"Failed to parse detail page for {task}: {err}")
                    self.failed_tasks.append({
                        'task': task,
                        'error': err
                    })
                    return

        except ClientError as ex:
            self._handle_connection_error(task, ex)

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

