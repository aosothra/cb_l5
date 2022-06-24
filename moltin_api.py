import time
import requests


class SimpleMoltinApiClient:
    def __init__(self, client_id, client_secret):
        self.__client_id = client_id
        self.__client_secret = client_secret
        self.__access_token = None
        self.__expires_on = 0


    def __get_access_token(self):
        """Get access token or acquire a new one upon expiration"""
        now = time.time()

        if self.__access_token and now < self.__expires_on:
            return self.__access_token

        url = "https://api.moltin.com/oauth/access_token"
        data = {
            "client_id": self.__client_id,
            "client_secret": self.__client_secret,
            "grant_type": "client_credentials"
        }

        response = requests.post(url, data=data)
        response.raise_for_status()
        auth_data = response.json()

        self.__access_token = auth_data["access_token"]
        self.__expires_on = now + auth_data["expires_in"]

        return self.__access_token


    def get_products(self):
        url = "https://api.moltin.com/v2/products"
        
        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        product_data = response.json()

        return {
            product["name"]: product["id"] 
            for product in product_data["data"]
        }

    
    def get_product_by_id(self, id):
        url = f"https://api.moltin.com/v2/products/{id}"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        product_info = response.json()

        return product_info["data"]

    
    def get_image_url_by_file_id(self, id):
        url = f"https://api.moltin.com/v2/files/{id}"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        file_info = response.json()
        return file_info["data"]["link"]["href"]


    def remove_product_from_cart(self, cart_id, item_id):
        url = f"https://api.moltin.com/v2/carts/{cart_id}/items/{item_id}"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.delete(url, headers=headers)
        response.raise_for_status()

    
    def get_cart_and_full_price(self, cart_id):
        url = f"https://api.moltin.com/v2/carts/{cart_id}/items"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        items_info = response.json()

        return (
            items_info["data"], 
            items_info["meta"]["display_price"]["with_tax"]["formatted"]
        )

    
    def add_product_to_cart(self, cart_id, product_id, quantity):
        url = f"https://api.moltin.com/v2/carts/{cart_id}/items"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}",
            "Content-Type": "application/json"
        }

        json = {
            "data":{
                "id": product_id,
                "type": "cart_item",
                "quantity": quantity
            }
        }

        response = requests.post(url, headers=headers, json=json)
        response.raise_for_status()

    
    def get_or_create_customer_by_email(self, email):
        url = "https://api.moltin.com/v2/customers"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        customer_info = response.json()

        if customer_info["data"]:
            return customer_info["data"][0]["id"]

        headers["Content-Type"] = "application/json"

        json = {
            "data": {
                "type": "customer",
                "name": "Anonymous Customer",
                "email": email
            }
        }

        response = requests.post(url, headers=headers, json=json)
        response.raise_for_status()

        customer_info = response.json()

        return customer_info["data"]["id"]


    def flush_cart(self, cart_id):
        url = f"https://api.moltin.com/v2/carts/{cart_id}"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        response = requests.delete(url, headers=headers)
        response.raise_for_status()


    def checkout(self, cart_id, customer_id):
        placeholder_data = {
            "first_name": "na",
            "last_name": "na",
            "line_1": "na",
            "region": "na",
            "postcode": "na",
            "country": "na"
        }

        url = f"https://api.moltin.com/v2/carts/{cart_id}/checkout"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}",
            "Content-Type": "application/json"
        }

        json = {
            "data":{
                "customer": {"id": customer_id},
                "billing_address": placeholder_data,
                "shipping_address": placeholder_data
            }
        }

        response = requests.post(url, headers=headers, json=json)
        response.raise_for_status()
