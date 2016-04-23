#!/usr/bin/python
# -*- coding: utf-8 -*-

__version__ = "1.0.0"

from abc import ABCMeta
from cl_scraper import *
from lxml import html
from utils import prompt, retry

import argparse
import csv
import functools
import logging
import requests
import os
import time


class CLJobScraper(CLScraper):
    """ Scrapes Craiglist for job listings and outputs them into CSVs. """
    __metaclass__ = ABCMeta

    DOMAINS_ROOT_FILENAME = "domains"
    JOB_LINKS_ROOT_FILENAME = "job_links"

    @property
    def scrape_types(self):
        return ("scrape_domains", "scrape_all_jobs", "scrape_job_details")

    @csv_out(root_filename=DOMAINS_ROOT_FILENAME, header=("City", "Domain"))
    def scrape_domains(self):
        """ Scrape for all Craigslist domains and output into CSV files.

        :returns: Generator yielding Craiglist cities & links to their listings
        :rtype: generator<str, str>
        """
        DOMAINS_ENDPOINT = "http://www.craigslist.org/about/sites"
        DOMAIN_XPATH = ".//div[contains(@class, 'box')]//a"

        logger.debug("Scraping domains, hitting endpoint %s", DOMAINS_ENDPOINT)

        res = retry(functools.partial(requests.get, DOMAINS_ENDPOINT), SLEEP_TIME)

        doc = html.fromstring(res.text)

        for anchor_elem in doc.xpath(DOMAIN_XPATH):
            href = "http:{}".format(anchor_elem.get("href"))
            city = anchor_elem.text

            yield city, href

    @csv_out(root_filename="job_details", header=("Title", "Company", "Latitude", "Longitude"))
    def scrape_job_details(self):
        """ Scrape all job details iteratively from what we already have.

        :returns: Generator yielding Craiglist job details
        :rtype: generator<str, str, str, str>
        """
        logger.debug("Scraping job details")

        job_detail_files = get_matching_csv_files(CLJobScraper.JOB_LINKS_ROOT_FILENAME)
        if not job_detail_files:
            logger.debug("No files found with root filename %s", CLJobScraper.JOB_LINKS_ROOT_FILENAME)
        else:
            for filename in job_detail_files:
                with open(filename, "rb") as csv_file:
                    csv_reader = csv.reader(csv_file)
                    header = csv_reader.next()

                    for row in csv_reader:
                        res = scrape_single_job_details(row[0])
                        if res is not None:
                            yield res,

                        logger.debug("Sleeping Zzz")
                        time.sleep(SLEEP_TIME) # sleep to avoid being blacklisted

    def scrape_single_job_details(self, endpoint):
        """ Scrapes a single job's page for details.

        :param endpoint: The endpoint where to get job details from
        :type endpoint: str

        :returns: Job details including title, company, latitude, and longitude
        :rtype: tuple
        """

        TITLE_XPATH = ".//span[@id='titletextonly']"
        MAP_XPATH = ".//div[@id='map']"

        title = company = latitude = longitude = None

        try:
            logger.debug("Hitting single job endpoint %s", endpoint)
            res = retry(functools.partial(requests.get, endpoint), SLEEP_TIME)

            # parse results
            doc = html.fromstring(res.text)

            title_elem = doc.find(TITLE_XPATH)
            if title_elem is not None:
                title = title_elem.text
            else:
                raise MissingDataException("Title is missing from job listing")

            company = "A Company That's Hiring" # XXX no reliable way to parse this from CL

            map_elem = doc.find(MAP_XPATH)
            if map_elem is not None:
                latitude = map_elem.get("data-latitude")
                longitude = map_elem.get("data-longitude")
            else:
                raise MissingDataException("Map coordinates are missing from job listing")

            return title, company, latitude, longitude
        except MissingDataException: # raises are for failing fast
            pass
        except Exception:
            logger.exception("Encountered an issue while scraping single job details", exc_info=True)

    @csv_out(root_filename=JOB_LINKS_ROOT_FILENAME, header=("Listing URL",))
    def scrape_jobs(self, domain):
        """ Scrape all jobs iteratively through this domain.

        :param domain: Domain to scan jobs from
        :type domain: str

        :returns: Generator yielding Craiglist job links to their listings
        :rtype: generator<str>
        """
        JOB_XPATH = (".//div[contains(@class, 'content')]"
                      "//p[contains(@class, 'row')]")
        MAP_TAG_XPATH = ".//span[@class='maptag']"
        JOB_LINK_XPATH = ".//a[@class='hdrlnk']"
        MAX_RESULTS = 100

        payload = {"employment_type": "1", "s": 1}

        endpoint = os.path.join(domain, "search", "jjj")
        logger.debug("Hitting jobs endpoint %s w/payload %s", endpoint, payload)

        res = retry(functools.partial(requests.get, endpoint, params=payload), SLEEP_TIME)

        while True:
            try:
                # parse results
                doc = html.fromstring(res.text)

                listings = doc.xpath(JOB_XPATH)
                if not listings:
                    logger.debug("Paginated scraping complete")
                    break

                logger.debug("%s listings found", len(listings))
                for listing in listings:
                    # this signifies we can get the lat & long when drilling
                    if listing.find(MAP_TAG_XPATH) is not None:
                        anchor_elem = listing.find(JOB_LINK_XPATH)
                        link = "{}{}".format(domain, anchor_elem.get("href")[1:]) # slice off the leading slash

                        yield link,
            except Exception:
                logger.exception("Encountered an issue while scraping jobs", exc_info=True)
            finally:
                if len(listings) < MAX_RESULTS:
                    logger.debug("Paginated scraping complete")
                    break

                payload["s"] += MAX_RESULTS

                logger.debug("Sleeping Zzz")
                time.sleep(SLEEP_TIME) # sleep to avoid being blacklisted
                logger.debug("Hitting jobs endpoint %s w/payload %s", endpoint, payload)
                res = retry(functools.partial(requests.get, endpoint, params=payload), SLEEP_TIME)

    def scrape_all_jobs(self):
        """ Scrape for all Craigslist jobs and output into CSV files.
              In interactive mode, single-domain parsing is allowed.
        """
        logger.debug("Scraping jobs")

        jobs_files = get_matching_csv_files(CLJobScraper.DOMAINS_ROOT_FILENAME)
        if not jobs_files :
            logger.debug("No files found with root filename %s", CLJobScraper.DOMAINS_ROOT_FILENAME)

        all_domains = []
        for filename in jobs_files:
            with open(filename, "rb") as csv_file:
                csv_reader = csv.reader(csv_file)
                header = csv_reader.next()

                for row in csv_reader:
                    city, domain = row
                    all_domains.append(domain)

        if self.is_interactive:
            res = prompt("Scrape all domains?", ("y","N"))
            if res == "N":
                print_str = ""
                for i, domain in enumerate(all_domains, start=1):
                    print_str += "{:<3}. {:<50}".format(i, domain)

                    # 2 domains per line
                    if not(i % 2):
                        print(print_str)
                        print_str = ""

                print("")
                res = prompt("What domain do you want to scrape?")
                try:
                    all_domains = [all_domains[int(res)-1]]
                except (IndexError, ValueError):
                    raise ValueError("Invalid number provided")

        for domain in all_domains:
            self.scrape_jobs(domain)


def main():
    """ Module's main method, to be easily packagable. """
    logger.info("Craigslist Job Scraper, v%s", __version__)

    parser = argparse.ArgumentParser(description="Craigslist Jobs Scraper, v{}".format(__version__))

    parser.add_argument("-a", "--all", action="store_true", help="Run all scraping commands serially")
    parser.add_argument("-t", "--type", action="append",
                        help="Specify the type(s) of scrapings to do (see CLJobScraper.scrape_types property)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Run in verbose mode")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    cls = CLJobScraper(is_interactive=True, scrape_types=args.type)
    cls.run()


if __name__ == "__main__":
    main()
