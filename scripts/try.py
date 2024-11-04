from utils.functions import save_image_to_s3
headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}
print(save_image_to_s3('https://www.candere.com/media/jewellery/images/KC03606_1_2.jpeg', headers, 'test', 'v.png'))