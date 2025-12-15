# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ApartmentsItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class FrboListingItem(scrapy.Item):
    """Item for For Rent By Owner listings with all contact details."""
    listing_url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    beds = scrapy.Field()
    baths = scrapy.Field()
    sqft = scrapy.Field()
    owner_name = scrapy.Field()
    owner_email = scrapy.Field()
    phone_numbers = scrapy.Field()
    full_address = scrapy.Field()
    street = scrapy.Field()
    city = scrapy.Field()
    state = scrapy.Field()
    zip_code = scrapy.Field()
    neighborhood = scrapy.Field()
    description = scrapy.Field()