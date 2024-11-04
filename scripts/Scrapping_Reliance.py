import re, time
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
    save_image_to_s3, update_flag_to_delete, save_to_excel, find_row_using_existing, ping_my_db, convert_currency,\
    scroll_page, find_gold_purity


def clear_popup(page):
    """
    This function is used to clear any expected popup when appeared on the page while scrapping.
    Args:
        page: Browser page object.

    Returns: This function does not return anything.

    """
    try:
        page.locator('a.m-button m-accept').click()
    except:
        pass


def create_product_list(page):
    """
    This function is used to extract products links from a page.
    Args:
        page: Playwright browser context page.

    Returns: This function returns list of product links extracted.

    """
    links = list()
    url_list = [
        "https://www.reliancejewels.com/all-jewellery/categoryid:1/search:/filter_Metal:%28%22Diamond%22%29",
        "https://www.reliancejewels.com/all-jewellery/category:1/filter_Metal:%28%22Platinum%22%29/"
    ]

    for url in url_list:
        page.goto(url)
        print('Scrolling through the page to obtain products links....')
        scroll_page(page, 'div.copyt', 0)
        time.sleep(2)
        soup = BeautifulSoup(page.content(), 'html.parser')
        p_tags = soup.find_all('p', class_='product_title')
        print((len(p_tags)))
        for p_tag in p_tags:
            try:
                links.append("https://www.reliancejewels.com" + p_tag.find('a', class_='tooltip_18')['href'])
            except:
                continue

    return list(set(links))


def find_metal_details(soup, prod):
    """
    This function is used to find the metal details of the product.
    Args:
        soup: Contains all the HTML content from an instance of the page when loaded completely.
        prod: Dictionary containing product information.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    if 'gold' in prod['Name'].lower() or (prod['Description'] is not None and 'gold' in prod['Description'].lower()) or 'gold' in prod['Info']['metal']:
        details['MetalType'] = 'Gold'
        try:
            details['MetalPurity'] = find_gold_purity(re.search(r'(\d+)\s*kt', prod['Info']['metal purity'], re.IGNORECASE).group(1))
        except:
            try:
                details['MetalPurity'] = find_gold_purity(re.search(r'(\d+)\s*kt', prod['Description'], re.IGNORECASE).group(1))
            except:
                try:
                    details['MetalPurity'] = find_gold_purity(re.search(r'(\d+)\s*kt', prod['Name'], re.IGNORECASE).group(1))
                except:
                    details['MetalPurity'] = None
        try:
            details['MetalColour'] = find_metal_colour(prod['Info']['metal colour'])
        except:
            try:
                details['MetalColour'] = find_metal_colour(prod['Info']['metal color'])
            except:
                details['MetalColour'] = None
    elif 'platinum' in prod['Name'].lower() or (prod['Description'] is not None and 'platinum' in prod['Description']) or 'platinum' in prod['Info']['metal']:
        details['MetalType'] = 'Platinum'
        try:
            details['MetalPurity'] = re.search(r'pt\s*(\d+)', prod['Info']['metal purity'], re.IGNORECASE).group(1)
        except:
            try:
                details['MetalPurity'] = re.search(r'pt\s*(\d+)', prod['Description'], re.IGNORECASE).group(1)
            except:
                try:
                    details['MetalPurity'] = re.search(r'pt\s*(\d+)', prod['Name'], re.IGNORECASE).group(1)
                except:
                    details['MetalPurity'] = None
        details['MetalColour'] = None
    elif 'silver' in prod['Name'].lower() or (prod['Description'] is not None and 'silver' in prod['Description']) or 'silver' in prod['Info']['metal']:
        details['MetalType'] = 'Silver'
        details['MetalPurity'] = None
        details['MetalColour'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalPurity'] = None
        details['MetalColour'] = None

    try:
        details['MetalWeight'] = float()
        table_rows = soup.find('table', class_='pricebreakupd').find_all('tr')
        for row in table_rows:
            tds = row.find_all('td')
            for td in tds:
                if 'gold' in td.text.lower() or 'platinum' in td.text.lower() or 'silver' in td.text.lower():
                    details['MetalWeight'] += float(tds[tds.index(td) + 1].text.strip())
        details['MetalWeight'] = None if details['MetalWeight'] == 0 else details['MetalWeight']
    except:
        details['MetalWeight'] = None
    return details


def find_diamond_details(soup, prod):
    """
    This function is used to find the diamond details of the product.
    Args:
        soup: This object contains all the HTML content from an instance of the page when loaded completely.
        prod: Dictionary containing product information.

    Returns: It returns a dictionary containing diamond colour, clarity, number of pieces and total diamond carat weight.

    """
    details = dict()
    try:
        details['DiamondColour'] = prod['Info']['diamond colour']
    except:
        try:
            details['DiamondColour'] = prod['Info']['diamond color']
        except:
            details['DiamondColour'] = None
    try:
        details['DiamondClarity'] = prod['Info']['diamond clarity']
    except:
        details['DiamondClarity'] = None
    try:
        details['DiamondWeight'] = float(remove_non_numeric_chars(prod['Info']['diamond weight']))
    except:
        try:
            details['DiamondWeight'] = float()
            table_rows = soup.find('table', class_='pricebreakupd').find_all('tr')
            for row in table_rows:
                tds = row.find_all('td')
                for td in tds:
                    if 'stone' in td.text.lower() and 'carat' in tds[tds.index(td) + 2].text.strip().lower():
                        try:
                            details['DiamondWeight'] += float(tds[tds.index(td) + 1].text.strip())
                        except:
                            continue
            details['DiamondWeight'] = None if details['DiamondWeight'] == 0 else details['DiamondWeight']
        except:
            details['DiamondWeight'] = None
    try:
        details['DiamondPieces'] = int(prod['Info']['no. of diamonds'])
    except:
        details['DiamondPieces'] = None
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
    details['Name'] = soup.find('span', id='productTitleInPDP').text.strip()
    img_url = soup.find('img', id='pbilimage1tag')['src']
    img_url = 'https:' + img_url if 'https:' not in img_url else img_url
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers, f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    # details['ImgUrl'] = img_url
    try:
        price_div = soup.find('div', class_='pricebx')
        try:
            details['Price'] = float(remove_non_numeric_chars(price_div.find('span', id='feedPrice').text.strip()))
        except:
            price = price_div.find('div', class_='best-price').text.strip().replace('\n', '').replace('₹', '')
            price = re.sub(r'\s+', ' ', price, re.IGNORECASE)
            details['Price'] = float(re.search(r'price\s*:?\s*(\d+\.?\d*)', price, re.IGNORECASE).group(1))
        details['Currency'] = 'INR'
        details['PriceINR'] = convert_currency(details['Price'], rates_inr[details['Currency']])
        details['PriceUSD'] = convert_currency(details['Price'], rates_usd[details['Currency']])
    except:
        details['Price'], details['Currency'], details['PriceINR'], details['PriceUSD'] = None, None, None, None
    text_list = list()
    try:
        desc_uls = soup.find('div', id='keyfeaturesBoxDiv').find_all('ul', class_='keyfeature_neo')
        for desc_ul in desc_uls:
            li_tags = desc_ul.find_all('li')
            for li_tag in li_tags:
                text_list.append(li_tag.text.strip())
        details['Description'] = ' || '.join(text_list)
    except:
        details['Description'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])

    details['Info'] = dict()
    try:
        spec_tables = soup.find_all('table', class_='specs_map')
        for spec_table in spec_tables:
            rows = spec_table.find_all('tr')
            for row in rows:
                try:
                    details['Info'][row.find('td', class_='specs_key').text.strip().lower()] = row.find('td', class_='specs_value').text.strip()
                except:
                    continue
    except:
        pass

    try:
        details['ProductWeight'] = float(re.search(r'(\d*\.?\d*)\s*g', details['Info']['gross weight'], re.IGNORECASE).group(1))
    except:
        try:
            table_rows = soup.find('table', class_='pricebreakupd').find_all('tr')
            for row in table_rows:
                tds = row.find_all('td')
                for td in tds:
                    if 'gross wt' in td.text.lower():
                        details['ProductWeight'] = float(tds[tds.index(td) + 1].text.strip())
                        break
        except:
            details['ProductWeight'] = None

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
        rates_inr: Price conversion rates for INR.
        rates_usd: Price conversion rates for USD.

    Returns: It returns a dictionary containing two different object of the row, one to be added to mysql database, other a row list for the dataframe.

    """
    data = dict()
    page.goto(link, timeout=60000)
    # time.sleep(2)
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(page, soup, link, company_name, run_date, image_num, rates_inr, rates_usd)
    # print(product_details)
    metal_details = find_metal_details(soup, product_details)
    # print(metal_details)
    diamond_details = find_diamond_details(soup, product_details)
    # print(diamond_details)
    # save_image_to_s3(product_details['ImgUrl'], f'{company_name}_1_{image_num}.jpg')
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
    company_name = 'Reliance'
    country_name = 'India'
    rates_inr = get_latest_currency_rate('INR')
    rates_usd = get_latest_currency_rate('USD')
    # rates_inr = {'INR': 1}
    # rates_usd = {'INR': 1}
    run_date = date.today()
    warnings.filterwarnings("ignore")
    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        browser = p.chromium.launch(headless=True)
        page = open_new_page(browser)
        product_links = create_product_list(page)
        print(f'{len(product_links)} no. of diamond products loaded.', end='\n\n')
        print('Starting scrapping...........')
        # print(scrape_product('https://reliancejewels.com/14-karat-gold-diamond-bracelet/all-jewellery/bangles-bracelet/product:538552/cid:168/?pos=1', page, company_name, country_name, run_date, 1, rates_inr, rates_usd))
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
                    if product_links.index(link) % 25 == 0:
                        browser.close()
                        browser = p.chromium.launch(headless=True)
                        page = open_new_page(browser)

                    # Ping the db so that it maintains a persistent connection.
                    ping_my_db(session, product_links.index(link))

                    # find_row_in_db() will return the row if the Product_URL is present in the database and return None otherwise.
                    # row = find_row_in_db(session, DataTable, company_name, link)
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
