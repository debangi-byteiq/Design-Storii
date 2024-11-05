# from utils.functions import save_image_to_s3
# headers = {
#     'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
# }
# print(save_image_to_s3('https://www.candere.com/media/jewellery/images/KC03606_1_2.jpeg', headers, 'test', 'v.png'))

import requests
from bs4 import BeautifulSoup
links = list()
print("Collecting product links...")
# page.goto('https://manubhai.in/jewellery.php?category=3')
# scroll_page(page, 'div.footer__copyright', 5)
# soup = BeautifulSoup(page.content(), 'html.parser')
url = "https://manubhai.in/jewellery.php"
querystring = {"category": "3"}
payload = ""
headers = {"cookie": "PHPSESSID=4c0d831ef289f4761b5249c8a3c1e8c8"}
response = requests.request("GET", url, data=payload, headers=headers, params=querystring)
soup = BeautifulSoup(response.content, "html.parser")
print(soup)
div_tags = soup.find_all('div', class_='d__product_card')
for div_tag in div_tags:
    links.append(div_tag.find('a')['href'])
print(len(links))