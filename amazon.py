import random
import urllib.request
import csv
from urllib.error import HTTPError
import bottlenose
import bs4
import time
from bs4 import BeautifulSoup


def error_handler(err):
    ex = err['exception']
    if isinstance(ex, HTTPError) and ex.code == 503:
        time.sleep(random.expovariate(0.1))
        print("503 retry")
        return True


def get_amazon_by_region(region):
    access_key = "AKIAIN7FKTAMCSG7VVOA"
    secret = "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"
    if region == 'us':
        return bottlenose.Amazon(access_key, secret, "gary62107-20", ErrorHandler=error_handler)
    elif region == 'jp':
        return bottlenose.Amazon(access_key, secret, "gary62107-22", Region="JP", ErrorHandler=error_handler)
    else:
        return None


def fetch_review(url):
    while True:
        try:
            api_request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36"
            })
            resource = urllib.request.urlopen(api_request, timeout=5)
            review_response = resource.read()
            review_soup = BeautifulSoup(review_response, "lxml")
            return review_soup
        except urllib.error.HTTPError as e:
            if e.code == 503:
                time.sleep(random.expovariate(0.1))
                print(url)
                print('review 503')
            else:
                return None


def fetch(asin, region):
    amazon = get_amazon_by_region(region)
    if amazon is None:
        return {"error": "region code not valid"}
    response = amazon.ItemLookup(ItemId=asin, ResponseGroup="BrowseNodes,ItemAttributes,Offers,Reviews,SalesRank")
    soup = BeautifulSoup(response, "lxml")
    if soup.error is not None:
        return {"error": soup.error.message.get_text()}

    time.sleep(1)
    review_soup = fetch_review(soup.iframeurl.text)
    review_avg_star_node = review_soup.find('span', class_='crAvgStars')

    # print(soup.iframeurl.text)

    if review_avg_star_node is not None:
        reviews_count = int(review_avg_star_node.find_all('a')[-1].text.split(' ')[0].replace(',', ''))
        stars_ratio = review_soup.find_all('div', class_='histoCount')
    else:
        reviews_count = 0

    result = {}
    if soup.listprice is not None:
        result["price"] = soup.listprice.formattedprice
    else:
        result['price'] = soup.formattedprice
    if soup.price is not None:
        result["sale_price"] = soup.price.formattedprice
    else:
        result["sale_price"] = None
    result["binding"] = soup.binding
    result["star1"] = 0 if reviews_count is 0 else round(float(stars_ratio[4].text[0:-1]) / 100 * reviews_count)
    result["star2"] = 0 if reviews_count is 0 else round(float(stars_ratio[3].text[0:-1]) / 100 * reviews_count)
    result["star3"] = 0 if reviews_count is 0 else round(float(stars_ratio[2].text[0:-1]) / 100 * reviews_count)
    result["star4"] = 0 if reviews_count is 0 else round(float(stars_ratio[1].text[0:-1]) / 100 * reviews_count)
    result["star5"] = 0 if reviews_count is 0 else round(float(stars_ratio[0].text[0:-1]) / 100 * reviews_count)
    result["total_reviews"] = reviews_count
    result["average_rating"] = 0 if reviews_count is 0 else \
        review_soup.find('span', class_='asinReviewsSummary').img.attrs['alt'].split(' ')[0]
    result["sales_rank"] = soup.salesrank
    result["release_date"] = soup.releasedate
    result["category"] = [node.find('name').text for node in soup.select("browsenodes > browsenode")]
    result["url"] = soup.detailpageurl

    for key, value in result.items():
        if isinstance(value, bs4.element.Tag):
            result[key] = value.text
    return result


def to_list(product):
    result = [product['price'], product['sale_price'], product['binding'], product['star1'], product['star2'],
              product['star3'],
              product['star4'], product['star5'], product['total_reviews'], product['average_rating'],
              product['sales_rank'], product['release_date']]
    result += product['category']
    # result.append(product['url'])
    return result


def get_last_asin():
    try:
        with open('output.csv', 'r') as file:
            last_row = None
            for row_in_last_output in csv.reader(file):
                last_row = row_in_last_output
            last_asin = None if last_row is None or len(last_row) == 0 else last_row[0]
            last_asin = None if not last_asin or last_asin == 'asin' else last_asin
            return last_asin
    except FileNotFoundError:
        return None


def write_row(data, filename='output.csv'):
    with open(filename, 'a', encoding='utf-8') as output_file:
        writer = csv.writer(output_file, lineterminator='\n')
        writer.writerow(data)
        output_file.close()


def main():
    last_asin = get_last_asin()
    with open('asin.csv') as csv_file:
        reader = csv.reader(csv_file)
        if last_asin is None:
            write_row(['asin', 'country', 'price', 'sale_price', 'binding', 'star1', 'star2', 'star3', 'star4', 'star5',
                       'total_reviews',
                       'average_rating', 'sales_rank', 'release_date', 'category'])
        i = 0
        for row in reader:
            row[0] = row[0].zfill(10)
            i += 1
            if i == 1:
                continue
            if last_asin is not None:
                if row[0] == last_asin:
                    last_asin = None
                continue
            else:
                print(row)
                data_dict = fetch(row[0], row[1])
                print(data_dict)
                if 'error' in data_dict.keys():
                    write_row(row + [data_dict['error']])
                    write_row(row + [data_dict['error']], filename='error.csv')
                else:
                    data_list = to_list(data_dict)
                    write_row(row + data_list)
                if i == 10000:
                    break


if __name__ == '__main__':
    main()
    # a = fetch("0316000000", "us")
    # print(a)
