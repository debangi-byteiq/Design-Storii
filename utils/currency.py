import requests
from config.database_bucket import CURRENCY_API_KEY, CURRENCY_API_URL


def get_latest_currency_rate(text):
    """
    This method returns the rate of exchange based on the currency using API.
    Args:
        text: Currency Abbreviation.

    Returns: Returns a dictionary of conversion rates.

    """
    try:
        url = f"{CURRENCY_API_URL}/{CURRENCY_API_KEY}/latest/{text}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data["conversion_rates"]
    except requests.exceptions.RequestException as e:
        print('Failed to fetch data:', e)
        return None
