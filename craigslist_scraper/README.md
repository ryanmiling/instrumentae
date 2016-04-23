# craigslist scraper
Back-end application that will scrape Craigslist for jobs, etc. and upon transformation will output the data into CSV files.

## Jobs Scrape Runtime analysis
100 jobs per job listing page
~2000 jobs per city
20 pages need to be processed per city
714 cities
30s sleep per request + ~2s to parse = 32s per job listing result page
30s sleep per request + ~1s to parse = 31s per job page

714 * 20 * 32 = 456960s = 127h = 5.28d to scrape all job URLs
456960 * 31 = 14165760s = 3935h = 163d to get all job data

Therefore, we need to multi-process this or focus on a subset of domains.
