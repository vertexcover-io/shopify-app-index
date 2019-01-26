import enum
from datetime import datetime

from dataclasses import dataclass, asdict, field
from typing import List

from shopify_crawler.utils import slugify


class Category(enum.Enum):
    STORE_DESIGN = "Store design"
    SALES_AND_CONVERSION = "Sales and conversion optimization"
    MARKETING = "Marketing"
    ORDER_AND_SHIPPING = "Orders and shipping"
    CUSTOMER_SUPPORT = "Customer support"
    INVENTORY_MANAGEMENT = "Inventory management"
    REPORTING = "Reporting"
    FINDING_PRODUCT = "Finding and adding products"
    PRODUCTIVITY = "Productivity"
    FINANCES = "Finances"
    TRUST_AND_SECURITY = "Trust and security"
    PLACES_TO_SELL = "Places to sell"


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
    crawled_on: datetime = field(default=None)

    @property
    def id(self):
        return slugify(self.name)

    def asdict(self, *, use_enums=True, **kwargs):
        dct = asdict(self, **kwargs)
        if not use_enums:
            dct["category"] = str(dct["category"])
        return dct
