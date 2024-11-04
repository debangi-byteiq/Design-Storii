import re
import time
import requests
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from models.kama_model import DataTable, Session
from utils.currency import get_latest_currency_rate
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, get_category, find_metal_colour, open_new_page,\
    save_image_to_s3, update_flag_to_delete, save_to_excel, find_row_using_existing, ping_my_db, convert_currency



def create_product_list():
    """
    This function uses the request library to fetch product links from the API library.
    Returns: This function returns list of product links extracted.

    """
    links = list()
    urls = ["https://www.orra.co.in/platinum", "https://www.orra.co.in/diamond"]
    for url in urls:
        n = 1
        while True:
            querystring = {"p": f"{n}"}

            payload = ""
            headers = {
                "accept": "text/html, */*; q=0.01",
                "accept-language": "en-US,en;q=0.9",
                "priority": "u=1, i",
                "^sec-ch-ua": "^\^Not"
            }

            response = requests.request("GET", url, data=payload, headers=headers, params=querystring)
            soup = BeautifulSoup(response.content, "html.parser")
            a_tags = soup.find_all('a', class_='product photo product-item-photo')
            if len(a_tags) == 0:
                print("...................................")
                break
            for a_tag in a_tags:
                links.append(a_tag['href'])
            print(f"{len(a_tags)} Products from page {n} loaded")
            n += 1
            time.sleep(1)
        # page.goto(url, timeout=60000)
        # time.sleep(2)
        # print("Navigating through the pages to obtain product links")
        # while True:
        #     scroll_page(page, 'div.footer-bottom', 2)
        # time.sleep(3)
        #     try:
        #         page.query_selector('div.ias-trigger.ias-trigger-next').wait_for_selector('button.load-more').click()
        #         time.sleep(4)
        #     except:
        #         print('All products loaded')
        #         break
        # a_tags = page.query_selector_all("a.product.photo.product-item-photo")
        # for tag in a_tags:
        #     href = tag.get_attribute('href')
        #     links.append(href)
    return list(set(links))


def find_metal_details(soup, desc):
    """
    This function is used to find the metal details of the product.
    Args:
        soup: This object contains all the HTML content from an instance of the page when loaded completely.
        desc: Contains the description of the product.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    try:
        metal = soup.find('div', class_='gold-purity').find('h6', class_='gold-puirty-value').text.strip()
    except:
        metal = ''
    if 'kt' in metal.lower() and 'pt' in metal.lower():
        details['MetalType'] = 'Gold/Platinum'
        try:
            details['MetalColour'] = find_metal_colour(desc['metal colour'])
        except:
            details['MetalColour'] = None
        try:
            details['MetalPurity'] = int(re.search(r'(\d+)kt', metal, re.IGNORECASE).group(1))
        except:
            details['MetalPurity'] = None
    elif 'kt' in metal.lower():
        details['MetalType'] = 'Gold'
        try:
            details['MetalColour'] = find_metal_colour(desc['metal colour'])
        except:
            details['MetalColour'] = None
        try:
            details['MetalPurity'] = int(re.search(r'(\d+)kt', metal, re.IGNORECASE).group(1))
        except:
            details['MetalPurity'] = None
    elif 'jewellery type' in desc and 'platinum' in desc['jewellery type'].lower() or 'pt' in metal.lower():
        details['MetalType'] = 'Platinum'
        details['MetalColour'] = None
        try:
            details['MetalPurity'] = int(re.search(r'(\d+)pt', metal, re.IGNORECASE).group(1))
        except:
            details['MetalPurity'] = None
    elif 'jewellery type' in desc and 'silver' in desc['jewellery type'].lower():
        details['MetalType'] = 'Silver'
        details['MetalColour'] = None
        details['MetalPurity'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalColour'] = None
        details['MetalPurity'] = None
    try:
        details['MetalWeight'] = float(remove_non_numeric_chars(soup.find('div', id='gross-weight-value').text.strip()))
    except:
        details['MetalWeight'] = None
    return details


def find_diamond_details(desc):
    """
    This function is used to find the diamond details of the product.
    Args:
        desc: Contains the description of the product.

    Returns: It returns a dictionary containing diamond colour, clarity, number of pieces and total diamond carat weight.

    """
    details = dict()
    try:
        details['DiamondWeight'] = float(remove_non_numeric_chars(desc['diamond weight (ct)']))
    except:
        details['DiamondWeight'] = None
    try:
        details['DiamondPieces'] = int(desc['diamonds (pcs)'])
    except:
        details['DiamondPieces'] = None
    try:
        quality = desc['diamond quality'].replace(" ", "")
        details['DiamondColour'] = quality[0:2]
        details['DiamondClarity'] = quality[2:]
    except:
        details['DiamondClarity'] = None
        details['DiamondColour'] = None
    return details


def find_product_details(page, soup, link, company_name, run_date, image_num, rates_inr, rates_usd):
    """
    This function is used to find the product details of the product.
    Args:
        soup: This object contains all the HTML content from an instance of the page when loaded completely.
        link: Product URL.
        page: This is the playwright page object the Product URL is opened.
        company_name: Name of the company that is being scraped.
        run_date: Date on which the script is being executed. This is called in order to create the unique id for the image
        image_num: Number of the image to be displayed on the image name, increments by one with every image saved.
        rates_inr: Currency exchange rates for INR.
        rates_usd: Currency exchange rates for USD.

    Returns: It returns a dictionary containing product details such as Product Name, S3 Image URL, Product Category, Price, Description and Product Weight.

    """
    details = dict()
    details['Name'] = soup.find('h1', class_='page-title').text.strip()
    img_url = soup.find('meta', {'property': 'og:image'})['content']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('span', class_='price-container').text.strip()))
        details['Currency'] = 'INR'
        details['PriceINR'] = convert_currency(details['Price'], rates_inr[details['Currency']])
        details['PriceUSD'] = convert_currency(details['Price'], rates_usd[details['Currency']])
    except:
        details['Price'], details['Currency'], details['PriceINR'], details['PriceUSD'] = None, None, None, None
    try:
        details['Description'] = soup.find('div', {'itemprop': 'description'}).text.strip()
    except:
        details['Description'] = None
    try:
        info = soup.find('tbody', class_='detail-product-content').find_all('tr')
        for i in info:
            key = i.find('th').text.strip().lower().strip(':')
            details[key] = i.find('td').text.strip()
    except:
        pass
    details['ProductWeight'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])
    return details


def scrape_product(link, page, company_name, country_name, run_date, image_num, rates_inr, rates_usd):
    """
    This function is used to navigate to the product page and scrape the product details.
    Args:
        link: Product URL to be scrapped.
        page: Playwright browser page in which the url will be opened.
        company_name: Name of the company that is being scrapped.
        country_name: Name of the country that the site is being scrapped.
        run_date: Date on which the site script is being executed.
        image_num: Number of the image to be displayed on the image name, increments by one with every image saved.
        rates_inr: Currency exchange rates for INR.
        rates_usd: Currency exchange rates for USD.

    Returns: It returns a dictionary containing two different object of the row, one to be added to mysql database, other a row list for the dataframe.

    """
    data = dict()
    page.goto(link, timeout=60000)
    time.sleep(2)
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(page, soup, link, company_name, run_date, image_num, rates_inr, rates_usd)
    metal_details = find_metal_details(soup, product_details)
    diamond_details = find_diamond_details(product_details)
    data['DB Row'] = DataTable(
        Country_Name=country_name, Company_Name=company_name, Product_Name=product_details['Name'],
        Product_URL=link, Image_URL=product_details['ImgUrl'], Category=product_details['Category'],
        Currency=product_details['Currency'], Price=product_details['Price'], Price_In_INR=product_details['PriceINR'],
        Price_In_USD=product_details['PriceUSD'], Description=product_details['Description'],
        Product_Weight=product_details['ProductWeight'], Metal_Type=metal_details['MetalType'],
        Metal_Colour=metal_details['MetalColour'], Metal_Purity=metal_details['MetalPurity'],
        Metal_Weight=metal_details['MetalWeight'], Diamond_Colour=diamond_details['DiamondColour'],
        Diamond_Clarity=diamond_details['DiamondClarity'], Diamond_Pieces=diamond_details['DiamondPieces'],
        Diamond_Weight=diamond_details['DiamondWeight'], Flag="New"
    )
    data['DF Row'] = [
        country_name, company_name, product_details['Name'], link, product_details['ImgUrl'],
        product_details['Category'],  product_details['Currency'], product_details['Price'],
        product_details['PriceINR'], product_details['PriceUSD'], product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'Orra'
    country_name = 'India'
    rates_inr = get_latest_currency_rate('INR')
    rates_usd = get_latest_currency_rate('USD')
    # rates_inr = {"INR": 1}
    # rates_usd = {"INR": 1}
    run_date = date.today()
    warnings.filterwarnings("ignore")
    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        product_links = create_product_list()
        print(f'{len(product_links)} no. of diamond products loaded.', end='\n\n')
        print('Starting scrapping...........')
        browser = p.firefox.launch(headless=True)
        page = open_new_page(browser)
        # print(scrape_product('https://www.orra.co.in/navratna-multi-stone-pendant-scy16004-d307r0b', page, company_name, country_name, run_date, 4, rates_inr, rates_usd ))
        # exit()



        # Create a database session.
        session = Session()
        scraped_links = list()

        # Extract existing rows of the company before start of the scrapping in order to compare and update flag later.
        existing_rows = session.query(DataTable).filter_by(Company_Name=company_name).all()

        image_num = 1
        for link in product_links:
            retries = 0
            # While loops tries to scrape 3 times if any error occurs during scrapping.
            while retries <= max_retries:
                try:
                    # Close and launch a new browser after every 25 links scraped.
                    if product_links.index(link) % 25 == 0 and product_links.index(link) != 0:
                        browser.close()
                        browser = p.firefox.launch(headless=True)
                        page = open_new_page(browser)

                    # Ping the db so that it maintains a persistent connection.
                    ping_my_db(session, product_links.index(link))

                    # find_row_in_db() will return the row if the Product_URL is present in the database and return None otherwise.
                    row = find_row_using_existing(existing_rows, link)
                    if row:
                        # If exists change the flag to existing.
                        row.Flag = 'Existing'
                        print(f'Product already exists, changed flag to existing.\nURL: {link}')
                        break
                    else:
                        # Else scrape the Product_URl
                        data = scrape_product(link, page, company_name, country_name, run_date, image_num, rates_inr, rates_usd)

                        # Add the row to the session.
                        session.add(data['DB Row'])

                        # Add the row to the dataframe
                        row_list.append(data['DF Row'])
                        print(f"{product_links.index(link) + 1}: {data['DB Row'].Product_URL}, {data['DB Row'].Image_URL}")
                        print(f"{data['DF Row']}", end='\n\n')

                        # Store the links that got scrapped to check and update and flags later.
                        scraped_links.append(link)
                        image_num += 1
                        break
                except Exception as e:
                    # Below exception is to catch network error occurred during runtime. If any such error occurs this will pause the execution and wait for the user to enter a command.
                    if any(error in str(e) for error in network_errors):
                        cmd = input('You are disconnected from the internet!...\nEnter "y" to resume or "n" to terminate the program: ')
                        if cmd == 'y':
                            continue
                        else:
                            # If the user prompts to terminate the program we will update the flags if found deleted and save the rows into a dataframe and database, will commit the session and close it afterward.
                            save_to_excel(pd, row_list, company_name, run_date)
                            update_flag_to_delete(existing_rows, scraped_links)
                            session.commit()
                            session.close()
                            exit('Program terminated by the user.')
                    else:
                        if retries == max_retries:
                            print(link)
                            print(f'Could not scrape the page even after {max_retries} retries..........')
                            print("Error:", e)
                            image_num += 1
                            break
                        else:
                            print(link)
                            print(f"Error Occurred: {e}\nFailed to scrape the page, trying again..........")
                            retries += 1
                            print(f'{max_retries - retries} out of {max_retries} retries left..........')
                            continue
        browser.close()

        # Update the flags save the Excel file, commit and close the database.
        save_to_excel(pd, row_list, company_name, run_date)
        update_flag_to_delete(existing_rows, scraped_links)
        session.commit()
        session.close()


if __name__ == '__main__':
    main()
