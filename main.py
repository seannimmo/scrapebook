import argparse
import requests
import os
import sys
import shutil
from osxmetadata import OSXMetaData
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from collections.abc import Callable
import logging
from typing import Any
import send2trash
from urllib.parse import urlparse
import validators
from countTime import count_seconds

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from bs4 import BeautifulSoup


def main():
    scrape_strategy = requests_scrape
    output_strategy = output_to_file
    output_folder = False

    parser = get_parser()
    args = vars(parser.parse_args())

    if args["wait"]:
        scrape_strategy = browser_scrape
    if args["img"]:
        output_folder = True
        output_strategy = output_to_dir


    #Check if file/folder exists and user wants to overwrite it.
    if args["out"]:
        name:str = args["out"]
        if output_folder:
            ask_overwrite(name)
        elif args["html"]:
            name = name if name.endswith('.html') else name + '.html'
            ask_overwrite(name)
        else:
            name = name if name.endswith('.txt') else name + '.txt'
            ask_overwrite(name)

    page = scrape(scrape_strategy, args["website"], args)
    struct = create_struct(page, name, args)

    if name:
        output(output_strategy, struct)

def scrape(scrape_strategy: Callable, website: str, args: dict[str, Any]) -> BeautifulSoup:
    #standardize webpage
    if not website.startswith("http"):
        website = "https://" + website
    return scrape_strategy(website, args)

def requests_scrape(website: str, args: dict[str, Any] ={}) -> BeautifulSoup:
    """Scrapes a webpage with the requests library

    Args:
        website: Name of the website
        args: not required

    Returns:
        A BeautifulSoup object of the website
    
    Raises:
        RequestException
        InvalidURL
    """
    try:
        response = requests.get(website)
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        logger.error("Could not connect\n" + str(e))
    except requests.exceptions.InvalidURL as e:
        logger.error("Invalid URL: " + website + "\n"+ str(e))
    
    return BeautifulSoup(response.text, features="html.parser")


def browser_scrape(website: str, args: dict[str, Any]) -> BeautifulSoup:
    logger.info(f"downloading {website} with selenium")
    options = Options()
    if args["headless"]:
        options.add_argument("--headless=new")
    if args["incognito"]:
        options.add_argument("--incognito")
    options.page_load_strategy = 'normal'
    driver = webdriver.Chrome(options=options)
    # driver.implicitly_wait(5)
    driver.get(website)
    # wait = WebDriverWait(driver, 10)
    # wait.until(EC.visibility_of_any_elements_located((By.CLASS_NAME, "home_text")))
    ps = driver.page_source
    driver.quit()
    return BeautifulSoup(ps, features="html.parser")


def create_struct(page: BeautifulSoup, name: str, args: dict[str, Any]):
    """Creates a dictionary of items to be extracted from the webpage, e.g. images, links.

    Args:
        page: The BeautifulSoup object of the webpage
        name: The name of the folder or file to output to
        args: The arguments from the console

    Returns:
        A dictionary representing the page
    """
    logger.info("Creating structure...")
    struct = {"name": name, "page": page}
    if args["img"]:
        imgs = page.find_all("img")
        struct['img'] = {}
        counts = defaultdict(int)
        counts['image'] = 1
        for image in imgs:
            if "src" in image.attrs and image["src"]:
                url = getValidUrl(image["src"], image.attrs)
                if "alt" in image.attrs and image['alt']:
                    alt = image['alt']
                    name = f"{alt}_{counts[alt]:03d}" if counts[alt] else alt
                    counts[alt] = counts[alt] + 1
                else:
                    name = f"image_{counts['image']:03d}"
                    counts['image'] += 1
                struct['img'][name] = url
            else:
                logger.INFO(f"did not save {image}")
    return struct

def getValidUrl(src: str, image: dict[str, Any]) -> str:
    result = validators.url(src)
    if isinstance(result, validators.utils.ValidationError):
        if src.startswith("//"):
            src = "https:" + src
        else: 
            if "data-original" in image:
                src = getValidUrl(image["data-original"], image)
            else:
                logger.warning(f"Could not get url for: {image}")
    return src




def output(output_strategy: Callable, struct: dict[str, Any]):
    return output_strategy(struct)

def output_to_file(struct: dict[str, Any]):
    f = open(struct["name"], "w")
    f.write(struct["page"].prettify())
    f.close


def output_to_dir(struct: dict[str, Any]):
    logger.info("Creating files...")
    name = struct["name"]
    if os.path.isdir(name):
        send2trash.send2trash(name)
    os.mkdir(name)
    os.chdir(name)
    if struct['img']:
        for img_name, img_url in struct['img'].items():
            save_image(img_name, img_url)

def save_image(img_name: str, img_url: str):
    file_name = img_name + ".svg" if img_url.endswith(".svg") else img_name + ".jpeg"
    # file_name = img_name + ".jpeg"
    try: 
        r = requests.get(img_url, stream=True)
        if r.status_code == 200:
            with open(file_name, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
                if sys.platform == 'linux':
                    os.setxattr(file_name, 'user.source', img_url)
                if sys.platform == "darwin":
                    md = OSXMetaData(file_name)
                    md['kMDItemURL'] = img_url

    except Exception as e: 
        logging.warning(f"Could not access or save '{file_name}' at {img_url}\n\tError: {e}")



            



def ask_overwrite(name: str):
    if os.path.exists(name):
        overwrite = input(f"The folder/file {name} already exists. Do you wish to send it to the trash? y/n\n")
        if overwrite.lower() not in ['y', 'yes', 'yeah']:
            exit()

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("website", help="website to scrape")
    parser.add_argument("-w", "--wait", action="store_true", help="wait for javascript to load")
    parser.add_argument("-o", "--out", help="file or directory to store output")
    parser.add_argument("-html", action="store_true", help="output files as html")
    parser.add_argument("-i", "--img", action="store_true", help="download all images to folder")
    parser.add_argument("--incognito", action="store_true", help="start browser in incognito mode")
    parser.add_argument("-hl", "--headless", action="store_true", help="Prevent browser from being shown")

    return parser


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    main()