"""
File to create the BaseScraper class.
"""

from io import StringIO
import time
import random

import pandas as pd
import requests
import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc

import logging

logging.basicConfig(level=logging.INFO)


import json
import os
from tqdm import tqdm
import selenium
import re

# Constants
HEADERS_FILE = "./backend/scraper/headers.yml"
USER_AGENTS_FILE = "./backend/scraper/user_agents.yml"
FREE_PROXY_URL = "https://free-proxy-list.net"

# if ./backend/scraper/data/ does not exist, create it
if not os.path.exists("./backend/scraper/data/"):
    os.makedirs("./backend/scraper/data/")

class BaseScraper:
    """Base class for scraping."""

    def __init__(
        self,
        headful: bool = False,
        verbose: bool = False,
        driver_type: str = "undetected",
        use_proxy: bool = True,
    ):
        self.headless = not headful
        self.verbose = verbose
        self.driver_type = driver_type
        self.use_proxy = use_proxy

        self.browser_headers = self._load_browser_headers()
        self.user_agents = self._load_user_agents()
        if self.use_proxy:
            self._get_good_proxies()
        self.driver = None

    @staticmethod
    def _load_browser_headers():
        """Load headers from the headers.yml file."""
        with open(HEADERS_FILE, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    @staticmethod
    def _load_user_agents():
        """Load user-agents from the user_agents.yml file."""
        with open(USER_AGENTS_FILE, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def _get_good_proxies(self):
        """Get a list of good proxies from https://free-proxy-list.net."""
        if self.verbose:
            logging.info("Getting good proxies...")
        try:
            response = requests.get(FREE_PROXY_URL, timeout=5)
            proxy_list = pd.read_html(StringIO(response.text))[0]
            proxy_list["url"] = "http://" + proxy_list["IP Address"] + ":" + proxy_list["Port"].astype(str)
            https_proxies = proxy_list[proxy_list["Https"] == "yes"]
            url = "https://httpbin.org/ip"
            # Test if self.good_proxies exists
            if not hasattr(self, "good_proxies"):
                self.good_proxies = set()
            headers = self.browser_headers["Chrome"]
            for proxy_url in https_proxies["url"]:
                proxies = {
                    "http": proxy_url,
                    "https": proxy_url,
                }

                try:
                    response = requests.get(url, headers=headers, proxies=proxies, timeout=2)
                    self.good_proxies.add(proxy_url)
                    if self.verbose:
                        logging.info("Proxy %s OK, added to good_proxy list", proxy_url)
                except (TimeoutException, requests.exceptions.RequestException):
                    pass

            # Add a variable to save the time
            self.proxies_time = time.time()

        except (TimeoutException, requests.exceptions.RequestException) as e:
            logging.error("Error getting proxies: %s", e)

    def _get_random_header(self, browser_type):
        """Get a random header and user-agent for the specified browser type."""
        header = self.browser_headers[browser_type]
        user_agent = random.choice(self.user_agents[browser_type])
        header["User-Agent"] = user_agent
        return header

    def _get_random_wait_time(self):
        """Get a random wait time between 0.01 and 1 second."""
        return random.uniform(0.001, 0.01) if self.headless else 0.5

    def _setup_driver(self):
        """Set up the browser driver."""
        if self.verbose:
            logging.info("Setting up %s driver...", self.driver_type)
        
        # First quit the previous driver if it exists
        if self.driver:
            if self.verbose:
                logging.info("Quitting existing driver...")
            self.driver.quit()

        browser_type = "Chrome" if self.driver_type == "undetected" else self.driver_type.capitalize()
        if self.verbose:
            logging.info("Getting random header for %s...", browser_type)
        header = self._get_random_header(browser_type)

        if self.use_proxy:
            if self.verbose:
                logging.info("Setting up proxy...")
            # Reload the proxies if the time is more than 10 minutes
            if time.time() - self.proxies_time > 600:
                if self.verbose:
                    logging.info("Proxies are stale, refreshing...")
                self._get_good_proxies()

            if hasattr(self, 'good_proxies') and self.good_proxies:
                proxy_url = random.choice(list(self.good_proxies))
                proxy = proxy_url.replace("http://", "")
                if self.verbose:
                    logging.info("Using proxy: %s", proxy)
            else:
                if self.verbose:
                    logging.warning("No good proxies available, proceeding without proxy")
                self.use_proxy = False

        options = None
        match self.driver_type:
            case "Firefox":
                if self.verbose:
                    logging.info("Initializing Firefox driver...")
                options = webdriver.FirefoxOptions()
                if self.headless:
                    options.add_argument("--headless")
                profile = webdriver.FirefoxProfile()
                for key, value in header.items():
                    profile.set_preference("general.useragent.override", header["User-Agent"])
                    profile.set_preference(f"{key}", value)
                options.profile = profile
                if self.use_proxy:
                    options.add_argument(f"--proxy-server={proxy}")
                return webdriver.Firefox(options=options)

            case "Chrome":
                if self.verbose:
                    logging.info("Initializing Chrome driver...")
                options = webdriver.ChromeOptions()
                if self.headless:
                    options.add_argument("--headless")
                for key, value in header.items():
                    options.add_argument(f"{key}={value}")
                if self.use_proxy:
                    options.add_argument(f"--proxy-server={proxy}")
                return webdriver.Chrome(options=options)

            case "undetected":
                if self.verbose:
                    logging.info("Initializing undetected Chrome driver...")
                options = uc.ChromeOptions()
                options.add_argument("--uc=True")
                if self.headless:
                    options.add_argument("--headless=True")
                for key, value in header.items():
                    options.add_argument(f"{key}={value}")
                if self.use_proxy:
                    options.add_argument(f"--proxy-server={proxy}")
                driver = uc.Chrome(options=options)
                if self.verbose:
                    logging.info("Undetected Chrome driver initialized successfully")
                return driver

            case _:
                raise ValueError("Invalid driver type")

    def __del__(self):
        """Clean up the driver when the scraper is deleted."""
        if self.driver:
            self.driver.quit()
            
"""Scraper to extract models from the PartSelect website."""


# Constants
BASE_URL = "https://www.partselect.com/"
CATEGORIES = [
    "Dishwasher",
    "Refrigerator",    
]

class ModelsScraper(BaseScraper):
    """Class to scrape models/parts on the PartSelect website."""

    def get_number_of_models(self):
        """Extract the total number of models from the summary element, or count parts directly."""
        if self.verbose:
            logging.info("Attempting to find summary element to get number of models...")
        
        # First check if this is a parts page by looking for parts elements
        try:
            part_elements = self.driver.find_elements(By.CLASS_NAME, "nf__part")
            if part_elements:
                # This is a parts page
                if self.verbose:
                    logging.info("Detected parts page with %d parts", len(part_elements))
                return len(part_elements)
        except:
            pass
        
        # Try to find summary element for models pages
        try:
            summary = self.driver.find_element(By.CLASS_NAME, "summary")
            if self.verbose:
                logging.info("Found summary element: %s", summary.text)
            total_models_text = summary.text.split()[-1]
            total_models = int(total_models_text.replace(',', ''))  # Convert to integer after removing commas
            if self.verbose:
                logging.info("Extracted total models: %d", total_models)
            return total_models
        except selenium.common.exceptions.NoSuchElementException:
            logging.error("No summary found: cannot determine the number of models.")
            return 0
        except (TimeoutException, ValueError) as e:
            if self.verbose:
                logging.error("Error finding number of models: %s", e)
            return 0  # Default to 0 models if there's an error
        except selenium.common.exceptions.StaleElementReferenceException as e:
            if self.verbose:
                logging.error("Exception raised: %s", e)
            return 0  # Default to 0 models if there's an error

    def get_number_of_models_and_pages(self, models_per_page=100):
        # """Calculate the number of pages based on the total number of models."""
        if self.verbose:
            logging.info("Getting number of models and calculating pages...")
        n_models = self.get_number_of_models()
        
        # For parts pages, we typically only have one page
        # Check if this is a parts page
        try:
            part_elements = self.driver.find_elements(By.CLASS_NAME, "nf__part")
            if part_elements:
                # This is a parts page - typically single page
                n_pages = 1 if n_models > 0 else 0
                if self.verbose:
                    logging.info("Parts page detected - using single page approach")
            else:
                # This is a models page - use pagination
                n_pages = 0 if n_models == 0 else (n_models + models_per_page - 1) // models_per_page
        except:
            n_pages = 0 if n_models == 0 else (n_models + models_per_page - 1) // models_per_page
        
        if self.verbose:
            logging.info("Calculated %d pages for %d models", n_pages, n_models)
        return n_pages, n_models
    
    def scrape_models_on_page(self):
        """Extract all items (models or parts) listed on the current page."""
        if self.verbose:
            logging.info("Starting to scrape items on current page...")
        
        # First check if this is a parts page
        try:
            part_elements = self.driver.find_elements(By.CLASS_NAME, "nf__part")
            if part_elements:
                return self._scrape_parts_on_page(part_elements)
        except:
            pass
        
        # Try to scrape as models page
        return self._scrape_models_on_page()
    
    # def _scrape_parts_on_page(self, part_elements):
    #     """Extract dishwasher parts from the page."""
    #     if self.verbose:
    #         logging.info("Scraping parts page with %d part elements", len(part_elements))
        
    #     parts = []
    #     for i, part_div in enumerate(part_elements):
    #         if self.verbose and i % 5 == 0:  # Log every 5th item to avoid spam
    #             logging.info("Processing part element %d/%d", i+1, len(part_elements))
            
    #         try:
    #             # Find the title link within the part detail section
    #             title_link = part_div.find_element(By.CSS_SELECTOR, ".nf__part__detail__title")
    #             part_name = title_link.find_element(By.TAG_NAME, "span").text
    #             part_url = title_link.get_attribute("href")
                
    #             # Extract additional information
    #             try:
    #                 # Get part number information
    #                 part_number_elements = part_div.find_elements(By.CSS_SELECTOR, ".nf__part__detail__part-number strong")
    #                 partselect_number = part_number_elements[0].text if len(part_number_elements) > 0 else ""
    #                 manufacturer_number = part_number_elements[1].text if len(part_number_elements) > 1 else ""
                    
    #                 # Get price
    #                 try:
    #                     price_element = part_div.find_element(By.CSS_SELECTOR, ".price")
    #                     price = price_element.text
    #                 except:
    #                     price = ""
                    
    #                 # Get stock status
    #                 try:
    #                     stock_element = part_div.find_element(By.CSS_SELECTOR, ".nf__part__left-col__basic-info__stock span")
    #                     stock_status = stock_element.text.strip()
    #                 except:
    #                     stock_status = ""
                        
    #             except Exception as detail_error:
    #                 if self.verbose:
    #                     logging.warning("Could not extract detailed info for part %d: %s", i+1, detail_error)
    #                 partselect_number = ""
    #                 manufacturer_number = ""
    #                 price = ""
    #                 stock_status = ""
                
    #             parts.append({
    #                 "name": part_name,
    #                 "url": part_url,
    #                 "description": part_name,  # Using name as description for consistency
    #                 "partselect_number": partselect_number,
    #                 "manufacturer_number": manufacturer_number,
    #                 "price": price,
    #                 "stock_status": stock_status
    #             })
                
    #         except Exception as part_error:
    #             if self.verbose:
    #                 logging.warning("Could not extract part %d: %s", i+1, part_error)
    #             continue

    #     if self.verbose:
    #         logging.info("Successfully scraped %d parts from current page", len(parts))
    #     return parts
    def _extract_image_url(self, part_div):
        """
        Extract the image URL from a part div, handling both regular and lazy-loaded images.
        
        Args:
            part_div: The Selenium element representing the part div
            
        Returns:
            str: The URL of the image, or None if not found
        """
        try:
            # First try to find the picture element
            picture_elem = part_div.find_element(By.CSS_SELECTOR, "picture")
            if not picture_elem:
                return None
                
            # Try to get the img element inside the picture element
            img_elem = picture_elem.find_element(By.TAG_NAME, "img")
            if not img_elem:
                return None
                
            # First check if the image is already loaded (b-loaded class)
            if "b-loaded" in img_elem.get_attribute("class"):
                # Get the src attribute directly since the image is loaded
                image_url = img_elem.get_attribute("src")
                if image_url and not image_url.startswith("data:"):
                    return image_url
                    
            # If not loaded or src is data URI, try data-src (lazy loading)
            data_src = img_elem.get_attribute("data-src")
            if data_src and not data_src.startswith("data:"):
                return data_src
                
            # If still no URL, try to get from source elements
            source_elems = picture_elem.find_elements(By.TAG_NAME, "source")
            for source in source_elems:
                # Try regular srcset first (non-lazy loaded images)
                srcset = source.get_attribute("srcset")
                if srcset:
                    # Extract the first URL from the srcset attribute
                    urls = srcset.split(",")
                    if urls:
                        url = urls[0].strip().split(" ")[0].strip()
                        if url:
                            return url
                            
                # Try data-srcset for lazy loaded images
                data_srcset = source.get_attribute("data-srcset")
                if data_srcset:
                    # Extract the first URL from the data-srcset attribute
                    urls = data_srcset.split(",")
                    if urls:
                        url = urls[0].strip().split(" ")[0].strip()
                        if url:
                            return url
            
            return None
        except Exception as e:
            if self.verbose:
                logging.warning(f"Error extracting image URL: {str(e)}")
            return None

    def _scrape_parts_on_page(self, part_elements):
        """Extract dishwasher parts from the page."""
        if self.verbose:
            logging.info("Extracting parts from current page...")
        
        parts = []
        for i, part_div in enumerate(part_elements):
            try:
                part_data = {}
                
                # Extract part URL
                try:
                    part_link_elem = part_div.find_element(By.CSS_SELECTOR, ".nf__part__left-col__img a")
                    if part_link_elem:
                        part_data["url"] = part_link_elem.get_attribute("href")
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Unable to extract URL: {e}")

                # Extract image URL - call the new helper method
                image_url = self._extract_image_url(part_div)
                if image_url:
                    part_data["image_url"] = image_url
                elif self.verbose:
                    logging.warning(f"Part {i+1}: Could not extract image URL.")
                    
                # Extract title and part numbers
                try:
                    title_elem = part_div.find_element(By.CSS_SELECTOR, ".nf__part__detail__title span")
                    if title_elem:
                        part_data["name"] = title_elem.text.strip()

                    ps_number_elem = part_div.find_element(By.XPATH, ".//div[contains(text(), 'PartSelect Number')]/strong")
                    if ps_number_elem:
                        part_data["partselect_number"] = ps_number_elem.text.strip()

                    mfr_number_elem = part_div.find_element(By.XPATH, ".//div[contains(text(), 'Manufacturer Part Number')]/strong")
                    if mfr_number_elem:
                        part_data["manufacturer_number"] = mfr_number_elem.text.strip()
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Title/part number extraction error: {e}")

                # Extract description - get text content directly after part number divs
                try:
                    # Get all text nodes in the detail section, excluding nested elements
                    detail_div = part_div.find_element(By.CLASS_NAME, "nf__part__detail")
                    
                    # Get all the text content
                    full_text = detail_div.text
                    
                    # Remove known element texts
                    if part_data.get("name"):
                        full_text = full_text.replace(part_data["name"], "")
                    
                    # Remove part number texts
                    part_number_pattern = r"PartSelect Number.*\n"
                    full_text = re.sub(part_number_pattern, "", full_text)
                    
                    part_number_pattern = r"Manufacturer Part Number.*\n"
                    full_text = re.sub(part_number_pattern, "", full_text)
                    
                    # Remove "Fixes these symptoms" and everything after
                    symptoms_index = full_text.find("Fixes these symptoms")
                    if symptoms_index > 0:
                        full_text = full_text[:symptoms_index].strip()
                    
                    # Remove "Installation Instructions" and everything after
                    instructions_index = full_text.find("Installation Instructions")
                    if instructions_index > 0:
                        full_text = full_text[:instructions_index].strip()
                    
                    if full_text:
                        part_data["description"] = full_text.strip()
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Description extraction error: {e}")

                # Extract price
                try:
                    price_elem = part_div.find_element(By.CSS_SELECTOR, ".price")
                    if price_elem:
                        currency = price_elem.find_element(By.CSS_SELECTOR, ".price__currency").text
                        price_text = price_elem.text.replace(currency, "").strip()
                        part_data["price"] = f"{currency}{price_text}"
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Price extraction error: {e}")

                # Extract stock status
                try:
                    stock_elem = part_div.find_element(By.CSS_SELECTOR, ".nf__part__left-col__basic-info__stock span")
                    if stock_elem:
                        part_data["stock_status"] = stock_elem.text.strip()
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Stock status extraction error: {e}")

                # Extract rating info
                try:
                    rating_elem = part_div.find_element(By.CSS_SELECTOR, ".nf__part__detail__rating")
                    if rating_elem:
                        alt_text = rating_elem.get_attribute("alt")
                        if alt_text and "out of 5" in alt_text:
                            part_data["rating"] = alt_text

                    review_count_elem = part_div.find_element(By.CSS_SELECTOR, ".rating__count")
                    if review_count_elem:
                        match = re.search(r'\d+', review_count_elem.text)
                        if match:
                            part_data["reviews_count"] = int(match.group(0))
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Part {i+1}: Rating extraction error: {e}")
                # Only add parts with at least name or URL
                if part_data.get("name") or part_data.get("url"):
                    parts.append(part_data)
                    if self.verbose and i % 10 == 0:
                        logging.info(f"Processed part {i+1}: {part_data.get('name', 'Unknown')}")
                        
            except Exception as e:
                if self.verbose:
                    logging.warning(f"Part {i+1}: General error: {e}")

        if self.verbose:
            logging.info(f"Extracted {len(parts)} parts from page")
        
        return parts

    def scrape_single_part_details(self, url):
        """Scrape detailed information from a single part page, including reviews, repair stories, videos and troubleshooting info."""
        try:
            self.driver.get(url)
            time.sleep(self._get_random_wait_time())  # Allow page to load
            
            # Initialize the result dictionary with new fields
            part_details = {
                "name": "",
                "part_number": "",
                "price": "",
                "rating": "",
                "reviews_count": 0,
                "reviews": [],
                "repair_stories": [],
                "videos": [],            # New field for videos
                "symptoms_fixed": "",    # New field for symptoms
                "works_with": "",        # New field for product compatibility
                "also_replaces": []      # New field for replacement parts
            }
            
            # Get basic part details (existing code)
            try:
                part_details["name"] = self.driver.find_element(By.CSS_SELECTOR, "h1.title-lg").text
            except Exception as e:
                if self.verbose:
                    logging.warning("Could not find part name: %s", e)
            
            try:
                part_details["part_number"] = self.driver.find_element(By.CSS_SELECTOR, "div.mb-2 span[itemprop='mpn']").text.strip()
            except Exception as e:
                if self.verbose:
                    logging.warning("Could not find part number: %s", e)
            
            try:
                price_element = self.driver.find_element(By.CSS_SELECTOR, "span.price.pd__price")
                part_details["price"] = price_element.text.strip()
            except Exception as e:
                if self.verbose:
                    logging.warning("Could not find part price: %s", e)
            
            try:
                # Get rating
                rating_div = self.driver.find_element(By.CSS_SELECTOR, "div.rating__stars__upper")
                style = rating_div.get_attribute("style")
                if "width:" in style:
                    width_percent = style.split("width:")[1].split("%")[0].strip()
                    rating_value = float(width_percent) / 20  # Convert percentage to 5-star scale
                    part_details["rating"] = f"{rating_value:.1f}/5"
                
                # Get number of reviews
                reviews_count_element = self.driver.find_element(By.CSS_SELECTOR, "span.rating__count")
                reviews_text = reviews_count_element.text.strip()
                if "Reviews" in reviews_text:
                    reviews_count = int(reviews_text.split(" ")[0])
                    part_details["reviews_count"] = reviews_count
            except Exception as e:
                if self.verbose:
                    logging.warning("Could not find rating information: %s", e)
            
            # Extract part videos - NEW CODE
            try:
                # Try to find the Part Videos section
                try:
                    # Click on the Part Videos section to ensure it's loaded
                    videos_section = self.driver.find_element(By.XPATH, "//div[@id='PartVideos']")
                    videos_section.click()
                    time.sleep(0.5)  # Short delay to let content load
                except Exception:
                    if self.verbose:
                        logging.info("No separate Part Videos section found, continuing...")
                
                # Look for video elements
                video_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.yt-video")
                
                for video in video_elements:
                    video_data = {}
                    
                    # Extract video title from heading before the video
                    try:
                        # Try to find the title in the heading above the video
                        title_element = video.find_element(By.XPATH, "./preceding-sibling::h4[1]")
                        video_data["title"] = title_element.text.strip()
                    except Exception:
                        # If no heading found, try alternative approaches or set default
                        try:
                            # Try getting the image alt text as title
                            img_element = video.find_element(By.TAG_NAME, "img")
                            video_data["title"] = img_element.get_attribute("title") or img_element.get_attribute("alt") or "Untitled Video"
                        except:
                            video_data["title"] = "Untitled Video"
                    
                    # Extract YouTube video ID
                    try:
                        # First try the data-yt-init attribute which usually contains the YouTube ID
                        youtube_id = video.get_attribute("data-yt-init")
                        if not youtube_id:
                            # If not found, try getting it from the image src
                            img_element = video.find_element(By.TAG_NAME, "img")
                            img_src = img_element.get_attribute("src")
                            if "youtube.com/vi/" in img_src:
                                # Extract ID from YouTube thumbnail URL
                                youtube_id = img_src.split("/vi/")[1].split("/")[0]
                        
                        if youtube_id:
                            video_data["youtube_id"] = youtube_id
                            video_data["video_url"] = f"https://www.youtube.com/watch?v={youtube_id}"
                            # Also store the thumbnail URL
                            video_data["thumbnail_url"] = f"https://img.youtube.com/vi/{youtube_id}/maxresdefault.jpg"
                    except Exception as e:
                        if self.verbose:
                            logging.warning(f"Could not extract video URL: {e}")
                    
                    # Add to videos list if we have at least an ID or URL
                    if "youtube_id" in video_data or "video_url" in video_data:
                        part_details["videos"].append(video_data)
                        
            except Exception as e:
                if self.verbose:
                    logging.warning(f"Error extracting part videos: {e}")
            
            # Extract troubleshooting information - FIXED CODE
            try:
                # Try to find the Troubleshooting section
                try:
                    # Click on the Troubleshooting section to ensure it's loaded
                    troubleshooting_section = self.driver.find_element(By.XPATH, "//div[@id='Troubleshooting']")
                    troubleshooting_section.click()
                    time.sleep(0.5)  # Short delay to let content load
                except Exception:
                    if self.verbose:
                        logging.info("No separate Troubleshooting section found, continuing...")
                
                # Get symptoms this part fixes - IMPROVED SELECTORS
                try:
                    # Try multiple selector approaches
                    symptoms_div = None
                    
                    # First try: Look for the div with the title followed by the content in the same parent
                    try:
                        symptoms_container = self.driver.find_element(
                            By.XPATH, 
                            "//div[contains(text(), 'This part fixes the following symptoms:')]/parent::div"
                        )
                        # Get the text excluding the heading
                        full_text = symptoms_container.text
                        symptoms_text = full_text.replace("This part fixes the following symptoms:", "").strip()
                        part_details["symptoms_fixed"] = symptoms_text
                    except Exception:
                        # Second try: Find the heading and then its following div or text
                        try:
                            symptoms_heading = self.driver.find_element(
                                By.XPATH, 
                                "//div[contains(@class, 'bold') and contains(text(), 'This part fixes the following symptoms:')]"
                            )
                            # Get the parent element and extract the text content after the heading
                            parent_div = symptoms_heading.find_element(By.XPATH, "./..")
                            full_text = parent_div.text
                            symptoms_text = full_text.replace("This part fixes the following symptoms:", "").strip()
                            part_details["symptoms_fixed"] = symptoms_text
                        except Exception:
                            # Third try: Direct approach for the specific HTML structure shown
                            try:
                                symptoms_container = self.driver.find_element(
                                    By.XPATH,
                                    "//div[@id='Troubleshooting']/following-sibling::div//div[contains(@class, 'col-md-6')][1]"
                                )
                                symptoms_heading = symptoms_container.find_element(By.XPATH, ".//div[contains(@class, 'bold')]")
                                symptoms_text = symptoms_container.text.replace(symptoms_heading.text, "").strip()
                                part_details["symptoms_fixed"] = symptoms_text
                            except Exception as e:
                                if self.verbose:
                                    logging.warning(f"Could not extract symptoms fixed (third attempt): {e}")
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Could not extract symptoms fixed: {e}")
                
                # Get what products this part works with - IMPROVED SELECTORS
                try:
                    # Similar multi-approach strategy
                    try:
                        works_with_container = self.driver.find_element(
                            By.XPATH, 
                            "//div[contains(text(), 'This part works with the following products:')]/parent::div"
                        )
                        full_text = works_with_container.text
                        works_with_text = full_text.replace("This part works with the following products:", "").strip()
                        part_details["works_with"] = works_with_text
                    except Exception:
                        try:
                            works_with_heading = self.driver.find_element(
                                By.XPATH, 
                                "//div[contains(@class, 'bold') and contains(text(), 'This part works with the following products:')]"
                            )
                            parent_div = works_with_heading.find_element(By.XPATH, "./..")
                            full_text = parent_div.text
                            works_with_text = full_text.replace("This part works with the following products:", "").strip()
                            part_details["works_with"] = works_with_text
                        except Exception:
                            # Direct approach for the specific HTML structure
                            try:
                                works_with_container = self.driver.find_element(
                                    By.XPATH,
                                    "//div[@id='Troubleshooting']/following-sibling::div//div[contains(@class, 'col-md-6')][2]"
                                )
                                works_with_heading = works_with_container.find_element(By.XPATH, ".//div[contains(@class, 'bold')]")
                                works_with_text = works_with_container.text.replace(works_with_heading.text, "").strip()
                                part_details["works_with"] = works_with_text
                            except Exception as e:
                                if self.verbose:
                                    logging.warning(f"Could not extract works with information (third attempt): {e}")
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Could not extract works with information: {e}")
                
                # Get parts this part replaces - IMPROVED SELECTORS
                try:
                    if part_details['part_number']:
                        try:
                            replaces_container = self.driver.find_element(
                                By.XPATH, 
                                f"//div[contains(text(), 'Part# {part_details['part_number']} replaces these:')]/parent::div"
                            )
                            
                            # Try to find the replacement parts in a div within the container
                            try:
                                replacements_div = replaces_container.find_element(By.XPATH, ".//div[contains(@data-collapse-container, 'targetClassToggle')]")
                                replaces_text = replacements_div.text
                            except Exception:
                                # If can't find the specific div, just get the text without the heading
                                full_text = replaces_container.text
                                replaces_text = full_text.replace(f"Part# {part_details['part_number']} replaces these:", "").strip()
                            
                            if replaces_text:
                                # Split by commas and clean up whitespace
                                part_details["also_replaces"] = [part.strip() for part in replaces_text.split(",")]
                        except Exception:
                            # Try the third column in the troubleshooting section
                            try:
                                replaces_container = self.driver.find_element(
                                    By.XPATH,
                                    "//div[@id='Troubleshooting']/following-sibling::div//div[contains(@class, 'col-md-6')][3]"
                                )
                                if replaces_container.is_displayed():
                                    replaces_heading = replaces_container.find_element(By.XPATH, ".//div[contains(@class, 'bold')]")
                                    replacements_div = replaces_container.find_element(By.XPATH, ".//div[contains(@data-collapse-container, 'targetClassToggle')]")
                                    if replacements_div:
                                        replaces_text = replacements_div.text
                                    else:
                                        replaces_text = replaces_container.text.replace(replaces_heading.text, "").strip()
                                    
                                    if replaces_text:
                                        # Split by commas and clean up whitespace
                                        part_details["also_replaces"] = [part.strip() for part in replaces_text.split(",")]
                            except Exception as e:
                                if self.verbose:
                                    logging.warning(f"Could not extract replacement part information (third attempt): {e}")
                except Exception as e:
                    if self.verbose:
                        logging.warning(f"Could not extract replacement part information: {e}")
                
            except Exception as e:
                if self.verbose:
                    logging.warning(f"Error extracting troubleshooting information: {e}")
                                
            # Extract customer reviews (existing code)
            try:
                # Click on the Customer Reviews section to ensure it's loaded
                reviews_section_link = self.driver.find_element(By.XPATH, "//a[contains(@href, '#CustomerReviews')]")
                reviews_section_link.click()
                time.sleep(1)
                
                # Find all review elements
                review_elements = self.driver.find_elements(By.CLASS_NAME, "pd__cust-review__submitted-review")
                
                for review in review_elements:
                    review_data = {}
                    
                    # Extract the rating
                    try:
                        rating_element = review.find_element(By.CLASS_NAME, "rating__stars__upper")
                        style = rating_element.get_attribute("style")
                        if "width:" in style:
                            width_percent = style.split("width:")[1].split("%")[0].strip()
                            rating_value = float(width_percent) / 20  # Convert percentage to 5-star scale
                            review_data["rating"] = f"{rating_value:.1f}/5"
                    except Exception as e:
                        review_data["rating"] = "N/A"
                        if self.verbose:
                            logging.warning("Could not extract review rating: %s", e)
                    
                    # Extract reviewer name and date
                    try:
                        header = review.find_element(By.CLASS_NAME, "pd__cust-review__submitted-review__header")
                        header_text = header.text.strip()
                        if " - " in header_text:
                            name, date = header_text.split(" - ", 1)
                            review_data["reviewer"] = name.strip()
                            review_data["date"] = date.strip()
                    except Exception as e:
                        review_data["reviewer"] = "Unknown"
                        review_data["date"] = "Unknown"
                        if self.verbose:
                            logging.warning("Could not extract reviewer info: %s", e)
                    
                    # Extract review title
                    try:
                        title_element = review.find_element(By.CLASS_NAME, "bold")
                        review_data["title"] = title_element.text.strip()
                    except Exception as e:
                        review_data["title"] = ""
                        if self.verbose:
                            logging.warning("Could not extract review title: %s", e)
                    
                    # Extract review text
                    try:
                        content_element = review.find_element(By.CLASS_NAME, "js-searchKeys")
                        review_data["content"] = content_element.text.strip()
                    except Exception as e:
                        review_data["content"] = ""
                        if self.verbose:
                            logging.warning("Could not extract review content: %s", e)
                    
                    # Add the review to our list
                    part_details["reviews"].append(review_data)
            
            except Exception as e:
                if self.verbose:
                    logging.warning("Error extracting customer reviews: %s", e)
            
            # Extract repair stories (existing code)
            try:
                # Click on the Repair Stories section to ensure it's loaded 
                repair_stories_link = self.driver.find_element(By.XPATH, "//a[contains(@href, '#RepairStories')]")
                repair_stories_link.click()
                time.sleep(1)
                
                # Find all repair story elements
                story_elements = self.driver.find_elements(By.CLASS_NAME, "repair-story")
                
                for story in story_elements:
                    story_data = {}
                    
                    # Extract story title
                    try:
                        title_element = story.find_element(By.CLASS_NAME, "repair-story__title")
                        story_data["title"] = title_element.text.strip()
                    except Exception as e:
                        story_data["title"] = ""
                        if self.verbose:
                            logging.warning("Could not extract repair story title: %s", e)
                    
                    # Extract story instructions
                    try:
                        instruction_element = story.find_element(By.CSS_SELECTOR, "div.repair-story__instruction div.js-searchKeys")
                        story_data["instructions"] = instruction_element.text.strip()
                    except Exception as e:
                        story_data["instructions"] = ""
                        if self.verbose:
                            logging.warning("Could not extract repair story instructions: %s", e)
                    
                    # Extract author information
                    try:
                        author_element = story.find_element(By.CSS_SELECTOR, "ul.repair-story__details li:nth-child(1) div.bold")
                        story_data["author"] = author_element.text.strip()
                    except Exception as e:
                        story_data["author"] = "Unknown"
                        if self.verbose:
                            logging.warning("Could not extract repair story author: %s", e)
                    
                    # Extract difficulty level
                    try:
                        difficulty_element = story.find_element(By.XPATH, ".//li[2]//div[contains(@class, 'bold')]/following-sibling::text() | .//li[2]//div[not(contains(@class, 'bold'))]")
                        story_data["difficulty"] = difficulty_element.text.strip()
                    except Exception as e:
                        try:
                            # Alternative approach using different selector
                            difficulty_div = story.find_element(By.XPATH, ".//li[2]/div/div[2]")
                            story_data["difficulty"] = difficulty_div.text.strip()
                        except:
                            story_data["difficulty"] = "Unknown"
                        if self.verbose:
                            logging.warning("Could not extract repair difficulty: %s", e)
                    
                    # Extract repair time
                    try:
                        time_element = story.find_element(By.XPATH, ".//li[3]//div[contains(@class, 'bold')]/following-sibling::text() | .//li[3]//div[not(contains(@class, 'bold'))]")
                        story_data["repair_time"] = time_element.text.strip()
                    except Exception as e:
                        try:
                            # Alternative approach using different selector
                            time_div = story.find_element(By.XPATH, ".//li[3]/div/div[2]")
                            story_data["repair_time"] = time_div.text.strip()
                        except:
                            story_data["repair_time"] = "Unknown"
                        if self.verbose:
                            logging.warning("Could not extract repair time: %s", e)
                    
                    # Extract helpfulness rating
                    try:
                        helpful_element = story.find_element(By.CLASS_NAME, "js-displayRating")
                        found_helpful = helpful_element.get_attribute("data-found-helpful")
                        vote_count = helpful_element.get_attribute("data-vote-count")
                        story_data["helpfulness"] = f"{found_helpful}/{vote_count}"
                    except Exception as e:
                        story_data["helpfulness"] = "N/A"
                        if self.verbose:
                            logging.warning("Could not extract helpfulness rating: %s", e)
                    
                    # Add the repair story to our list
                    part_details["repair_stories"].append(story_data)
                    
            except Exception as e:
                if self.verbose:
                    logging.warning("Error extracting repair stories: %s", e)
            
            return part_details
        
        except Exception as e:
            if self.verbose:
                logging.error("Error scraping single part page: %s", e)
            return {}        
        
    def _scrape_models_on_page(self):
        """Extract models from a models listing page."""
        if self.verbose:
            logging.info("Scraping models page...")
        try:
            # First check if this is a parts page
            try:
                part_elements = self.driver.find_elements(By.CLASS_NAME, "nf__part")
                if part_elements:
                    if self.verbose:
                        logging.info("Detected parts page format - using parts extraction method")
                    return self._scrape_parts_on_page(part_elements)
            except Exception as e:
                if self.verbose:
                    logging.info("Not a parts page format, continuing with models extraction: %s", e)
            
            # Continue with original model extraction logic
            models = []
            if self.verbose:
                logging.info("Looking for ul element with class 'nf__links'...")
            ul_element = self.driver.find_element(By.CLASS_NAME, "nf__links")
            if self.verbose:
                logging.info("Found ul element, looking for li elements...")
            li_elements = ul_element.find_elements(By.TAG_NAME, "li")
            if self.verbose:
                logging.info("Found %d li elements", len(li_elements))

            for i, li in enumerate(li_elements):
                if self.verbose and i % 10 == 0:  # Log every 10th item to avoid spam
                    logging.info("Processing li element %d/%d", i+1, len(li_elements))
                a_tag = li.find_element(By.TAG_NAME, "a")
                model_name = a_tag.get_attribute("title")
                model_url = a_tag.get_attribute("href")
                model_description = a_tag.text
                models.append(
                    {
                        "name": model_name,
                        "url": model_url,
                        "description": model_description,
                    }
                )

            if self.verbose:
                logging.info("Successfully scraped %d models from current page", len(models))
            return models
        except selenium.common.exceptions.NoSuchElementException as e:
            logging.error("No models found on the page: %s", e)
            return []
        except (TimeoutException, ValueError) as e:
            if self.verbose:
                logging.error("Error scraping models on page: %s", e)
            return []
        
    def scrape_models_with_details(self, n_pages: int, base_url: str, save_local=True, max_details=5):
        """
        Scrape models and get detailed information for a subset of them.
        
        Args:
            n_pages: Number of pages to scrape for models
            base_url: Base URL to start scraping from
            save_local: Whether to save results locally
            max_details: Maximum number of models to get detailed information for
        """
        if self.verbose:
            logging.info("Starting to scrape models with details from %s", base_url)
        
        # First get all models from the listing pages
        all_models = self.scrape_all_models(n_pages, base_url, save_local=False)
        
        if not all_models:
            if self.verbose:
                logging.warning("No models found at %s", base_url)
            return []
        
        # Get detailed information for a subset of models (to avoid excessive scraping)
        models_to_detail = all_models[:min(max_details, len(all_models))]
        
        if self.verbose:
            logging.info("Found %d models, getting detailed information for %d of them", 
                        len(all_models), len(models_to_detail))
        
        # For each model, get detailed information
        for i, model in enumerate(models_to_detail):
            if self.verbose:
                logging.info("Getting details for model %d/%d: %s", 
                            i+1, len(models_to_detail), model.get("name", "Unknown"))
            
            # Get the model URL
            model_url = model.get("url")
            if not model_url:
                if self.verbose:
                    logging.warning("No URL found for model %s, skipping", model.get("name", "Unknown"))
                continue
            
            # Get details for this model
            details = self.scrape_single_part_details(model_url)
            
            # Add details to the model
            model["details"] = details
            
            # Add a small delay between requests to avoid overloading the server
            time.sleep(self._get_random_wait_time() / 2)
        
        if save_local:
            # Extract category and brand from URL for filename
            url_parts = base_url.rstrip('/').split('/')
            filename_part = url_parts[-1] if url_parts else "unknown"
            # Remove .htm extension if present
            filename_part = filename_part.replace('.htm', '').replace('.html', '')
            
            # Create filename
            file_path = f"./backend/scraper/data/{filename_part}.json"
            if self.verbose:
                logging.info("Saving detailed data to JSON file %s...", file_path)
            
            # Save all models, including those with details
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(all_models, f, indent=2)
        
        return all_models
    
    def scrape_all_models(self, n_pages: int, base_url: str, save_local=True):
        """Scrape all models/parts across multiple pages."""
        if self.verbose:
            logging.info("Starting to scrape all items across %d pages from base URL: %s", n_pages, base_url)
        
        # Fix URL construction - remove extra slashes
        base_url = base_url.replace("///", "/")
        
        try:
            if not self.driver:
                if self.verbose:
                    logging.info("Setting up driver...")
                self.driver = self._setup_driver()
            
            if self.verbose:
                logging.info("Driver setup complete, navigating to base URL...")
            self.driver.get(base_url)
            wait_time = self._get_random_wait_time()
            if self.verbose:
                logging.info("Waiting %.3f seconds for page to load...", wait_time)
            time.sleep(wait_time)  # Allow page to load

            all_models = []

            # Check if this is a parts page (single page) or models page (multiple pages)
            try:
                part_elements = self.driver.find_elements(By.CLASS_NAME, "nf__part")
                is_parts_page = len(part_elements) > 0
            except:
                is_parts_page = False

            # if is_parts_page and n_pages == 1:
            #     # For parts pages, just scrape the current page
            #     if self.verbose:
            #         logging.info("Detected parts page - scraping single page")
            #     page_models = self.scrape_models_on_page()
            #     all_models.extend(page_models)
            # else:
            try:
                n_pages=100
                # For models pages, iterate through pages
                for i in tqdm(range(n_pages), desc=f"Scraping pages up to {n_pages}"):
                    if i == 0:
                        # Already on first page
                        url = base_url
                    else:
                        url = f"{base_url}?start={i+1}"
                    
                    page_source = self.driver.page_source
                    if "Reviews" not in page_source:
                        logging.info("No models found on page %d. Stopping further scraping.", i+1)
                        break
                    
                    if self.verbose:
                        logging.info("Processing page %d/%d - URL: %s", i+1, n_pages, url)
                    
                    if i > 0:  # Don't navigate away from first page
                        if self.verbose:
                            logging.info("Navigating to page %d...", i+1)
                        self.driver.get(url)
                        wait_time = self._get_random_wait_time()
                        if self.verbose:
                            logging.info("Waiting %.3f seconds for page %d to load...", wait_time, i+1)
                        time.sleep(wait_time)  # Allow page to load

                    if self.verbose:
                        logging.info("Scraping items from page %d...", i+1)
                    page_models = self.scrape_models_on_page()
                    all_models.extend(page_models)
                    if self.verbose:
                        logging.info("Page %d complete. Got %d items. Total so far: %d", i+1, len(page_models), len(all_models))
            except Exception as e:
                logging.error("Error scraping at page: %d. Error: \n%s", i, e)
                return []
            
            if self.verbose:
                logging.info("Finished scraping all pages. Total items collected: %d", len(all_models))

            if save_local:
                # Save the scraped data to a JSON file
                # Extract category and brand from URL
                url_parts = base_url.rstrip('/').split('/')
                filename_part = url_parts[-1] if url_parts else "unknown"
                # Remove .htm extension if present
                filename_part = filename_part.replace('.htm', '').replace('.html', '')
                
                file_path = f"./backend/scraper/data/{filename_part}_data.json"
                if self.verbose:
                    logging.info("Saving scraped data to JSON file %s...", file_path)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(all_models, f, indent=2)
                if self.verbose:
                    logging.info("Data saved successfully to %s", file_path)

            return all_models
        except (TimeoutException, ValueError) as e:
            if self.verbose:
                logging.error("Error scraping all models: %s", e)
            return []
        except Exception as e:
            logging.error("Unexpected error in scrape_all_models: %s", e)
            return []
        
    # Example usage in your main scraper function
    def scrape_models(self, save_local: bool = True):
        """Scrape the PartSelect site for models/parts with details."""
        if self.verbose:
            logging.info("\nScraping %s models with details...", BASE_URL)

        models_data = {}
        
        for category in CATEGORIES:
            # load from backend\scraper\suffix\{category}.json the correct suffix
            try:
                with open(f"./backend/scraper/suffix/{category}.json", "r", encoding="utf-8") as f:
                    BRANDS = json.load(f)
            except FileNotFoundError:
                logging.error("Could not find suffix file for category %s", category)
                continue

            # BRANDS is a dictionary with brand_name, brand_suffix pairs
            for brand_name, brand_suffix in BRANDS.items():
                self.driver = self._setup_driver()
                
                # Fix URL construction - ensure proper format
                if brand_suffix.startswith('/'):
                    url = f"{BASE_URL.rstrip('/')}{brand_suffix}"
                else:
                    url = f"{BASE_URL.rstrip('/')}/{brand_suffix}"
                
                if self.verbose:
                    logging.info("\nScraping category: %s at URL: %s", category, url)
                
                try:
                    self.driver.get(url)
                    time.sleep(self._get_random_wait_time())  # Allow page to load

                    n_pages, n_models = self.get_number_of_models_and_pages()
                    if self.verbose:
                        logging.info("> For category %s, brand %s found %d models across %d pages", 
                                    category, brand_name, n_models, n_pages)

                    # Use the new method to get models with details
                    all_models = self.scrape_models_with_details(
                        n_pages=n_pages,
                        base_url=url,
                        save_local=True,
                        max_details=3  # Limit to 3 models per brand to avoid excessive scraping
                    )
                    
                    if not models_data.get(category):
                        models_data[category] = dict()
                    models_data[category][brand_name] = all_models
                
                except Exception as e:
                    logging.error("Error scraping %s %s: %s", category, brand_name, e)
                    continue

        if save_local:
            # Create "./backend/scraper/data/" directory if it doesn't exist
            if not os.path.exists("./backend/scraper/data/"):
                os.makedirs("./backend/scraper/data/")
            file_path = "./backend/scraper/data/models_with_details.json"
            if self.verbose:
                logging.info("Saving scraped data to JSON file %s...", file_path)
            # Save the scraped data to a JSON file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(models_data, f, indent=2)
                
def main():
    """Run the scraper."""
    import argparse
    parser = argparse.ArgumentParser(description="Scrape models from PartSelect website.")
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode.")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output.")
    parser.add_argument(
        "--driver",
        type=str,
        default="undetected",
        help="Type of driver to use (undetected, Firefox, Chrome).",
    )
    parser.add_argument("--no-proxy", action="store_false", help="Don't use a proxy.")
    args = parser.parse_args()

    
    scraper = ModelsScraper(headful=args.headful, verbose=args.verbose, driver_type=args.driver, use_proxy=args.no_proxy)
    scraper.scrape_models()


if __name__ == "__main__":
    main()