import scrapy
import json
import logging
import redis
from rustore.items import MapfinderItem
from rustore.redis_settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_password

BATCH_SIZE = 100


class MapsearchSpider(scrapy.Spider):
    name = "mapsearch"
    allowed_domains = ["google.com"]

    def start_requests(self):
        redis_conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_password)
        urls_batch = self.get_urls_batch(redis_conn)

        while urls_batch:
            for url in urls_batch:
                page_url = url.split('|URLH|')[1]
                key_url = url.split('|URLH|')[0]
                yield scrapy.Request(url=page_url,
                                     callback=self.parse,
                                     meta={'key_url': key_url})
            urls_batch = self.get_urls_batch(redis_conn)

    def get_urls_batch(self, redis_conn):
        urls_batch = []
        for _ in range(BATCH_SIZE):
            url = redis_conn.lpop('url')
            if url:
                urls_batch.append(url.decode('utf-8'))
            else:
                break
        return urls_batch

    def parse(self, response):
        try:
            if response.text[:11] == '{"c":0,"d":':
                page_data = json.loads(response.text[:-6])
                text = page_data["d"][4:].strip()
            else:
                text = response.text[4:].strip()
            data = json.loads(text)
            listings = data[0][1]
            key_url = response.meta.get('key_url', False)
            item = MapfinderItem()
            item['key_url'] = key_url
            for listing in listings:
                if len(listing) > 14:
                    item["placeid"] = listing[14][78]
                    item["datafid"] = listing[14][10]
                    item["name"] = listing[14][11]
                    item["address"] = listing[14][39]
                    item["city"] = listing[14][166]
                    try:
                        item["country"] = listing[14][30]
                    except:
                        item["country"] = ''
                    try:
                        item["website"] = listing[14][7][0]
                    except:
                        item["website"] = ''

                    try:
                        lat = listing[14][9][2]
                        lon = listing[14][9][3]
                        item["latlon"] = f"{lat},{lon}"
                    except:
                        item["latlon"] = ''

                    try:
                        item["booking_link"] = listing[14][75][0][0][2][0][1][2][1][0]
                    except:
                        item["booking_link"] = ''

                    try:
                        item["phone"] = listing[14][178][0][1][1][0]
                    except:
                        item["phone"] = ''

                    try:
                        item["rating"] = listing[14][4][7]
                    except:
                        item["rating"] = 0

                    try:
                        item["reviews"] = listing[14][4][8]
                    except:
                        item["reviews"] = 0
                    item["categories"] = ', '.join(item[0] for item in listing[14][76])
                    yield item
            if len(listings) > 20:
                page = response.meta.get('page', False)
                if not page:
                    next_url = response.url.replace('!7i20!10b1!', '!7i20!8i20!10b1!')
                    page = 20
                else:
                    current_page = page
                    page += 20
                    next_url = response.url.replace(f'!7i20!8i{current_page}!10b1!', f'!7i20!8i{page}!10b1!')
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={'page': page, 'key_url': key_url}
                )
        except json.JSONDecodeError as e:
            logging.error(f"JSON error: {e}")
