import re
import time
import requests
import warnings
from datetime import date
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from models.data_model import DataTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, get_category, open_new_page,\
    save_image_to_s3, update_flag_to_delete, save_to_excel, find_row_using_existing, ping_my_db, scroll_page


def create_product_list(page):
    """
    This function uses the request library to fetch product links from the API library.
    Returns: This function returns list of product links extracted.

    """
    links = list()
    print("Collecting product links...")
    page.goto('https://manubhai.in/jewellery.php?category=3')
    scroll_page(page, 'div.footer__copyright', 5)
    soup = BeautifulSoup(page.content(), 'html.parser')
    # url = "https://manubhai.in/jewellery.php"
    # querystring = {"category": "3"}
    # payload = ""
    # headers = {"cookie": "PHPSESSID=4c0d831ef289f4761b5249c8a3c1e8c8"}
    # response = requests.request("GET", url, data=payload, headers=headers, params=querystring)
    # soup = BeautifulSoup(response.content, "html.parser")
    div_tags = soup.find_all('div', class_='d__product_card')
    for div_tag in div_tags:
        links.append(div_tag.find('a')['href'])
    return list(set(links))


def find_metal_details(desc):
    """
    This function is used to find the metal details of the product.
    Args:
        desc: Contains the description of the product.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    details['MetalType'] = 'Gold'
    details['MetalColour'] = None
    try:
        # details['MetalPurity'] = int(re.search(r'(\d+)kt', metal, re.IGNORECASE).group(1))
        details['MetalPurity'] = int(re.search(r"purity\s*(\d+)\s*K", desc, re.IGNORECASE).group(1))
    except:
        details['Metal'] = None
    try:
        details['MetalWeight'] = float(re.search(r"net\sweight\s*([\d\.]+)\s*gram", desc, re.IGNORECASE).group(1))
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
    details['DiamondColour'] = None
    details['DiamondClarity'] = None
    details['DiamondPieces'] = None
    try:
        details['DiamondWeight'] = float(re.search(r"diamond\sweight\s*([\.\d]+)\s*ct", desc, re.IGNORECASE).group(1))
    except:
        details['DiamondWeight'] = None
    return details



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
    details['Name'] = soup.find('div', class_='d__product_heading_box').find('h1').text.strip()
    img_url = soup.find('div', class_='d__product_image_container').find('div',class_='slide slick-slide slick-current slick-active').find(
        'img')['src']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers,
                                             image_name=f'{company_name}_{run_date}_{image_num}.png', company_name=company_name)
    except:
        details['ImgUrl'] = img_url

    details['Description'] = None
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('div', class_='d__product_price').text.strip()))
        details['Currency'] = 'INR'
    except:
        details['Price'] = None
        details['Currency'] = None

    try:
        div_tags = soup.find('div', class_='d-flex d__weight_container').find_all('div', class_='d__product_weight')
        # details['desc'] = [div_tag.text.strip().replace('\n', ' ') for div_tag in div_tags]
        details['desc'] = '||'.join([div_tag.text.strip().replace('\n', ' ') for div_tag in div_tags])
    except:
        details['desc'] = ''
    try:
        details['ProductWeight'] = float(re.search(r"gross\sweight\s*([\d\.]+)\s*gram", details['desc'], re.IGNORECASE).group(1))
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
    time.sleep(2)
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(page, soup, link, company_name, run_date, image_num)
    metal_details = find_metal_details(product_details['desc'])
    diamond_details = find_diamond_details(product_details['desc'])
    data['DB Row'] = DataTable(
        Country_Name=country_name, Company_Name=company_name, Product_Name=product_details['Name'],
        Product_URL=link, Image_URL=product_details['ImgUrl'], Category=product_details['Category'],
        Currency=product_details['Currency'], Price=product_details['Price'],  Description=product_details['Description'],
        Product_Weight=product_details['ProductWeight'], Metal_Type=metal_details['MetalType'],
        Metal_Colour=metal_details['MetalColour'], Metal_Purity=metal_details['MetalPurity'],
        Metal_Weight=metal_details['MetalWeight'], Diamond_Colour=diamond_details['DiamondColour'],
        Diamond_Clarity=diamond_details['DiamondClarity'], Diamond_Pieces=diamond_details['DiamondPieces'],
        Diamond_Weight=diamond_details['DiamondWeight'], Flag="New"
    )
    data['DF Row'] = [
        country_name, company_name, product_details['Name'], link, product_details['ImgUrl'],
        product_details['Category'],  product_details['Currency'], product_details['Price'], product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'ManuBhai'
    country_name = 'India'
    run_date = date.today()
    warnings.filterwarnings("ignore")
    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        browser = p.chromium.launch(headless=False)
        page = open_new_page(browser)
        # print(scrape_product('https://manubhai.in/new_product_detail.php?product_id=1077', page, company_name, country_name, run_date, 1, rates_inr, rates_usd))
        # exit()
        product_links = create_product_list(page)
        print(f'{len(product_links)} no. of diamond products loaded.', end='\n\n')
        print('Starting scrapping...........')

        # Create a database session.
        session = Session()
        scraped_links = list()
        #
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
                        data = scrape_product(link, page, company_name, country_name, run_date, image_num)

                        # Add the row to the session.
                        session.add(data['DB Row'])

                        # Add the row to the dataframe
                        row_list.append(data['DF Row'])
                        print(f"{product_links.index(link) + 1}: {data['DB Row'].Product_URL}, {data['DB Row'].Image_URL}")
                        print(f"{data['DF Row']}", end='\n\n')  # no commenting

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
