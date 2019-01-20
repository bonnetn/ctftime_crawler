# coding=utf-8
"""
Crawl pwn write-ups.
"""
import logging
import random
import sys
import time
from collections import namedtuple
from multiprocessing.pool import ThreadPool
from pprint import pprint

import requests
from lxml import html

PARALLEL_REQ = 7  # connections in parallel to the website.
MAX_RETRIES = 15  # Max retries for a piece of information.

BASE_URL = 'https://ctftime.org'
FIREFOX_USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36')
HEADERS = {
    'user-agent': FIREFOX_USER_AGENT,
}

RowInformation = namedtuple('RowInformation', ['ctf', 'challenge', 'link'])


class CouldNotFetchInformation(Exception):
    """
    Transient error thrown when can't reach the website.
    """
    pass


def get_all_writetups():
    """
    Retrieve all the pwn write-ups from CTFtime, with their names and links.
    :return: the writeups meta data
    """
    response = requests.get(BASE_URL + '/writeups?tags=pwn&hidden-tags=pwn', headers=HEADERS)
    assert_status_200(response.status_code)

    tree = html.fromstring(response.content)
    rows = tree.xpath("//table[@id='writeups_table']/tbody/tr")
    logging.info("Fetched the write-ups list.")

    with ThreadPool(PARALLEL_REQ) as pool:
        info = pool.map(extract_info, rows)
    logging.info("Retrieved the information for each challenge.")

    return info


def extract_info(row):
    """
    Given a lxml row, fetch all the information for the CTF challenge.
    :param row: HtmlElement
    :return: a RowInformation object
    """
    ctf = row.xpath("td[1]/a/text()")[0]
    challenge = row.xpath("td[2]/a/text()")[0]
    link = row.xpath("td[5]/a")[0].get("href")

    for i in range(MAX_RETRIES):
        try:
            url = get_writeup_url(BASE_URL + link)
            logging.debug("Fetched info for {} - {}.".format(ctf, challenge))
            return RowInformation(ctf, challenge, url)
        except CouldNotFetchInformation:
            wait_time = (2 ** (i + random.random())) / 1000  # exponential backoff.
            logging.debug("Failed to request information. Retrying in {:.0f}ms.".format(wait_time * 1000))
            time.sleep(wait_time)

    raise CouldNotFetchInformation(
        "Could not fetch write-up URL ({} - {}) information after {} retries.".format(ctf, challenge, MAX_RETRIES))


def get_writeup_url(url):
    """
    Fetch the "real" write-up URL.

    Look at the description and at the 'original writeup" link in order to figure out where the "real" writeup is.
    Useful for write-ups that are hosted on github.
    :param url: CTFtime write-up link
    :return: real url
    """
    response = requests.get(url, headers=HEADERS)
    assert_status_200(response.status_code)

    tree = html.fromstring(response.content)

    # Try to get a URL in the description.
    description = tree.xpath("//div[@id='id_description']/p/a")
    if description:
        return description[0].get("href")

    # Otherwise use the original writeup URL.
    original_writeup = tree.xpath("//a[text()='Original writeup']")
    if original_writeup:
        return original_writeup[0].get("href")

    return url


def assert_status_200(status):
    """
    Assert that status is equal to 200, if not, throw an exception.
    :param status: integer status
    """
    if status != 200:
        raise CouldNotFetchInformation("Excpected status_code = 200, got {}".format(status))


def configure_logger():
    """
    Configure the root logger.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)


if __name__ == '__main__':
    configure_logger()
    try:
        info = get_all_writetups()
    except CouldNotFetchInformation:
        logging.exception("Could not fetch the write-ups.")

    print("=" * 100)
    pprint(info)
