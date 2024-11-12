import re
import time
import http.client
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from unicodedata import category

from models.data_model import DataTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, ping_my_db, find_row_using_existing, get_category, find_metal_colour, find_gold_purity, open_new_page, save_image_to_s3, update_flag_to_delete, save_to_excel


def create_category_list(page):
    links = dict()
    page.goto('https://www.grtjewels.com/jewellery/diamond-jewellery.html', timeout=60000)
    time.sleep(2)
    li_tags = page.query_selector('ol#show_in_main_sidebar-metal').query_selector_all('li')
    for li_tag in li_tags:
        try:
            a_tag = li_tag.query_selector('a')
            links[re.sub(r'\s+', ' ', a_tag.text_content().replace('\n', '').strip())] = li_tag.query_selector(
                'a').get_attribute('href')
        except:
            continue
    return links


def get_html_content(link, p):
    conn = http.client.HTTPSConnection("www.grtjewels.com")
    payload = ""
    headers = {
        'accept': "text/html, */*; q=0.01",
        'accept-language': "en-US,en;q=0.9",
        '^cookie': "mage-banners-cache-storage=^{^}; _gcl_au=1.1.1546475219.1710401156; _fbp=fb.1.1710401156510.1121264599; _hjSessionUser_3719842=eyJpZCI6IjY1NGQ4YzVjLWEzZDYtNTkxYi05MTQ3LTMxM2Y1ZmU4NTlkZiIsImNyZWF0ZWQiOjE3MTA0MDExNTY1MDAsImV4aXN0aW5nIjp0cnVlfQ==; form_key=2EE3cI2JMZpkd2GC; _gcl_aw=GCL.1713177372.CjwKCAjwoPOwBhAeEiwAJuXRhyhdedQYc7uZjIqUiwwZO73Nf0PzuedIrlfhSZ9-_UUScQO4ipG6xhoCEKYQAvD_BwE; _gid=GA1.2.986817065.1713177372; _gac_UA-20025751-1=1.1713177372.CjwKCAjwoPOwBhAeEiwAJuXRhyhdedQYc7uZjIqUiwwZO73Nf0PzuedIrlfhSZ9-_UUScQO4ipG6xhoCEKYQAvD_BwE; mage-cache-storage=^{^}; mage-cache-storage-section-invalidation=^{^}; mage-cache-sessid=true; mage-messages=; recently_viewed_product=^{^}; recently_viewed_product_previous=^{^}; recently_compared_product=^{^}; recently_compared_product_previous=^{^}; product_data_storage=^{^}; _ga=GA1.1.257059499.1710401156; _hjSession_3719842=eyJpZCI6ImYwYWVjMWQ4LWE4YjEtNDQ2OC1hOGEyLTE2OWNjNDVkZGMxMyIsImMiOjE3MTMyNDI1MzU5NzQsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; _uetsid=fa7983f0fb1311ee8723010368734135; _uetvid=71c62dc0f7f211ee8c1a5916e0b4041c; _clck=1iwhn4d^%^7C2^%^7Cfkz^%^7C0^%^7C1562; _ga_ES9PXZ7C29=GS1.1.1713242535.7.0.1713242536.59.0.1546658048; cto_bundle=nuh4nl94TDJOb3BGalZuWCUyRk9mWUNJUzRvbk9aaUZsUG5wRlUxaEd3YVlaM0l4Q0JTaFJtV1dUQ1ltcjJjWVFpTWhTSmdRb2tMa1ZYOXJZdXllcEExNEJEUnRtNnJTbWJzMG9lTTExYmhhazk4U2tabWp6aVFyRSUyQlBwMFRrd0p6eTZUSSUyRjNFZ1BFWjVKRDVQQ1cza3pKcHdSJTJGOTBjaW9ITXBTSGRPQkxHM3Y2MHklMkJSV1NucjlxQiUyRlRjRDgzZ3ZEa1F1VURiOUxJZTN0N0g1dWtrTXlhV0tEaVdJT1RqUVVEUDElMkZ0dDR6ZUZlekJ0REVHUHhuZDhvMXhsOGlWZENXdG9KZGtXUUh2Z1NhbiUyRkxvVDFTQTgxSGsxVURpY1UwdEJWRm45RXVTUDFxbWpiRjdYc0F0Sm5DWnRLN1UlMkJZU0xYam84Yw; _clsk=oz7jbr^%^7C1713242538072^%^7C1^%^7C1^%^7Ca.clarity.ms^%^2Fcollect^",
        'referer': "https://www.grtjewels.com/jewellery/diamond-jewellery.html",
        '^sec-ch-ua': "^\^Google",
        'sec-ch-ua-mobile': "?0",
        '^sec-ch-ua-platform': "^\^Windows^^^",
        'sec-fetch-dest': "empty",
        'sec-fetch-mode': "cors",
        'sec-fetch-site': "same-origin",
        'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        'x-requested-with': "XMLHttpRequest"
    }
    conn.request("GET", f"{link}&p={p}", payload, headers)
    res = conn.getresponse()
    return res.read().decode("utf-8")


def create_product_list(value):
    links = list()
    p = 1
    prev_links = list()
    while True:
        current_links = list()
        soup = BeautifulSoup(get_html_content(value, p), 'html.parser')
        a_tags = soup.find_all('a', class_='product photo product-item-photo')
        for a_tag in a_tags:
            current_links.append(a_tag['href'])
        if current_links == prev_links:
            print('..................................')
            break
        else:
            prev_links = current_links
        links += current_links
        print(f'Products from page {p} loaded')
        p += 1
        time.sleep(2)
    return list(set(links))


def find_metal_details(desc, category):
    """
    This function is used to find the metal details of the product.
    Args:
        desc: The description of the product.
        category:

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    if 'gold' in desc['metal'].lower():
        details['MetalType'] = 'Gold'
        try:
            details['MetalPurity'] = find_gold_purity(desc['purity'])
        except:
            details['MetalPurity'] = None
        try:
            if 'rose gold' in category.lower():
                details['MetalColour'] = 'Rose'
            elif 'yellow gold' in category.lower():
                details['MetalColour'] = 'Yellow'
            elif 'white gold' in category.lower():
                details['MetalColour'] = 'White'
            else:
                details['MetalColour'] = None
        except:
            details['MetalColour'] = None
        try:
            weight = re.search(r'(\d*\.?\d*)\s*g', desc['weight'], re.IGNORECASE).group(1)
            details['MetalWeight'] = float(weight)
        except:
            details['MetalWeight'] = None
    elif 'silver' in desc['metal'].lower():
        details['MetalType'] = 'Silver'
        details['MetalPurity'] = None
        details['MetalColour'] = None
        details['MetalWeight'] = None
    elif 'platinum' in desc['metal'].lower():
        details['MetalType'] = 'Platinum'
        details['MetalPurity'] = int(remove_non_numeric_chars(desc['purity']))
        details['MetalColour'] = None
        details['MetalWeight'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalPurity'] = None
        details['MetalColour'] = None
        details['MetalWeight'] = None
    return details


def find_diamond_details(soup):
    """
    This function is used to find the diamond details of the product.
    Args:
        soup: This object contains all the HTML content from an instance of the page when loaded completely.

    Returns: It returns a dictionary containing diamond colour, clarity, number of pieces and total diamond carat weight.

    """
    details = dict()
    diamond_list = list()
    table_tr = soup.find('div', class_='grt-product-description-tablesection').find('div',class_='table-responsive').find_all('tr')
    theads = table_tr[0].find_all('th')
    for head in theads:
        diamond_list.append([head.text.strip().lower()])
    start_index, end_index = 0, 0
    for tr in table_tr:
        if 'diamond detail' in tr.text.strip().lower():
            start_index = table_tr.index(tr) + 1
        elif 'total diamond value' in tr.text.strip().lower():
            end_index = table_tr.index(tr)
    for i in range(start_index, end_index):
        tds = table_tr[i].find_all('td')
        for j in range(len(diamond_list)):
            try:
                text = tds[j].text.strip()
                if text == '' or text == ' ':
                    diamond_list[j].append('0')
                else:
                    diamond_list[j].append(text)
            except:
                diamond_list.append('0')
    diamond_dict = dict()
    for sublist in diamond_list:
        diamond_dict[sublist[0]] = sublist[1:]
    try:
        details['DiamondWeight'] = sum([float(remove_non_numeric_chars(element)) for element in diamond_dict['weight']])
        details['DiamondWeight'] = round(details['DiamondWeight'], 3)
    except:
        details['DiamondWeight'] = None

    details['DiamondPieces'] = 0
    for item in diamond_dict['component']:
        try:
            details['DiamondPieces'] += int(re.search(r'(\d+)\s*no', item, re.IGNORECASE).group(1))
        except:
            details['DiamondPieces'] += 0
    details['DiamondPieces'] = None if details['DiamondPieces'] == 0 else details['DiamondPieces']

    try:
        match = re.search(r'\-\s([\w\-\/]+)\s([\w\s\/]+)\s([\w\(\)\s]+)?\s*\-', diamond_dict['component'][0],
                          re.IGNORECASE)
        details['DiamondColour'] = match.group(1)
        details['DiamondClarity'] = match.group(2)
    except:
        details['DiamondColour'] = None
        details['DiamondClarity'] = None
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
    details['Name'] = soup.find('div', class_='grt-product-detailpage-titlesection').find('h1').text.strip()
    try:
        img_url = soup.find('div', class_='fotorama__stage__shaft.fotorama__grab').find(
            'div', class_='fotorama__stage__frame.fotorama__active')['href']
        img_url = soup.find_all('div', class_='fotorama__stage__frame')[1]['src'] if '_sizing' in img_url else img_url
    except:
        img_url = soup.find('div', class_='gallery-placeholder').find_all('img')[0]['src']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers,company_name, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    try:
        details['Price'] = soup.find('span', class_='special-price').find('span', class_='price').text.strip()
        details['Price'] = float(remove_non_numeric_chars(details['Price']))
        details['Currency'] = soup.find('meta', {'itemprop': 'priceCurrency'})['content']
    except:
        try:
            details['Price'] = soup.find('span', class_='normal-price').find('span', class_='price').text.strip()
            details['Price'] = float(remove_non_numeric_chars(details['Price']))
            details['Currency'] = soup.find('meta', {'itemprop': 'priceCurrency'})['content']
        except:
            details['Price'], details['Currency'], details['PriceINR'], details['PriceUSD'] = None, None, None, None
    details['Description'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])
    try:
        detail_divs = soup.find('div', class_='grt-product-description-leftsection').find_all('div', class_='grt-product-detais')
        for div in detail_divs:
            try:
                details[div.find('label').text.strip().lower()] = div.find('span').text.strip()
            except:
                continue
    except:
        pass
    details['ProductWeight'] = None
    return details


def scrape_product(link, page, company_name, country_name, run_date, image_num, metal_category):
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
    time.sleep(3)
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(soup, link, page, company_name, run_date, image_num)
    metal_details = find_metal_details(product_details, metal_category)
    diamond_details = find_diamond_details(soup)
    data['DB Row'] = DataTable(
        Country_Name=country_name, Company_Name=company_name, Product_Name=product_details['Name'],
        Product_URL=link, Image_URL=product_details['ImgUrl'], Category=product_details['Category'],
        Currency=product_details['Currency'], Price=product_details['Price'], Description=product_details['Description'],
        Product_Weight=product_details['ProductWeight'], Metal_Type=metal_details['MetalType'],
        Metal_Colour=metal_details['MetalColour'], Metal_Purity=metal_details['MetalPurity'],
        Metal_Weight=metal_details['MetalWeight'], Diamond_Colour=diamond_details['DiamondColour'],
        Diamond_Clarity=diamond_details['DiamondClarity'], Diamond_Pieces=diamond_details['DiamondPieces'],
        Diamond_Weight=diamond_details['DiamondWeight'], Flag="New"
    )
    data['DF Row'] = [
        country_name, company_name, product_details['Name'], link, product_details['ImgUrl'],
        product_details['Category'], product_details['Currency'], product_details['Price'], product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'GRT'
    country_name = 'India'
    run_date = date.today()
    warnings.filterwarnings("ignore")

    with sync_playwright() as p:
        row_list = list()
        max_retries = 3

        # browser = p.chromium.launch(headless=True)
        # page = open_new_page(browser)
        # print(scrape_product('https://www.grtjewels.com/all-jewellery/ring/trendy-geometric-pattern-diamond-ring-736a001574-1-ef-if-vvs-18kt-yellow-gold-7.html', page, company_name, country_name, run_date, 1, rates_inr, rates_usd, 'Rose'))
        # exit()

        # Create a database session.
        session = Session()
        scraped_links = list()

        # Extract existing rows of the company before start of the scrapping in order to compare and update flag later.
        existing_rows = session.query(DataTable).filter_by(Company_Name=company_name).all()

        browser = p.firefox.launch(headless=True)
        page = open_new_page(browser)
        category_dict = create_category_list(page)
        print(f'{len(category_dict)} category links found.')
        # print(category_dict)
        browser.close()
        image_num = 1
        for category, value in category_dict.items():
            product_links = create_product_list(value)
            print(f'{len(product_links)} no. of products loaded.', end='\n\n')
            # continue
            print('Starting scrapping...........')
            # print(scrape_product('https://www.grtjewels.com/gold-jewellery/earrings/lustrous-floral-dancing-beaded-gold-earrings-17b423472.html', page, company_name, country_name, run_date,1, rates_inr, rates_usd))
            # exit()
            browser = p.chromium.launch(headless=True)
            page = open_new_page(browser)
            for link in product_links:
                retries = 0
                # While loops tries to scrape 3 times if any error occurs during scrapping.
                while retries <= max_retries:
                    try:
                        # Close and launch a new browser after every 25 links scraped.
                        if product_links.index(link) % 25 == 0 and product_links.index(link) != 0:
                            browser.close()
                            browser = p.chromium.launch(headless=True)
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
                            data = scrape_product(link, page, company_name, country_name, run_date, image_num, category)

                            # Add the row to the session.
                            session.add(data['DB Row'])

                            # Add the row to the dataframe
                            row_list.append(data['DF Row'])
                            print(
                                f"{image_num}: {data['DB Row'].Product_URL}, {data['DB Row'].Image_URL}")
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


if __name__ == '__main__':
    main()
