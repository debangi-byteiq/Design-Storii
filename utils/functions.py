import re
import requests
import time
from io import BytesIO
from PIL import Image
from utils.database import text as texts
from config.database_bucket import s3_client, bucket_name, bucket_path
from utils.dictionaries_and_lists import jewelry_types, metal_colour, columns_list, gold_purity


def remove_non_numeric_chars(input_string):
    """

    This function removes all the non-numeric characters except '.'

    Args:
        input_string (str) : Input string to remove all other characters except '.'

    Returns:
        Formatted string containing only integers and '.'

    """
    result = re.sub(r'[^.\d]', '', input_string)
    return result


def find_category(text):
    """
    This function finds the category of a given string based on the dictionary provided.
    Args:
        text: String to be searched.

    Returns: It returns the category of the given string.

    """
    for jewelry_type, keywords in jewelry_types.items():
        if any(keyword in text.lower() for keyword in keywords):
            return jewelry_type
    return 'Others'


def get_category(link, name, description):
    """
    This function aims to return the correct category type of the product upon checking in various attributes of the product.
    Args:
        link: Product URL string.
        name: Product Name string.
        description: Product Description string.

    Returns: Returns a string of the correct category type.

    """
    if find_category(link) == 'Others':
        if find_category(name) == 'Others':
            if description is None or find_category(description) == 'Others':
                return "Others"
            else:
                return find_category(description)
        else:
            return find_category(name)
    else:
        return find_category(link)


def find_metal_colour(text):
    """
    This function finds the metal colour of a given string based on the dictionary provided.
    Args:
        text: String to be searched.

    Returns:It returns the metal colour of the given string.

    """
    for colour, keywords in metal_colour.items():
        if any(keyword in text.lower().replace(' ', '').replace('and', '').replace('-', '').replace('/', '').replace('+', '').replace(',', '') for keyword in keywords):
            return colour
    return None

def convert_currency(price, rate):
    """
    This method converts price based on the rate.
    Args:
        price: Price of the product.
        rate: Rate to which the price needs to be converted.

    Returns: Converted price in floating point format.

    """
    try:
        return round(float(price)/rate, 3)
    except:
        return None


def open_new_page(browser):
    """
    This function opens a new page in a browser using playwright library.
    Args:
        browser: Browser object from the playwright library.

    Returns: It returns a new page object of the playwright library using browser context.

    """
    agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    context = browser.new_context(
        user_agent=agent,
        color_scheme=r"light",
        locale=r"en-US,en;q=0.9",
    )
    page = context.new_page()
    return page


def clear_popup(page, selector):
    """
    This method is used to clear any expected pop up on the page.
    Args:
        page: Playwright browser page on which the product URl is opened.
        selector: Element css selector to locate and close the popup on the page.

    Returns: This method does not return anything.

    """
    try:
        page.wait_for_selector(selector, timeout=5000).click()
    except:
        pass


def find_row_in_db(session, DataTable, company_name, product_url):
    """
    This function finds the row out of a given database table based on the company name and product_url.
    Args:
        session: SQL Alchemy session object based on the database.
        DataTable: This is the database object from the Database class from the database models.
        company_name: Company name from the script that was running.
        product_url: Product URL to be checked whether it is already present in the database.

    Returns: It checks whether a Product URL is present in the database or not if present it returns the corresponding row otherwise returns None.

    """
    new_row = session.query(DataTable).filter_by(Company_Name=company_name, Product_URL=product_url).one_or_none()
    return new_row


def update_flag_to_delete(existing_rows, scraped_links):
    """
    This function is used to update the Flag to 'Deleted' in the database if a Product URL is present in the database but is not found in the next run of the scripts.
    Args:
        existing_rows: This contains all the rows already present in the database instance.
        scraped_links: This contains all the links that are being scrapped in this run.

    Returns: This function does not return any value.

    """
    for row in existing_rows:
        if row.Product_URL not in scraped_links and row.Flag != 'Existing':
            row.Flag = "Deleted"
        else:
            continue


def save_to_excel(pd, row_list, company_name, run_date):
    """
    This function creates a dataframe from the row list and then create an excel file.
    Args:
        pd: Pandas library object to access the pandas library method.
        row_list: Contains the rows that were scrapped.
        company_name: Name of the company that was scrapped.
        run_date: Date on which the script was run.

    Returns: This function does not return any value but prints the number of products that were scrapped.

    """
    df = pd.DataFrame(row_list, columns=columns_list)
    print(f'{len(df)} no. of products scrapped.')
    df.to_excel(f'../Docs/{company_name}_{run_date}.xlsx', index=False)


def save_image_to_s3(image_url, headers, company_name, image_name):
    """
    This function download and save the image to a S3 bucket using URL.
    Args:
        image_url: Image URL that was scrapped from the site.
        headers: Headers required to download the image.
        company_name: Name of the company.
        image_name: Image name to be saved in the S3 bucket.

    Returns: It returns the image object URL from the S3 bucket where the image is saved.

    """
    response = requests.request('GET', image_url, headers=headers)
    content_type = response.headers.get('Content-Type')

    # Checks what content type the URL returns upon request.
    if content_type in ['image/png', 'image/jpeg', 'image/jpg']:
        s3_client.put_object(
            Body=response._content,
            Bucket=bucket_name,
            Key=f"{company_name}/{image_name}",
            ACL='public-read',
            ContentType='image/png'
        )
    else:
        # Changes the content type to png when other content type is returned.
        image = Image.open(BytesIO(response.content)).convert('RGB')
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        s3_client.put_object(
            Body=response._content,
            Bucket=bucket_name,
            Key=f"{company_name}/{image_name}",
            ACL='public-read',
            ContentType='image/png'
        )
    return f'{bucket_path}/{company_name}/{image_name}'


def is_element_visible(page, selector):
    element = page.locator(selector)
    bounding_box = element.bounding_box()
    if bounding_box is not None:
        viewport_height = page.viewport_size['height']
        return 0 <= bounding_box['y'] < viewport_height
    else:
        return False


def scroll_page(page, selector, sec):
    while True:
        page.mouse.wheel(0, 500)
        time.sleep(sec)
        if is_element_visible(page, selector):
            print('All Products Loaded')
            break

def find_gold_purity(text):
    """
    This method is used to extract the gold purity given in a string.
    Args:
        text: The string from which the gold purity is needed to be extracted.

    Returns: It returns the gold purity value in integer.

    """
    for purity, keywords in gold_purity.items():
        if any(keyword in text.lower().replace(' ', '') for keyword in keywords):
            return purity
    return None


def ping_my_db(session, number):
    """
    This method aims to ping the db with a simple query run, so that the connection stays persistent.
    Args:
        session: SQL Alchemy session object.
        number: Integer value used as trigger to ping.

    Returns: This method does not return anything.

    """
    if number % 5 == 0 and number != 0:
        session.execute(texts('SELECT 1;'))


def find_row_using_existing(existing_rows, link):
    """
    This function is used to find whether a product link already exists in the database.
    Args:
        existing_rows: DataTable object from the database containing all the already existing rows.
        link: Product URL string that needs to be checked.

    Returns: It returns the row if the product url is present in the existing row otherwise returns None.

    """
    for row in existing_rows:
        if row.Product_URL == link:
            row.Count += 1  # Increment the count
            return row
    return None



