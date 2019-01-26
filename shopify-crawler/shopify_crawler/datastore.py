import enum

from google.cloud import firestore

from shopify_crawler.model import App
from shopify_crawler.utils import (
    FirestoreBatchClient,
    AirtableClient,
    AirtableException,
    utcnow,
)


class DataStoreException(Exception):
    pass


class DataStore:
    def save(app: App):
        pass


class AirtableDataStore(DataStore):
    def __init__(self, *, api_key: str):
        self.airtable_client = AirtableClient(api_key)

    @staticmethod
    def _prepare_row(cls, app: App):
        row = {}
        for key, value in app.asdict().items():
            if key == "rating_map":
                for index, val in enumerate(value):
                    row[f"{index + 1} Star Rating"] = val
                continue

            if isinstance(value, list):
                value = ", ".join(value)
            if isinstance(value, enum.Enum):
                value = value.name
            row[key.title().replace("_", " ")] = value

        row["id"] = app.id

        return row

    async def save(self, app: App):
        row = self._prepare_row(app)
        try:
            await self.airtable_client.add_row(row)
        except AirtableException as ex:
            raise DataStoreException(str(ex)) from ex


class FireStore(DataStore):

    APP_COLLECTION = "apps"

    def __init__(self):
        self.db = FirestoreBatchClient()

    async def save(self, app: App):
        app_dict = app.asdict(use_enums=False)
        app_dict["timestamp"] = firestore.SERVER_TIMESTAMP
        exists = await self.db.exists(self.APP_COLLECTION, app.id)
        if not exists:
            app_dict["crawled_on"] = utcnow()

        await self.db.set(self.APP_COLLECTION, app.id, app_dict)
