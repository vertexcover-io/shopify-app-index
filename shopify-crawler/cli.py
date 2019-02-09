#!/usr/bin/env python
import os
import asyncio

import click

from shopify_crawler.datastore import FireStore
from shopify_crawler.crawler import ShopifyAppCrawler

MAX_WORKERS = os.environ.get("MAX_WORKERS", 20)


@click.group()
def cli():
    pass


@cli.command()
@click.option("-w", "--max-workers", type=click.INT, default=MAX_WORKERS)
def crawl(max_workers=MAX_WORKERS):
    """
    Start the shopify apps crawler
    """
    print(f"Crawling shopify apps with {max_workers} workers")
    loop = asyncio.get_event_loop()
    db = FireStore()
    crawler = ShopifyAppCrawler(db=db, max_workers=max_workers)

    loop.run_until_complete(crawler.run())
    loop.run_until_complete(asyncio.sleep(0.250))
    loop.close()


@cli.group()
def docker():
    pass


if __name__ == "__main__":
    cli()
