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

        print("Acquiring new access token")

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


    def __raw_api_call(self, method, query, **kwargs):
        """Make an API call with provided parameters"""

        url = f"https://api.moltin.com/v2/{query}"

        headers = {
            "Authorization": f"Bearer {self.__get_access_token()}"
        }

        if kwargs is not None:
            headers["Content-Type"] = "application/json"
        
        if method.lower() == "get":
            response = requests.get(url, headers=headers, params=kwargs)
        else:
            response = requests.request(method, url, headers=headers, json={"data": kwargs})
        
        try:
            return response.json()
        except ValueError:
            return None


    def get_products(self):
        product_data = self.__raw_api_call("GET", "products")
        return {
            product["name"]: product["id"] 
            for product in product_data["data"]
        }

    
    def get_product_by_id(self, id):
        product_info = self.__raw_api_call("GET", f"products/{id}")
        return product_info["data"]

    
    def get_image_url_by_file_id(self, id):
        file_info = self.__raw_api_call("GET", f"files/{id}")
        return file_info["data"]["link"]["href"]


    def remove_product_from_cart(self, cart_id, item_id):
        self.__raw_api_call("DELETE", f"carts/{cart_id}/items/{item_id}")

    
    def get_cart_and_full_price(self, cart_id):
        items_info = self.__raw_api_call("GET", f"carts/{cart_id}/items")
        return (
            items_info["data"], 
            items_info["meta"]["display_price"]["with_tax"]["formatted"]
        )

    
    def add_product_to_cart(self, cart_id, product_id, quantity):
        self.__raw_api_call("POST", f"carts/{cart_id}/items", 
            id=product_id,
            type="cart_item",
            quantity=quantity
        )

    
    def get_or_create_customer_by_email(self, email):
        customer_info = self.__raw_api_call("GET", "customers",
            filter=f"eq(email,{email})"
        )

        if customer_info["data"]:
            return customer_info["data"][0]["id"]

        customer_info = self.__raw_api_call("POST", "customers",
            type="customer",
            name="Anonymous Customer",
            email=email
        )

        return customer_info["data"]["id"]


    def flush_cart(self, cart_id):
        self.__raw_api_call("DELETE", f"cart/{cart_id}")


    def checkout(self, cart_id, customer_id):
        placeholder_data = {
                "first_name": "na",
                "last_name": "na",
                "line_1": "na",
                "region": "na",
                "postcode": "na",
                "country": "na"
            }
        self.__raw_api_call("POST", f"carts/{cart_id}/checkout",
            customer={"id":customer_id},
            billing_address=placeholder_data,
            shipping_address=placeholder_data
        )
