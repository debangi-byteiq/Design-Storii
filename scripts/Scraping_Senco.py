import re
# import time
import requests
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from models.kama_model import DataTable, PriceTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, ping_my_db, find_row_using_existing, get_category, \
    find_metal_colour, open_new_page, save_image_to_s3, update_flag_to_delete, save_to_excel, update_converted_prices


def create_product_list():
    """
    This function scrolls through the site to obtain all the product links.
    Args:
        page:  This is the playwright page object the Product URL is opened.

    Returns:
        This function returns a list of product links.
    """
    links = list()
    print("Navigating through pages to obtain product links")
    payloads = [
        {"filters": ",\"productsCount\":50,\"currency\":\"\",\"getAllVariants\":\"false\",\"showOOSProductsInOrder\":\"false\",\"attributeFacetValuesLimit\":20,\"attributes\":{},\"sort\":[{\"field\":\"priority:float\",\"order\":\"asc\"},{\"field\":\"relevance\",\"order\":\"asc\"}],\"categories\":[\"41\"],\"q\":null}"},
        {"filters": ",\"productsCount\":50,\"currency\":\"\",\"getAllVariants\":\"false\",\"showOOSProductsInOrder\":\"false\",\"attributeFacetValuesLimit\":20,\"attributes\":{},\"sort\":[{\"field\":\"priority:float\",\"order\":\"asc\"},{\"field\":\"relevance\",\"order\":\"asc\"}],\"categories\":[\"10\"],\"q\":null}"}
    ]
    url = 'https://api.wizzy.ai/v1/products/filter'
    for payload in payloads:
        num = 1
        while True:
            temp_payload = {'filters': f'{{\"page\":{num}' + payload["filters"]}
            # print(temp_payload)
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Origin": "https://sencogoldanddiamonds.com",
                "Referer": "https://sencogoldanddiamonds.com/",
                "Sec-Fetch-Mode": "cors",
                "Sec-Dest-Mode": "empty",
                "X-Api-Key": "WS9WOTF3Y2lXNzdyM0JqUTBhVmtqcmhvNEhEaXc5cDQxYURnTDhjeCs1RmpKTy92VHpLV3EvWG0waVM2b2VnV09SYXpiUjZQS3hYaURpc09sNVFXcEE9PQ==",
                "X-Store-Id": "ad8d0b90c67711eea99142010aa0000e"
            }

            response = requests.request("POST", url, json=temp_payload, headers=headers).json()
            results = response['payload']['result']
            if len(results) == 0:
                print('All products loaded')
                break
            else:
                for result in results:
                    links.append(result['url'])
                print(f'{len(results)} on page number {num}.')
            num += 1
    # for url in urls:
    #     num = 1
    #     page.goto(url, timeout=60000)
    #     while True:
    #         print(f"Products from page {num} loaded")
    #         num += 1
    #         try:
    #             page.locator('a.product_list_more_show___yKez').click()
    #             time.sleep(1)
    #         except:
    #             print("..................")
    #             break
    #     div_tags = page.query_selector_all('div.product_list_pad_10__TrJ0G')
    #     for div_tag in div_tags:
    #         try:
    #             href = div_tag.query_selector('a[target="_blank"]').get_attribute('href')
    #             links.append(href)
    #         except:
    #             continue
    #     time.sleep(2)
    # print("All products loaded")
    return list(set(links))


def find_metal_details(desc):
    """
    This function is used to find the metal details of the product.
    Args:
        desc: Contains the description of the product.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    if 'gold' in desc.lower():
        details['MetalType'] = 'Gold'
        try:
            match = re.search(r'(\d+)\s*k([a-z\,\s\-]+)\s*gold', desc, re.IGNORECASE)
            details['MetalPurity'] = int(match.group(1))
            details['MetalColour'] = find_metal_colour(match.group(2))
        except:
            details['MetalColour'], details['MetalPurity'] = None, None
        try:
            details['MetalWeight'] = float(re.search(r'gold\sweight\:\s*(\d*\.?\d*)', desc, re.IGNORECASE).group(1))
        except:
            details['MetalWeight'] = None
    elif 'platinum' in desc.lower():
        details['MetalType'] = 'Platinum'
        try:
            details['MetalPurity'] = int(re.search(r'metal\spurity\:\s*(\d+)', desc, re.IGNORECASE).group(1))
        except:
            details['MetalPurity'] = None
        details['MetalColour'] = None
        try:
            details['MetalWeight'] = float(re.search(r'platinum\sweight\:\s*(\d*\.?\d*)', desc, re.IGNORECASE).group(1))
        except:
            details['MetalWeight'] = None
    elif 'silver' in desc.lower():
        details['MetalType'] = 'Silver'
        details['MetalColour'], details['MetalPurity'], details['MetalWeight'] = None, None, None
    else:
        details['MetalType'] = 'Other'
        details['MetalColour'], details['MetalPurity'], details['MetalWeight'] = None, None, None
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
        details['DiamondWeight'] = float(re.search(r'diamond\sweight\:\s*(\d*\.?\d*)', desc, re.IGNORECASE).group(1))
    except:
        details['DiamondWeight'] = None
    try:
        quality = re.search(r'diamond\squality\:\s*([A-Z0-9\-\/]+)', desc, re.IGNORECASE).group(1)
        details['DiamondColour'] = quality.split('-')[0]
        details['DiamondClarity'] = quality.split('-')[1]
    except:
        details['DiamondColour'], details['DiamondClarity'] = None, None
    details['DiamondPieces'] = None
    return details


def find_product_details(soup, link, page, company_name, run_date, image_num):
    """
    This function is used to find the product details of the product.
    Args:
        soup: This object contains all the HTML content from an instance of the page when loaded completely.
        link: Product URL.
        page: This is the playwright page object the Product URL is opened.
        company_name: Name of the company that is being scraped.
        run_date: Date on which the script is being executed. This is called in order to create the unique id for the image
        image_num: Number of the image to be displayed on the image name, increments by one with every image saved.

    Returns: It returns a dictionary containing product details such as Product Name, S3 Image URL, Product Category, Price, Description and Product Weight.

    """
    details = dict()
    details['Name'] = soup.find('h1', class_='title_product_title__YbFQ1').text.strip().title()
    img_url = soup.find('div', class_='react-slider__picture').find('img')['src']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('p', class_='price_new_price__7iRYM').text.strip()))
        details['Currency'] = 'INR'
    except:
        details['Price'] = None
        details['Currency'] = None
    try:
        details['Description'] = soup.find_all('div', class_='details_text')[0].text.strip()
    except:
        details['Description'] = None
    try:
        p_list = list()
        desc = soup.find_all('div', class_='details_text')[1].find_all('p')
        for p in desc:
            p_list.append(p.text.strip())
        details['desc'] = '||' .join(p_list)
    except:
        details['desc'] = ''
    try:
        details['ProductWeight'] = float(re.search(r'gross\sweight\:\s*(\d*\.?\d*)', details['desc'], re.IGNORECASE).group(1))
    except:
        details['ProductWeight'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])
    return details


def scrape_product(link, page, company_name, country_name, run_date, image_num):
    """
    This function is used to navigate to the product page and scrape the product details.
    Args:
        link: Product URL to be scrapped.
        page: Playwright browser page in which the url will be opened.
        company_name: Name of the company that is being scrapped.
        country_name: Name of the country that the site is being scrapped.
        run_date: Date on which the site script is being executed.
        image_num: Number of the image to be displayed on the image name, increments by one with every image saved.

    Returns: It returns a dictionary containing two different object of the row, one to be added to mysql database, other a row list for the dataframe.

    """
    data = dict()
    page.goto(link, timeout=60000)
    # page.screenshot(path='screenshot1.png')
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(soup, link, page, company_name, run_date, image_num)
    metal_details = find_metal_details(product_details['desc'])
    diamond_details = find_diamond_details(product_details['desc'])
    data['DB Row'] = DataTable(
        Country_Name=country_name, Company_Name=company_name, Product_Name=product_details['Name'],
        Product_URL=link, Image_URL=product_details['ImgUrl'], Category=product_details['Category'],
        Currency=product_details['Currency'], Price=product_details['Price'],
        Description=product_details['Description'], Product_Weight=product_details['ProductWeight'],
        Metal_Type=metal_details['MetalType'], Metal_Colour=metal_details['MetalColour'],
        Metal_Purity=metal_details['MetalPurity'], Metal_Weight=metal_details['MetalWeight'],
        Diamond_Colour=diamond_details['DiamondColour'], Diamond_Clarity=diamond_details['DiamondClarity'],
        Diamond_Pieces=diamond_details['DiamondPieces'], Diamond_Weight=diamond_details['DiamondWeight'], Flag="New"
    )
    data['DF Row'] = [
        country_name, company_name, product_details['Name'], link, product_details['ImgUrl'],
        product_details['Category'], product_details['Currency'], product_details['Price'],
        product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'Senco'
    country_name = 'India'
    run_date = date.today()
    warnings.filterwarnings("ignore")

    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        # browser = p.firefox.launch(headless=True)
        # page = open_new_page(browser)
        # print(scrape_product('https://sencogoldanddiamonds.com/jewellery/neela-chakra-diamond-pendant', page, company_name, country_name, run_date, 1))
        # exit()
        product_links = create_product_list()
        print(f'{len(product_links)} no. of products loaded.', end='\n\n')
        print('Starting scrapping...........')

        # Create a database session.
        session = Session()
        scraped_links = list()

        # Extract existing rows of the company before start of the scrapping in order to compare and update flag later.
        existing_rows = session.query(DataTable).filter_by(Company_Name=company_name).all()

        browser = p.firefox.launch(headless=True)
        page = open_new_page(browser)
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
                        data = scrape_product(link, page, company_name, country_name, run_date, image_num)

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
                        cmd = input(
                            'You are disconnected from the internet!...\nEnter "y" to resume or "n" to terminate the program: ')
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
        update_converted_prices(Session, DataTable, PriceTable, company_name)


if __name__ == '__main__':
    main()
