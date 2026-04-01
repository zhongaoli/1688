#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import time
import json
import base64
import random
import logging
from hashlib import md5
from httpx import Timeout, Client, create_ssl_context

# ==================== ERROR CLASSES ====================
class CrawlerError(Exception):
    def __init__(self, url, proxies):
        self.url = url
        self.proxies = proxies

    def __str__(self):
        return f"url:{self.url}, proxies:{self.proxies}"


class RequestError(CrawlerError):
    def __init__(self, url, proxies, exc):
        super().__init__(url, proxies)
        self.exc = exc

    def __str__(self):
        return f"RequestError: {super().__str__()}, exc:{str(self.exc)}"


class BannedError(CrawlerError):
    def __init__(self, url, proxies):
        super().__init__(url, proxies)

    def __str__(self):
        return f"BannedError: {super().__str__()}"


class StatusError(CrawlerError):
    def __init__(self, url, proxies, code):
        super().__init__(url, proxies)
        self.code = code

    def __str__(self):
        return f"StatusError: {super().__str__()}, code:{self.code}"


# ==================== LOGGER ====================
logger = logging.getLogger('ImgSearch')
fmt = logging.Formatter('%(asctime)s,%(process)d,%(name)s,%(levelname)s,%(message)s')
sh = logging.StreamHandler()
sh.setFormatter(fmt)
sh.setLevel(logging.DEBUG)
logger.addHandler(sh)
logger.setLevel(logging.DEBUG)


# ==================== HTTPX SESSION ====================
ciphers_str = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA:AES128-SHA:DES-CBC3-SHA"
ciphers_ls = ciphers_str.split(':')
ciphers = "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:"


def get_ciphers():
    random.shuffle(ciphers_ls)
    return ciphers + ':'.join(ciphers_ls[:random.randint(12, 17)])


class HttpxSession:
    def __init__(self, headers=None, http2=True, verify=None, proxies=None, random_ua=False, timeout=Timeout(60)):
        _headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "zh-CN,zh;q=0.9",
        }
        _headers.update(headers or {})

        if verify is None:
            try:
                verify = create_ssl_context()
                verify.set_ciphers(get_ciphers())
            except Exception:
                verify = False

        self.proxies = proxies

        try:
            self.session = Client(headers=_headers, http2=http2, proxies=proxies,
                                  verify=verify, timeout=timeout, follow_redirects=True)
        except Exception as exc:
            if os.getenv("IGNORE_SSL", "0").lower() in ("1", "true", "yes"):
                logger.warning("TLS/SSL issue detected, retrying with verify=False due to IGNORE_SSL")
                self.session = Client(headers=_headers, http2=http2, proxies=proxies,
                                      verify=False, timeout=timeout, follow_redirects=True)
            else:
                logger.error(f"HTTPX Client init failed: {exc}")
                raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.session.close()

    @property
    def cookies(self):
        return self.session.cookies

    def request(self, method, url, headers=None, params=None, data=None, json_data=None):
        try:
            resp = self.session.request(method=method, url=url, headers=headers,
                                        params=params, data=data, json=json_data)
            if resp.status_code // 100 not in [2, 3]:
                raise StatusError(url, self.proxies, resp.status_code)
            if "sessionStorage.x5referer" in resp.text:
                exc = BannedError(url, self.proxies)
                logger.error(f"BannedError: {exc}")
                raise exc
            return resp
        except (BannedError, StatusError):
            raise
        except Exception as exc:
            logger.error(f"RequestException: {exc}")
            raise RequestError(url, self.proxies, exc)


# ==================== IMGSEARCH ====================
jsv = "2.7.2"
api_version = "1.0"
api_key = "12574478"
app_name = "searchImageUpload"
app_key = "pvvljh1grxcmaay2vgpe9nb68gg9ueg2"
upload_api_path = "mtop.1688.imageService.putImage"
token_api_path = "mtop.ovs.traffic.landing.seotaglist.queryHotSearchWord"

api_host = "https://h5api.m.1688.com"

tag_config = {
    "memberTagIds": {"isShiliDangKou": "3910593", "isSuperFactory": "3938689"},
    "tagIds": {
        "isPinZhiBaoZhang": "3951041",
        "deliveryHours48": "286402",
        "deliveryHours24": "286466",
        "superNewProduct": "277762",
        "isImallExpert": "3981057"
    }
}

tag_info_map = {
    "a": {"title": "源头工厂、平台优选、闪电发货", "img": "https://img.alicdn.com/imgextra/i3/O1CN01LcOfhW1QrmfmYQ66J_!!6000000002030-2-tps-112-112.png"},
    "b": {"title": "阿里巴巴建议您优先选择诚信通会员", "img": "https://img.alicdn.com/tfs/TB1xPJdjXT7gK0jSZFpXXaTkpXa-112-112.png"},
    "c": {"title": "实力商家：更品质、更可靠、更贴心", "img": "https://img.alicdn.com/tfs/TB1ObNfjlv0gK0jSZKbXXbK2FXa-112-112.png"},
    "d": {"title": "工业品牌：品牌正品，品质服务", "img": ""}
}

data_reg = re.compile(r"window.data.offerresultData\s?=\s?successDataCheck\((.*?})\);", re.S | re.I)


def parse_scores_num(score):
    tmp = round(float(score or 0), 1)
    tmp = tmp if tmp >= 0 else 0
    return tmp


def get_shop_tag_info(offer):
    tag_info = {"title": "", "img": ""}
    try:
        offer_tag_data = offer.get("marketOfferTag") or {}
        for k, v in tag_config.items():
            if not offer.get("feMapping"):
                offer["feMapping"] = {}
            ary = offer_tag_data.get(k)
            tag_result = {}
            if v and ary:
                for i in v:
                    tag_result[i] = True if v[i] in ary else False
            offer["feMapping"][k] = tag_result
    except Exception as exc:
        logger.error(f"tag数据格式异常: {exc}")
        return tag_info
    m = (offer.get("offerSource") or {}).get("fromShili")
    f = (offer.get("tradeService") or {}).get("tpMember")
    g = (offer.get("brand") or {}).get("industrialGoods")
    w = ((offer.get("feMapping") or {}).get("memberTagIds") or {}).get("isSuperFactory")
    if w:
        tag_info.update(tag_info_map["a"])
    else:
        if g:
            if f:
                tag_info.update(tag_info_map["b"])
            else:
                tag_info.update(tag_info_map["d"])
        else:
            if m:
                tag_info.update(tag_info_map["c"])
            else:
                if f:
                    tag_info.update(tag_info_map["b"])
    return tag_info


class ImgSearch:
    @staticmethod
    def init_for_url(url, api=False, max_page=None, max_size=None):
        with HttpxSession(verify=True) as session:
            content = session.request("GET", url).content
        b64img = base64.b64encode(content).decode()
        return ImgSearch(b64img, api, max_page, max_size)

    @staticmethod
    def init_for_file(path, api=False, max_page=None, max_size=None):
        assert os.path.exists(path), "file not found"
        with open(path, "rb") as f:
            content = f.read()
        b64img = base64.b64encode(content).decode()
        return ImgSearch(b64img, api, max_page, max_size)

    @staticmethod
    def init_for_b64(b64str, api=False, max_page=None, max_size=None):
        assert base64.b64encode(base64.b64decode(b64str)).decode() == b64str, "not b64str"
        return ImgSearch(b64str, api, max_page, max_size)

    def __init__(self, b64img, api, max_page, max_size):
        self.api = api
        self.max_page = max_page or 1 if not max_size else None
        if not api:
            self.max_page = 1
        self.max_size = max_size
        self.offset = 0
        self.page = 1
        self.upload_success = False
        self.upload_data_str = json.dumps({"imageBase64": b64img, "appName": app_name, "appKey": app_key}, separators=(",", ":"))
        self.img_id = None
        self.req_id = None
        self.session_id = None
        self.token = ""
        self.req = HttpxSession()

        self.set_cookie_cna()
        self.set_token()
        self.upload_img()

    def __str__(self):
        return f"page:{self.page}, max_page:{self.max_page}, max_size:{self.max_size}"

    def __iter__(self):
        return self

    def __next__(self):
        if self.max_size and self.offset >= self.max_size or self.max_page and self.page > self.max_page:
            self.page -= 1
            self.req.close()
            raise StopIteration
        logger.info(f"正在爬取:img_id:{self.img_id} {self}")
        if self.api:
            offer_list = self.request_api_offer_list()
        else:
            offer_list = self.request_web_offer_list()
        if not offer_list:
            logger.warning(f"无结果集:img_id:{self.img_id} {self}")
        item_ls = self.parse_offer_list(offer_list)
        self.page += 1
        return item_ls

    def set_token(self):
        url = f"{api_host}/h5/{token_api_path.lower()}/{api_version}/"
        headers = {"origin": "https://www.1688.com", "referer": "https://www.1688.com/"}
        params = {
            "jsv": jsv,
            "appKey": api_key,
            "t": str(int(time.time() * 1000)),
            "api": token_api_path,
            "v": api_version,
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": "mtopjsonp1",
            "preventFallback": True,
            "data": {},
        }
        self.req.request(method="GET", url=url, headers=headers, params=params)
        self.token = self.req.cookies.get("_m_h5_tk").split("_")[0]
        logger.info(f"设置cookie _m_h5_tk值: {self.token}")
        if not self.token:
            self.req.close()
            raise Exception("_m_h5_tk not found")

    def set_cookie_cna(self):
        timestamp = str(int(time.time() * 1000))
        url = f"https://log.mmstat.com/eg.js?t={timestamp}"
        headers = {"referer": "https://www.1688.com/"}
        self.req.request(method="GET", url=url, headers=headers)
        cna_cookie = self.req.cookies.get("cna")
        self.req.session.cookies.set("cna", cna_cookie, ".1688.com")
        logger.info(f"设置cookie cna值: {cna_cookie}")
        if not cna_cookie:
            self.req.close()
            raise Exception("cna not found")

    def upload_img(self):
        logger.info("正在上传图片!")
        url = f"{api_host}/h5/{upload_api_path.lower()}/{api_version}/"
        headers = {"origin": "https://www.1688.com", "referer": "https://www.1688.com/"}
        timestamp = str(int(time.time() * 1000))
        data = {"data": self.upload_data_str}
        s = self.token + "&" + timestamp + "&" + api_key + "&" + self.upload_data_str
        sign = md5(s.encode()).hexdigest()
        params = {
            "jsv": jsv,
            "appKey": api_key,
            "t": timestamp,
            "sign": sign,
            "api": upload_api_path,
            "ignoreLogin": "true",
            "prefix": "h5api",
            "v": api_version,
            "ecode": "0",
            "dataType": "jsonp",
            "jsonpIncPrefix": "search1688",
            "timeout": "20000",
            "type": "originaljson"
        }
        resp_json = self.req.request(method="POST", url=url, headers=headers, params=params, data=data).json()
        if not (resp_json.get("data") or {}).get("imageId"):
            logger.error(resp_json)
            self.req.close()
            raise Exception("上传图片失败!")
        self.img_id = resp_json["data"]["imageId"]
        self.req_id = resp_json["data"]["requestId"]
        self.session_id = resp_json["data"]["sessionId"]
        logger.info(f"上传图片成功: img_id:{self.img_id}")

    def request_api_offer_list(self):
        url = "https://search.1688.com/service/imageSearchOfferResultViewService"
        headers = {"origin": "https://s.1688.com", "referer": "https://s.1688.com/"}
        params = {
            "tab": "imageSearch",
            "imageAddress": "",
            "imageId": self.img_id,
            "imageIdList": self.img_id,
            "beginPage": self.page,
            "pageSize": "40",
            "pageName": "image",
            "sessionId": self.session_id
        }
        json_data = self.req.request(method="GET", url=url, headers=headers, params=params).json()
        data = (json_data.get("data") or {}).get("data") or {}
        page_count = data.get("pageCount")
        if page_count is not None and self.max_page > page_count:
            logger.info(f"max_page:{self.max_page} 超过最大page_count:{page_count}, max_page更改为:{page_count}")
            self.max_page = page_count
        offer_list = data.get("offerList") or []
        return offer_list

    def request_web_offer_list(self):
        url = "https://s.1688.com/youyuan/index.htm"
        headers = {"referer": "https://www.1688.com/"}
        params = {
            "tab": "imageSearch",
            "imageAddress": "",
            "spm": "a260k.dacugeneral.searchbox.input",
            "imageId": self.img_id,
            "imageIdList": self.img_id,
        }
        body = self.req.request(method="GET", url=url, headers=headers, params=params).text
        reg = data_reg.search(body)
        offer_list = []
        if reg:
            json_data = json.loads(reg.group(1))
            offer_list = (json_data.get("data") or {}).get("offerList") or []
        return offer_list

    def parse_offer_list(self, offer_list):
        item_ls = []
        # print("返回的原始结果列表：",offer_list)
        for offer in offer_list:
            item = {}
            self.offset += 1
            company = offer.get("company") or {}
            information = offer.get("information") or {}
            trade_service = offer.get("tradeService") or {}
            trade_quantity = offer.get("tradeQuantity") or {}
            offer_price = (offer.get("tradePrice") or {}).get("offerPrice") or {}
            position_labels = (offer.get("commonPositionLabels") or {}).get("offerMiddle") or []
            normalizationScore = information.get("normalizationScore") or 0.0

            item["normalizationScore"] = normalizationScore
            item["brand"] = (offer.get("brand") or {}).get("name")
            item["image_url"] = (offer.get("image") or {}).get("imgUrl")
            item["offer_id"] = offer.get("id")
            item["product_url"] = f"https://detail.1688.com/offer/{item['offer_id']}.html"
            item["category_id"] = information.get("categoryId")
            item["subject"] = information.get("subject")
            item["city"] = company.get("city")
            item["province"] = company.get("province")
            item["company_name"] = company.get("name")
            item["shop_url"] = company.get("url")
            item["credit_level"] = company.get("creditLevel")
            item["credit_text"] = company.get("creditLevelText")
            item["reg_capital"] = company.get("regCapital")
            item["reg_capital_unit"] = company.get("regCapitalUnit")
            item["position_labels"] = [labels_map["text"] for labels_map in position_labels if labels_map.get("text")]

            price = (offer_price.get("priceInfo") or {}).get("price") or ""
            if not price:
                original_price_info = offer_price.get("originalValue") or {}
                integer = original_price_info.get("integer") or 0
                decimals = original_price_info.get("decimals") or 0
                price = f"{integer}.{decimals}"
            item["price"] = float(price)

            item["quantity_begin"] = trade_quantity.get("quantityBegin")
            item["quantity_begin_unit"] = trade_quantity.get("unit")
            item["gmv_price"] = (trade_quantity.get("gmvValue") or {}).get("integer")

            repurchase_rate = str(information.get("rePurchaseRate") or "")
            if repurchase_rate and "%" not in repurchase_rate:
                repurchase_rate = round(float(repurchase_rate) * 100, 2)
                repurchase_rate = f"{repurchase_rate}%" if repurchase_rate else ""
            item["repurchase_rate"] = repurchase_rate

            quantity_prices = []
            for q in offer_price.get("quantityPrices") or []:
                price_info = q.get("value") or {}
                integer = price_info.get("integer") or 0
                decimals = price_info.get("decimals") or 0
                quantity_prices.append({"quantity": q.get("quantity"), "price": float(f"{integer}.{decimals}")})
            item["quantity_prices"] = quantity_prices

            item["scores"] = {
                "composite": parse_scores_num(trade_service.get("compositeNewScore")),
                "consultation": parse_scores_num(trade_service.get("consultationScore")),
                "goods": parse_scores_num(trade_service.get("goodsScore")),
                "logistics": parse_scores_num(trade_service.get("logisticsScore")),
                "return": parse_scores_num(trade_service.get("returnScore")),
                "dispute": parse_scores_num(trade_service.get("disputeScore"))
            }
            item["shop_tag"] = get_shop_tag_info(offer)
            item["shop_tag"]["year"] = trade_service.get("tpYear")
            item["ali_talk_name"] = (offer.get("aliTalk") or {}).get("loginId") or ""

            item_ls.append(item)

        return item_ls


# ==================== MAIN ====================
def main():
    image_path = os.environ.get("IMAGE_PATH", "img.jpg")
    if not os.path.exists(image_path):
        print(f"Error: image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    api = True
    max_page = 1

    img_obj = ImgSearch.init_for_file(image_path, api, max_page)
    for page in img_obj:
        for item in page:
            print(item)


if __name__ == "__main__":
    main()
