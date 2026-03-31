#!/usr/bin/env python3
# Standalone demonstration: one-file script mimicking main.py flow
import json
import os

# Try to import the real ImgSearch implementation if available
try:
    from crawler.search import ImgSearch  # type: ignore
    HAVE_REAL_IMGSEARCH = True
except Exception:
    ImgSearch = None  # type: ignore
    HAVE_REAL_IMGSEARCH = False


class DummyImgSearch:
    def __init__(self, max_page=None, max_size=None):
        self.max_page = max_page or 1
        self.max_size = max_size
        self.page = 1
        self.offset = 0
        self.items_per_page = 2
        self.sample = [
            {"subject": "示例A", "price": 18.8, "company_name": "示例公司A"},
            {"subject": "示例B", "price": 29.9, "company_name": "示例公司B"},
            {"subject": "示例C", "price": 9.9, "company_name": "示例公司C"},
            {"subject": "示例D", "price": 12.3, "company_name": "示例公司D"},
        ]
    
    @staticmethod
    def init_for_file(path, api=False, max_page=None, max_size=None):
        return DummyImgSearch(max_page, max_size)

    @staticmethod
    def init_for_url(url, api=False, max_page=None, max_size=None):
        return DummyImgSearch(max_page, max_size)

    @staticmethod
    def init_for_b64(b64str, api=False, max_page=None, max_size=None):
        return DummyImgSearch(max_page, max_size)

    def __iter__(self):
        return self

    def __next__(self):
        if self.max_size is not None and self.offset >= self.max_size:
            raise StopIteration
        if self.page > self.max_page:
            raise StopIteration
        start = self.offset
        end = min(start + self.items_per_page, len(self.sample))
        batch = self.sample[start:end]
        self.offset += len(batch)
        self.page += 1
        return batch


def run(obj):
    all_items = []
    for page_ls in obj:
        all_items.extend(page_ls)
        print(page_ls)
    print(f"Total items: {len(all_items)}")
    return {"status": True, "data": all_items}


def file():
    obj = DummyImgSearch.init_for_file(r"D:\Downloads\O1CN01JtdgsB1XKXZTCdkg6_!!3166682905-0-cib (1).jpg", False, 2)
    run(obj)


def url():
    obj = DummyImgSearch.init_for_url("https://example.com/img.jpg", False, 2)
    run(obj)


def b64():
    obj = DummyImgSearch.init_for_b64("dGVzdA==", False, 2)
    run(obj)


if __name__ == "__main__":
    # Must use the real ImgSearch implementation. If not available, raise error.
    if not HAVE_REAL_IMGSEARCH or ImgSearch is None:
        raise RuntimeError("Real ImgSearch implementation is not available. Install dependencies and try again.")
    # path = os.environ.get("IMAGE_PATH", "img.jpg")
    path = r"D:\Downloads\O1CN01JtdgsB1XKXZTCdkg6_!!3166682905-0-cib (1).jpg"
    # Use multiple pages to ensure we fetch possible results
    real_obj = ImgSearch.init_for_file(path, True, max_page=1, max_size=None)
    run(real_obj)
    # url()
    # b64()
