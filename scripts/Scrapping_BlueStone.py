import re
import requests
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from models.kama_model import DataTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, get_category, find_metal_colour, find_row_using_existing, open_new_page, save_image_to_s3, update_flag_to_delete, save_to_excel, ping_my_db


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


def create_product_list():
    """
    This function uses the request library to fetch product links from the API library.
    Returns: This function returns list of product links extracted.

    """
    links = list()
    url_list = ["https://www.bluestone.com/jewellery/diamond.html", "https://www.bluestone.com/jewellery/platinum.html"]
    for url in url_list:
        num = 1
        while True:
            querystring = {"p": f"{num}", "scroll": "true"}

            payload = ""
            headers = {
                "cookie": "VisitedBlueStone=yes; screenWidth=1536; screenHeight=864; JSESSIONID=49FC66E523608FAA8D27C5CCB7F90512; pincode=110001; 66136a51bdd135cb0d80e48aebacf46a=Y2hlY2tzdW0lN0MyOTIwNDIwNjQlNUIlNURpZF92aXNpdG9yX3RhZyU3QzMyMyU1QiU1RGlkX3Zpc2l0b3JzJTdDNjgyNjk3Nzg0; viewType=grid; showTFcards=false; isPageUsable=true; _ga=GA1.1.715393138.1717650561; we_luid=c23744af1d0062e901d6667561fd4edd3ae2a9d2; isPageLoaded=true; isPageActiveAfterLoad=true; visited=yes; _gcl_au=1.1.1197892804.1717650563; _fbp=fb.1.1717650563238.524434789534266337; oia_mapping=0; AWSALBTG=FdaL86w5IwxzgMTnts6C8KotLM2gLshVyrvMS1dCCIGtXn3e7emDiM3bKLdQceGWm61srwN61uweaMEm4v9WUy00b0RNo2+C0elgjhriXkSva3mNFRcWWW0EZkRI6NcSimbESzsOT0n5iDHVUhJ+uSimFUy+MSsH0BT5IIaqD+mh5HhYTBc=; AWSALBTGCORS=FdaL86w5IwxzgMTnts6C8KotLM2gLshVyrvMS1dCCIGtXn3e7emDiM3bKLdQceGWm61srwN61uweaMEm4v9WUy00b0RNo2+C0elgjhriXkSva3mNFRcWWW0EZkRI6NcSimbESzsOT0n5iDHVUhJ+uSimFUy+MSsH0BT5IIaqD+mh5HhYTBc=; AWSALB=cTGIOoux8Ek3wYyl1LVHnjwjo17fnixgb5ZVoD9JMtxqbD+bXcs4SaMWhRzGxaQie95K8olrPMuRZPv0p/j1C3ETDMMU6yJucA+/VPDk7CkwP4WpRMV7NDJSOAPy; AWSALBCORS=cTGIOoux8Ek3wYyl1LVHnjwjo17fnixgb5ZVoD9JMtxqbD+bXcs4SaMWhRzGxaQie95K8olrPMuRZPv0p/j1C3ETDMMU6yJucA+/VPDk7CkwP4WpRMV7NDJSOAPy; _ga_NR7QPBEZKB=GS1.1.1717650561.1.1.1717650982.36.0.0",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "priority": "u=1, i",
                "^sec-ch-ua": "^\^Google",
                "sec-ch-ua-mobile": "?0",
                "^sec-ch-ua-platform": "^\^Windows^^^",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "x-requested-with": "XMLHttpRequest"
            }

            response = requests.request("GET", url, data=payload, headers=headers, params=querystring)

            soup = BeautifulSoup(response.content, "html.parser")
            # print(soup)
            try:
                li_tags = soup.find('ul', class_='product-grid').find_all('li', class_='col-xs-4')
                print(f'{len(li_tags)} products found on page {num}')
                num += 1
            except:
                print('All products loaded.')
                break
            for li in li_tags:
                try:
                    links.append(li['data-url'])
                except:
                    continue
    return list(set(links))


def find_metal_details(soup, text):
    """
    This function is used to find the metal details of the product.
    Args:
        soup: Contains all the HTML content from an instance of the page when loaded completely.
        text: Contains the description of the product.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    metal = soup.find('section', id='metal-details').text.strip()
    if 'gold' in metal.lower():
        details['MetalType'] = 'Gold'

        try:
            match = re.search(r'(\d+)\s*kt\s*(\w+)\s*gold', text, re.IGNORECASE)
            details['MetalColour'] = find_metal_colour(match.group(2))
            details['MetalPurity'] = int(match.group(1))
            details['MetalWeight'] = float(remove_non_numeric_chars(soup.find('span', id='metalWeight').text.strip()))
        except:
            try:
                details['MetalColour'] = find_metal_colour(soup.find('label', id='metalColorId').text.strip())
                details['MetalPurity'] = int(soup.find('label', id='metalPurityId').text.strip())
                details['MetalWeight'] = float(remove_non_numeric_chars(soup.find('span', id='metalWeight').text.strip()))
            except:
                details['MetalColour'] = None
                details['MetalPurity'] = None
                details['MetalWeight'] = None
    elif 'platinum' in metal.lower():
        details['MetalType'] = 'Platinum'
        try:
            match = re.search(r'platinum\s*pt(\d+)', text, re.IGNORECASE)
            details['MetalColour'] = None
            details['MetalPurity'] = int(match.group(1))
            details['MetalWeight'] = float(remove_non_numeric_chars(soup.find('span', id='metalWeight').text.strip()))
        except:
            try:
                details['MetalPurity'] = int(soup.find('label', id='metalPurityId').text.strip())
                details['MetalColour'] = None
                details['MetalWeight'] = float(remove_non_numeric_chars(soup.find('span', id='metalWeight').text.strip()))
            except:
                details['MetalColour'] = None
                details['MetalPurity'] = None
                details['MetalWeight'] = None
    else:
        details['MetalType'] = None
        details['MetalColour'] = None
        details['MetalPurity'] = None
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
    info = soup.find('section', id='stone-details').text.strip()
    try:
        details['DiamondColour'] = re.search(r'color\s*([A-Z]+)', info, re.IGNORECASE).group(1)
    except:
        details['DiamondColour'] = None
    try:
        details['DiamondClarity'] = re.search(r'clarity\s*([A-Z]+)', info, re.IGNORECASE).group(1)
    except:
        details['DiamondColour'] = None
    try:
        details['DiamondWeight'] = float(re.search(r'(\d+\.?\d+?)\s*ct', info, re.IGNORECASE).group(1))
    except:
        details['DiamondWeight'] = None
    try:
        details['DiamondPieces'] = int(re.search(r'total\sno.\sof\sdiamonds\s*(\d+)', info, re.IGNORECASE).group(1))
    except:
        details['DiamondPieces'] = None

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
    details['Name'] = soup.find('h1', class_='title-5').text.strip()
    img_url = page.query_selector('a.cloud-zoom').get_attribute('href')
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    # details['ImgUrl'] = img_url
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('span', class_='final-pd-price').text.strip()))
        details['Currency'] = 'INR'
    except:
        details['Price'] = None
        details['Currency'] = None
    try:
        details['Description'] = soup.find('div', class_='desc').text.strip().replace('\n', ' ').replace('\xa0', ' ')
    except:
        details['Description'] = None
    try:
        details['ProductWeight'] = float(remove_non_numeric_chars(soup.find('dd', id='product_total_weight').text.strip()))
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
    soup = BeautifulSoup(page.content(), 'html.parser')
    product_details = find_product_details(page, soup, link, company_name, run_date, image_num)
    metal_details = find_metal_details(soup, product_details['Description'])
    diamond_details = find_diamond_details(soup)
    # save_image_to_s3(product_details['ImgUrl'], f'{company_name}_1_{image_num}.jpg')
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
        product_details['Category'], product_details['Currency'], product_details['Price'], product_details['Description'],
        product_details['ProductWeight'], metal_details['MetalType'], metal_details['MetalColour'],
        metal_details['MetalPurity'], metal_details['MetalWeight'], diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New"]
    return data


def main():
    company_name = 'BlueStone'
    country_name = 'India'
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
        image_num = 1

        # Create a database session.
        session = Session()
        scraped_links = list()

        # Extract existing rows of the company before start of the scrapping in order to compare and update flag later.
        existing_rows = session.query(DataTable).filter_by(Company_Name=company_name).all()

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
                    ping_my_db(session, link)

                    # find_row_in_db() will return the row if the Product_URL is present in the database or return None otherwise.
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
