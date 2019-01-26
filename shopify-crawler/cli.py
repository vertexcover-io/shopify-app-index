#!/usr/bin/env python

import asyncio
import fire

from shopify_crawler.datastore import FireStore
from shopify_crawler.crawler import ShopifyAppCrawler


def crawl(max_workers=10):
    loop = asyncio.get_event_loop()
    db = FireStore()
    crawler = ShopifyAppCrawler(db=db, max_workers=max_workers)
    loop.run_until_complete(crawler.run())


if __name__ == "__main__":
    fire.Fire()
