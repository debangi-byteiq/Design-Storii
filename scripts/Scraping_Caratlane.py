import re
import time
import warnings
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from models.data_model import DataTable, Session
from utils.dictionaries_and_lists import network_errors
from utils.functions import clear_popup,remove_non_numeric_chars,  ping_my_db, find_row_using_existing, get_category, find_metal_colour,  open_new_page, save_image_to_s3, update_flag_to_delete, save_to_excel, scroll_page


# def click_specification_button(page):
#     accordians = page.query_selector('div.style__ProdAccordions-sc-1y2jmx4-29').query_selector_all("div.MuiPaper-root")
#     for accordian in accordians:
#         if "specification" in accordian.text_content().lower():
#             accordian.query_selector('div.MuiButtonBase-root').click()


def create_product_list(page):
    """
    This function uses the request library to fetch product links from the API library.
    Returns: This function returns list of product links extracted.

    """
    links = list()
    print("Scrolling through the pages to obtain product links")
    page.goto('https://www.caratlane.com/jewellery/diamond.html', timeout=60000)
    time.sleep(2)
    clear_popup(page,'span.eddm8wl6.css-cby1fy.efp5dbi0')
    scroll_page(page, 'div.css-yrr9vb.ek8iqxx18', 1)
    div_tags = page.query_selector_all('div.css-17erzg6.e1fkptg30')
    for div_tag in div_tags:
        links.append(div_tag.query_selector('a[title="View Details"]').get_attribute('href'))
    return list(set(links))


def find_metal_details(desc):
    """
    This function is used to find the metal details of the product.
    Args:
        desc: This object contains all the details from the product details function

    Returns: It returns the dictionary of metal details that contains metal type, colour, purity and weight.

    """
    details = dict()
    if 'gold' in desc['Metal'].lower() or 'gold' in desc['Description'].lower() :
        details['MetalType'] = 'Gold'
        try:
            details['MetalColour'] = find_metal_colour(desc['Metal Color'])
        except:
            try:
                color = re.search(r'KT\s*(\w+)\s*'
                                  r'Gold', desc['Description'], re.IGNORECASE)
                details['MetalColour'] = find_metal_colour(color.group(1).strip())

            except:
                details['MetalColour'] = None
        try:
            details['MetalPurity'] = int(remove_non_numeric_chars(desc['Purity']))
        except:
            try:
                purity = re.search(r"(\d+)\s*KT", desc['Description'], re.IGNORECASE)
                details['MetalPurity'] = int(remove_non_numeric_chars(purity.group(1).strip()))
            except:
                details['MetalPurity'] = None
        try:
            metal_weight = re.search(r"(\d*\.?\d*)\s*g", desc['Description'], re.IGNORECASE)
            details['MetalWeight'] = round(float(metal_weight.group(1).strip()),3)
        except:
            details['MetalWeight'] = None
    elif 'platinum' in desc['Metal'].lower() or 'platinum' in desc['Name'].lower():
        details['MetalType'] = 'Platinum'
        try:
            details['MetalColour'] = find_metal_colour(desc['Metal Color'])
            details['MetalPurity'] = int(remove_non_numeric_chars(desc['Purity']))
        except:
            details['MetalColour'] = None
            details['MetalPurity'] = None
        try:
            metal_weight = re.search(r"(\d+\.\d+)\s*g", desc['Description'], re.IGNORECASE)
            details['MetalWeight'] = round(float(metal_weight.group(1).strip()))
        except:
            details['MetalWeight'] = None
    else:
        details['MetalType'] = 'Other'
        details['MetalColour'] = None
        details['MetalPurity'] = None
        details['MetalWeight'] = None


    return details

#
def find_diamond_details(desc):
    """
    This function is used to find the diamond details of the product.
    Args:
        desc: Contains the description of the product.

    Returns: It returns a dictionary containing diamond colour, clarity, number of pieces and total diamond carat weight.

    """
    details = dict()
    try:
        details['DiamondWeight'] = round(float(remove_non_numeric_chars(desc['weight'])),3)
    except:
        try:
            carats = re.search(r"(\d+\.\d+)\s*ct", desc['Description'], re.IGNORECASE)
            details['DiamondWeight'] = round(float(carats.group(1).strip()), 3)
        except:
            details['DiamondWeight'] = None
    try:
        quality = re.search(r"([A-Z]+)\s*\-\s*([A-Z]+)", desc['Type'])
        details['DiamondColour'] = quality.group(1)
        details['DiamondClarity'] = quality.group(2)
    except:
        try:
            quality = re.search(r"([A-Z]+)\s*\-\s*([A-Z]+)", desc['Description'])
            details['DiamondColour'] = quality.group(1)
            details['DiamondClarity'] = quality.group(2)
        except:
            details['DiamondColour'] = None
            details['DiamondClarity'] =None

    try:
        pieces =  re.search(r"(\d+)", desc['pieces'])
        details['DiamondPieces'] =  int(pieces.group(1).strip())
    except:
        details['DiamondPieces'] = None

    return details
#
#
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
    scroll_page(page,'div.css-11hmjk7.ef7m5f13',0)
    time.sleep(1)
    soup = BeautifulSoup(page.content(),'html.parser')
    details['Name'] = soup.find('h1', class_ = 'css-1jjhedq e45wtet21').text.strip().title()
    img_url = soup.find_all('div', class_ ='css-wvl4fq e195g4sk16')[1].find('img')['src']
    try:
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        details['ImgUrl'] = save_image_to_s3(img_url, headers,company_name, image_name=f'{company_name}_{run_date}_{image_num}.png')
    except:
        details['ImgUrl'] = img_url
    try:
        details['Metal'] = soup.find_all('p', class_ = 'css-149f01h e9ew4dk19')[0].text.strip()
    except:
        details['Metal'] = ''
    try:
        details['Price'] = float(remove_non_numeric_chars(soup.find('span', class_ = 'css-95c3ey textcolor').text.strip()))
        details['Currency'] = 'INR'
    except:
        details['Price'], details['Currency'] = None, None
    try:
      details['Description'] = soup.find('div', id = 'skucontentdiv').text.strip()
    except:
        details['Description'] = None
    details['Category'] = get_category(link, details['Name'], details['Description'])
    try:
        div_tags = soup.find_all('div',class_ = 'css-1wt0pqc e9ew4dk21')
        for div_tag in div_tags:
            key = div_tag.find('div', class_ ='css-1esru4k e9ew4dk22').text.strip()
            value = div_tag.find('p').text.strip()
            details[key] = value
    except:
        pass
    try:
        type_div = soup.find('div', class_ = 'css-1ai3n7e e9ew4dk21')
        type = type_div.find('div', class_ = 'css-1esru4k e9ew4dk22').text.strip()
        color_clarity = type_div.find('p').text.strip()
        details[type] = color_clarity
    except:
        pass
    try:
        div_tags1 = soup.find_all('div',class_ = 'css-10r9pjl e9ew4dk21')
        try:
            details['pieces'] = div_tags1[0].find_all('p')[1].text.strip()
        except:
            pass
        try:
            details['weight'] = div_tags1[1].find('p').text.strip()
        except:
            pass
    except:
        pass
    try:
        metal_color = soup.find_all('p', class_ = 'css-fvn8u7 e799vom33')
        details['Metal Color'] = metal_color[0].text.strip()
        details['ColorClarity'] = metal_color[1].text.strip()
    except:
        details['Metal Color'] = None
        details['ColorClarity'] = None
    try:
        product_weight = details['Weight']
        product_weight1 = re.search(r"(\d+\.\d+)\s*g", product_weight)
        details['ProductWeight'] = float(remove_non_numeric_chars(product_weight1.group(1)))
    except:
        details['ProductWeight'] = None
    return details
#
#
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
    clear_popup(page,'span.eddm8wl6.css-cby1fy.efp5dbi0')
    product_details = find_product_details( page,soup,link, company_name, run_date, image_num)
    metal_details = find_metal_details(product_details)
    diamond_details = find_diamond_details(product_details)
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
    company_name = 'Caratlane'
    country_name = 'India'
    run_date = date.today()
    warnings.filterwarnings("ignore")

    with sync_playwright() as p:
        row_list = list()
        max_retries = 3
        browser = p.firefox.launch(headless=False)
        page = open_new_page(browser)
        # print(scrape_product('https://www.caratlane.com/jewellery/mickey-mouse-dangling-bracelet-jt02269-1yp900.html',page,company_name,country_name,run_date,1))
        # exit()
        product_links = create_product_list(page)
        print(f'{len(product_links)} no. of products loaded.', end='\n\n')
        print('Starting scrapping...........')

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