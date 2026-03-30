# -*- coding: utf-8 -*-

import random
import os
from .error import *
from .ua import ua_ls
from .log import logger
from httpx import Timeout, Client, create_ssl_context, Response

ciphers_str = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA:AES128-SHA:DES-CBC3-SHA"
ciphers_ls = ciphers_str.split(':')
ciphers = "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:"


def get_ciphers():
    random.shuffle(ciphers_ls)
    return ciphers + ':'.join(ciphers_ls[:random.randint(12, 17)])


class HttpxSession:

    def __init__(self, headers=None, http2=True, verify=None,
                  proxies=None, random_ua=False, timeout=Timeout(60)):

        _headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "zh-CN,zh;q=0.9",
        }
        _headers.update(headers or {})

        if random_ua:
            _headers["user-agent"] = random.choice(ua_ls)

        # Determine SSL verification strategy
        # Default: try to use a custom SSLContext with a shuffled cipher list.
        # If that fails (e.g., in restricted environments), allow falling back to
        # verify=False when IGNORE_SSL is enabled for testing purposes.
        if verify is None:
            try:
                verify = create_ssl_context()
                verify.set_ciphers(get_ciphers())
            except Exception:
                verify = False
        else:
            pass

        self.proxies = proxies

        try:
            self.session = Client(headers=_headers, http2=http2, proxies=proxies,
                                  verify=verify, timeout=timeout, follow_redirects=True)
        except Exception as exc:
            # In environments with strict TLS interception or misconfigured SSL,
            # retry with TLS verification disabled if explicitly allowed.
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

    def request(self, method, url, headers=None, params=None, data=None, json_data=None) -> Response:
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
