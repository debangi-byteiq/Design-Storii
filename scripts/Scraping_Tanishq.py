import re
import time
from datetime import date
import warnings
import pandas as pd

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from models.data_model import DataTable,Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import open_new_page,remove_non_numeric_chars, find_metal_colour,save_image_to_s3, update_flag_to_delete, save_to_excel, find_row_using_existing, ping_my_db, get_category


# def scroll_page(page, selector, sec):
#     while True:
#         try:
#             page.mouse.wheel(0, 500)  # Scroll down by 500 pixels
#             time.sleep(2)
#         except Exception as e:
#             print(f"Scrolling failed: {e}")
#             break

def create_product_list(page):
    links = list()
    url_list = ["https://www.tanishq.com/jewelry/diamond","https://www.tanishq.com/jewelry/platinum-1"]
    print('Extacting product links....')
    for url in url_list:
        page.goto(url)
        while True:
            try:
                show_more_button = page.locator('button.show-more-btn')
                if show_more_button.is_visible():
                    show_more_button.click()
                    time.sleep(2)
                else:
                    print('All products loaded.')
                    break
            except:
                break

        soup = BeautifulSoup(page.content(), 'html.parser')
        div_tags = soup.find_all('div', class_='tile-body')
        for div_tag in div_tags:
            try:
                href = div_tag.find_all('a')[0]['href']
                links.append(href)
            except:
                continue
    return list(set(links))


def find_product_details(page, soup, link, company_name, run_date, image_num):
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
    details['Name'] = soup.find('div', class_='product-name').find('h1').text.strip()
    # details['Name'] = soup.find('h1', class_='m-0').text.strip()
    try:
        img_url = soup.find('img',class_='d-block')['src']
    except:
        img_url = soup.find('div',class_='product-detail-content col-lg-6 col-sm-12 text-center').find('img')['src']
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers, company_name, f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url

    try:
        details['Price'] = float(soup.find('span',class_='value price-text evgProductPrice').get('content'))
        details['Currency'] = 'USD'
    except:
        details['Price'], details['Currency'] = None, None
    try:
        details['Description'] = soup.find('p', class_='product-detail-para').text.strip()
        details['Description'] = soup.find('div', class_='col-sm-12').text.strip() if details['Description'] == '' or details['Description'] == None else details['Description']
    except:
        details['Description'] = None
    try:
        p_tags = soup.find('div',class_='attrval').find_all('p')
        for p_tag in p_tags:
            try:
                key = p_tag.find('span', class_='tech-head').text.strip().lower().strip(':')
                value = p_tag.find('span', class_='tech-value').text.strip()
                details[key] = value
            except:
                continue
    except:
        pass
    try:
        details['ProductWeight'] = float(remove_non_numeric_chars(details['gross weight']))
    except:
        details['ProductWeight'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])

    return details

def find_metal_details(soup, prod):
    details = dict()
    if 'metal' in prod and 'gold' in prod['metal'].lower():
        details['MetalType'] = 'Gold'
        try:
            details['MetalPurity'] = int(remove_non_numeric_chars(prod['karatage']))
        except:
            try:
                karat = soup.find('div', class_='gold-purity-section').text.strip()
                details['MetalPurity'] = re.search(r'gold\s*purity\s*:\s*(\d+)\s*k', karat, re.IGNORECASE).group(1)
                details['MetalPurity'] = int(details['MetalPurity'])
            except:
                details['MetalPurity'] = None
        try:
            details['MetalColour'] = find_metal_colour(prod['material colour'])
        except:
            details['MetalColour'] = None
        try:
            details['MetalWeight'] = 0
            desc_divs = soup.find('div', class_='price-break').find_all('div', class_='col-values')
            for desc_div in desc_divs:
                value_divs = desc_div.find_all('div')
                for value_div in value_divs:
                    if 'gold' in value_div.text.strip().lower():
                        details['MetalWeight'] = float(remove_non_numeric_chars(value_divs[value_divs.index(value_div) + 2].text.strip()))
                        break
                break
            details['MetalWeight'] = None if details['MetalWeight'] == 0 else details['MetalWeight']
        except:
            details['MetalWeight']= None
    elif 'metal' in prod and 'platinum' in prod['metal'].lower():
        details['MetalType'] = 'platinum'
        try:
            details['MetalPurity'] = int(remove_non_numeric_chars(prod['karatage']))
        except:
            details['MetalPurity'] = None
        try:
            details['MetalColour'] = find_metal_colour(prod['material colour'])
        except:
            details['MetalColour'] = None
        details['MetalWeight'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalPurity'] = None
        details['MetalColour'] = None
        details['MetalWeight'] = None
    return details

def find_diamond_details(soup,prod):
    details = dict()
    try:
        details['DiamondWeight'] = float(remove_non_numeric_chars(prod['diamond weight']))
    except:
        details['DiamondWeight'] = None
    details['DiamondWeight'] = None if details['DiamondWeight'] == 0 else details['DiamondWeight']

    try:
        details['DiamondColour'] = prod['diamond color']
    except:
        details['DiamondColour'] = None
    try:
        details['DiamondClarity'] = prod['diamond clarity']
    except:
        details['DiamondClarity'] = None
    details['DiamondPieces'] = None
    return details


def scrape_product(link, page, company_name, country_name, run_date, image_num):
    data = dict()
    page.goto(link, timeout=60000)
    soup = BeautifulSoup(page.content(),'html.parser')
    product_details = find_product_details(page, soup, link, company_name, run_date, image_num)
    metal_details = find_metal_details(soup, product_details)
    # print(metal_details)
    diamond_details = find_diamond_details(soup, product_details)
    # print(diamond_details)
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
        product_details['Category'], product_details['Currency'], product_details['Price'],
        product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'Tanishq'
    country_name = 'India'
    run_date = date.today()
    warnings.filterwarnings("ignore")
    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        browser = p.firefox.launch(headless=True)
        page = open_new_page(browser)
        product_links = create_product_list(page)
        browser.close()
        print(f'{len(product_links)} no. of diamond products loaded.', end='\n\n')
        print('Starting scrapping...........')
        # product_links = create_product_list(page)
        # print(len(product_links))
        # scrape_product('https://www.tanishq.com/product/radiant--elegance-earrings-uludp3saiada04.html', page, company_name, country_name, run_date, image_num)
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
                    # row = find_row_in_db(session, DataTable, company_name, link)
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
                        print(
                            f"{product_links.index(link) + 1}: {data['DB Row'].Product_URL}, {data['DB Row'].Image_URL}")
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

