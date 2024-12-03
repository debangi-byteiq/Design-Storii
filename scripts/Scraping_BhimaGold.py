import re
import time
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from models.data_model import DataTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import remove_non_numeric_chars, get_category, find_metal_colour, open_new_page,\
    save_image_to_s3, update_flag_to_delete, save_to_excel, find_row_using_existing, ping_my_db, scroll_page



def create_product_list(page):
    """
    This function uses the request library to fetch product links from the API library.
    Returns: This function returns list of product links extracted.

    """
    links = list()
    category_links = ['https://www.bhimagold.com/jewellery/diamond?catId=9619181614',
                      'https://www.bhimagold.com/jewellery/diamond?catId=1124545068',
                      'https://www.bhimagold.com/jewellery/diamond?catId=5794758704',
                      'https://www.bhimagold.com/jewellery/diamond?catId=4887208874',
                      'https://www.bhimagold.com/jewellery/diamond?catId=6380169059',
                      'https://www.bhimagold.com/jewellery/diamond?catId=9090843656',
                      'https://www.bhimagold.com/jewellery/diamond?catId=8562062630',
                      'https://www.bhimagold.com/jewellery/diamond?catId=2828362157']
    for category in category_links:
        page.goto(category, timeout=60000)
        scroll_page(page, 'div._17w9shn7', 2)
        print('Navigating through pages to obtain product links...This may take a while...Please Wait!')
        while True:
            try:
                page.get_by_text('View More').click(timeout=5000)
                time.sleep(2)
            except:
                pass
                print('All products loaded')
                break
        a_tags = page.query_selector_all('div.MuiGrid-root.MuiGrid-item')
        for tag in a_tags:
            try:
                href = tag.query_selector('a._13vip40').get_attribute('href')
                links.append('https://www.bhimagold.com' + href)
            except:
                continue

    return list(set(links))


def find_metal_details(desc):
    """
    This function is used to find the metal details of the product.
    Args:
        desc: Contains the description of the product.

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    if ('kt' in desc['Name'].lower() or desc['Description'] is not None and 'kt' in desc['Description'].lower()) or ('gold' in desc['Name'].lower() or desc['Description'] is not None and 'gold' in desc['Description'].lower()):
        details['MetalType'] = 'Gold'
        try:
            details['MetalPurity'] = int(remove_non_numeric_chars(desc['purity']))
        except:
            details['MetalPurity'] = None
        try:
            details['MetalColour'] = find_metal_colour(re.search(r'([a-z\-\s\,\/]+)\s*gold', desc['Name'], re.IGNORECASE).group(1))
        except:
            try:
               details['MetalColour'] = find_metal_colour(re.search(r'([a-z\-\s\,\/]+)\s*gold', desc['Description'], re.IGNORECASE).group(1))
            except:
                details['MetalColour'] = None
    elif 'platinum' in desc['Name'].lower() or desc['Description'] is not None and 'platinum' in desc['Description'].lower():
        details['MetalType'] = 'Platinum'
        details['MetalColour'] = None
        details['MetalPurity'] = None
    elif 'silver' in desc['Name'].lower() or desc['Description'] is not None and 'silver' in desc['Description'].lower():
        details['MetalType'] = 'Silver'
        details['MetalColour'] = None
        details['MetalPurity'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalColour'] = None
        details['MetalPurity'] = None
    try:
        details['MetalWeight'] = float(remove_non_numeric_chars(desc['metal weight']))
    except:
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
    try:
        c = soup.find_all('div', class_='MuiTableContainer-root')[1].find('table',
                                                                          class_='MuiTable-root _1t897d7').find('tr',
                                                                                                                class_='MuiTableRow-root MuiTableRow-head')
        th_tags = c.find_all('th', class_='MuiTableCell-root MuiTableCell-head _1kzh60vk')
        v = soup.find_all('div', class_='MuiTableContainer-root')[1].find('table',
                                                                          class_='MuiTable-root _1t897d7').find('tbody',
                                                                                                                class_='MuiTableBody-root')
        td_tags = v.find_all('td', class_='MuiTableCell-root MuiTableCell-body _16hz926')
        for i in range(len(th_tags)):
            key = th_tags[i].text.strip().lower()
            details[key] = td_tags[i].text.strip()
        details['DiamondWeight'] = float(remove_non_numeric_chars(details['weight']))
        details['DiamondColour'] = details['colour-clarity'].split("-")[0].strip()
        details['DiamondClarity'] = details['colour-clarity'].split("-")[1].strip()
        details['DiamondPieces'] = int(details['numbers'])
    except:
        details['DiamondWeight'], details['DiamondColour'], details['DiamondClarity'], details['DiamondPieces'] = None, None, None, None

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
    details['Name'] = soup.find('h1', class_='_ehh4x6').text.strip()
    img_url = soup.find('div', class_='_mttw7u').find('img')['src']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers,company_name, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('p', class_='_hdrca2y').text.strip()))
        details['Currency'] = 'INR'
    except:
        details['Price'], details['Currency']= None, None
    try:
        details['Description'] = soup.find('p', class_='_x3yydb').text.strip()
    except:
        details['Description'] = None
    try:
        div_tags = soup.find_all('div', class_='_5brgin')
        for tag in div_tags:
            details[tag.find('p', class_='_193l5grr').text.lower().strip(':').strip()] = tag.find('p', class_='_19pn7op').text.strip()
    except:
        pass
    try:
        details['ProductWeight'] = float(remove_non_numeric_chars(details['gross weight']))
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
    metal_details = find_metal_details(product_details)
    diamond_details = find_diamond_details(soup)
    data['DB Row'] = DataTable(
        Country_Name=country_name, Company_Name=company_name, Product_Name=product_details['Name'],
        Product_URL=link, Image_URL=product_details['ImgUrl'], Category=product_details['Category'],
        Currency=product_details['Currency'], Price=product_details['Price'], Description=product_details['Description'],
        Product_Weight=product_details['ProductWeight'], Metal_Type=metal_details['MetalType'],
        Metal_Colour=metal_details['MetalColour'], Metal_Purity=metal_details['MetalPurity'],
        Metal_Weight=metal_details['MetalWeight'], Diamond_Colour=diamond_details['DiamondColour'],
        Diamond_Clarity=diamond_details['DiamondClarity'], Diamond_Pieces=diamond_details['DiamondPieces'],
        Diamond_Weight=diamond_details['DiamondWeight'], Flag="New", Count=1, Run_Date=run_date
    )
    data['DF Row'] = [
        country_name, company_name, product_details['Name'], link, product_details['ImgUrl'],
        product_details['Category'],  product_details['Currency'], product_details['Price'],
        product_details['Description'],product_details['ProductWeight'], metal_details['MetalType'],
        metal_details['MetalColour'],metal_details['MetalPurity'], metal_details['MetalWeight'],diamond_details['DiamondColour'],
        diamond_details['DiamondClarity'], diamond_details['DiamondPieces'], diamond_details['DiamondWeight'], "New", 1, run_date]
    return data


def main():
    company_name = 'Bhima_Gold'
    country_name = 'India'
    run_date = date.today().strftime("%Y-%m-%d")
    warnings.filterwarnings("ignore")
    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        browser = p.firefox.launch(headless=True)
        page = open_new_page(browser)
        product_links = create_product_list(page)
        print(f'{len(product_links)} no. of diamond products loaded.', end='\n\n')
        print('Starting scrapping...........')

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
                        # If the product exists, update the flag and increment the count.
                        row.Flag = 'Existing'
                        row.Count += 1  # Increment the count for existing products
                        print(f'Product already exists, incremented count. New count: {row.Count}\nURL: {link}')
                        continue
                    else:
                        # Else scrape the Product_URl
                        data = scrape_product(link, page, company_name, country_name, run_date, image_num)

                        # Add the row to the session.
                        session.add(data['DB Row'])

                        # Initialize count for new products
                        data['DB Row'].Count = 1

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
                        cmd = input(f'You are disconnected from the internet! Error: {e}...\nEnter "y" to resume or "n" to terminate the program: ')
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
