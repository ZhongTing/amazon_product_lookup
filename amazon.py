import random
import urllib.request
import csv
from urllib.error import HTTPError
import bottlenose
import bs4
import time
from bs4 import BeautifulSoup
import re
import codecs
import os


def error_handler(err):
    ex = err['exception']
    if isinstance(ex, HTTPError) and ex.code == 503:
        time.sleep(random.expovariate(0.1))
        print("503 retry")
        return True


# noinspection SpellCheckingInspection
def get_amazon_by_region(region):
    access_key = "AKIAIN7FKTAMCSG7VVOA"
    secret = "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"
    if region == 'us':
        return bottlenose.Amazon(access_key, secret, "gary62107-20", ErrorHandler=error_handler)
    elif region == 'jp':
        return bottlenose.Amazon(access_key, secret, "gary62107-22", Region="JP", ErrorHandler=error_handler)
    else:
        return None


def open_url(url):
    while True:
        # noinspection PyUnresolvedReferences
        try:
            api_request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/42.0.2311.90 Safari/537.36 "
            })
            resource = urllib.request.urlopen(api_request, timeout=5)
            review_response = resource.read()
            review_soup = BeautifulSoup(review_response, "lxml")
            return review_soup
        except urllib.error.HTTPError as e:
            if e.code == 503:
                time.sleep(random.expovariate(0.1))
                # print(url)
                print('review 503')
            else:
                print(e)


def fetch(asin, region):
    amazon = get_amazon_by_region(region)
    if amazon is None:
        return {"error": "region code not valid"}
    response = amazon.ItemLookup(ItemId=asin, ResponseGroup="BrowseNodes,ItemAttributes,Offers,Reviews,SalesRank")
    soup = BeautifulSoup(response, "lxml")
    if soup.error is not None:
        return {"error": soup.error.message.get_text()}

    result = {
        "binding": soup.binding,
        "sales_rank": soup.salesrank,
        "release_date": soup.publicationdate,
        "price": soup.formattedprice if soup.listprice is None else soup.listprice.formattedprice,
        "sale_price": None if soup.price is None else soup.price.formattedprice
    }
    result_reviews = fetch_reviews(soup.iframeurl.text)
    result.update(result_reviews)
    fill_browse_node(result, soup)

    for key, value in result.items():
        if isinstance(value, bs4.element.Tag):
            result[key] = value.text
    return result


def fetch_reviews(iframe_url):
    time.sleep(1)
    review_soup = open_url(iframe_url)
    review_avg_star_node = review_soup.find('span', class_='crAvgStars')
    if review_avg_star_node is not None:
        reviews_count = int(re.split("[件 ]", review_avg_star_node.find_all('a')[-1].text)[0].replace(',', ''))
        stars_ratio = review_soup.find_all('div', class_='histoCount')
    else:
        reviews_count = 0
        stars_ratio = ['0'] * 5

    return {
        "star1": get_star_count(reviews_count, stars_ratio[4]),
        "star2": get_star_count(reviews_count, stars_ratio[3]),
        "star3": get_star_count(reviews_count, stars_ratio[2]),
        "star4": get_star_count(reviews_count, stars_ratio[1]),
        "star5": get_star_count(reviews_count, stars_ratio[0]),
        "total_reviews": reviews_count,
        "average_rating": get_average_rating(review_soup, reviews_count)
    }


def fill_browse_node(result, soup):
    department = []
    genre = []
    category = []
    for node in soup.select("browsenodes > browsenode"):
        if node.iscategoryroot is None:
            continue
        children_node = node.find('children')
        if children_node is not None:
            children_node.extract()
        root_name_node = node.iscategoryroot.parent.find('name')
        # print(root_name_node.text)
        if root_name_node.text not in ['Subjects', 'ジャンル別']:
            continue
        else:
            root_name_node.extract()
        name_list = [name_node.text for name_node in node.find_all('name')]
        if len(name_list) > 0:
            department.append(name_list.pop())
        if len(name_list) > 0:
            genre.append(name_list.pop())
        if len(name_list) > 0:
            category.append(name_list[0])

    result['department'] = list(set(department))
    result['genre'] = list(set(genre))
    result['category'] = list(set(category))


def get_average_rating(review_soup, reviews_count):
    if reviews_count is 0:
        return 0
    else:
        attr_alt_ = review_soup.find('span', class_='asinReviewsSummary').img.attrs['alt']
        try:
            average_rating = float(attr_alt_.split(' ')[0])
            return average_rating
        except ValueError:
            try:
                return float(attr_alt_.split(' ')[1])
            except ValueError:
                return 0


def get_star_count(reviews_count, star_ratio):
    if reviews_count == 0:
        return 0
    elif star_ratio.text.find('%') == -1:
        return int(star_ratio.text)
    else:
        return round(int(star_ratio.text[0:-1]) / 100 * reviews_count)


def to_list(product):
    result = [product['price'], product['sale_price'], product['binding'], product['star1'], product['star2'],
              product['star3'], product['star4'], product['star5'], product['total_reviews'], product['average_rating'],
              product['sales_rank'], product['release_date']]
    department_list = [''] * 5
    genre_list = [''] * 5
    for k in range(5):
        department_list[k] = product['department'][k] if k < len(product['department']) else ''
        genre_list[k] = product['genre'][k] if k < len(product['genre']) else ''
    result += department_list + genre_list + product['category']
    return result


def get_last_asin():
    try:
        with open('output.csv', 'r', encoding='utf-8') as file:
            last_row = None
            for row_in_last_output in csv.reader(file):
                last_row = row_in_last_output
            last_asin = None if last_row is None or len(last_row) == 0 else last_row[0]
            last_asin = None if not last_asin or last_asin == 'asin' else last_asin
            return last_asin
    except FileNotFoundError:
        return None


def write_bom(filename='output.csv'):
    with open(filename, 'wb') as file:
        file.write(codecs.BOM_UTF8)


def write_row(data, filename='output.csv'):
    try:
        with open(filename, 'a', encoding='utf-8') as file:
            writer = csv.writer(file, lineterminator='\n')
            writer.writerow(data)
            file.close()
    except IOError as e:
        print(e)
        print("請確認{} 沒有被另外一個程序使用")
        os.system("pause")
        write_row(data, filename)


def main():
    last_asin = get_last_asin()
    with open('asin.csv') as csv_file:
        asin_reader = csv.reader(csv_file)
        if last_asin is None:
            write_bom()
            headers = ['asin', 'country', 'price', 'sale_price', 'binding', 'star1', 'star2', 'star3', 'star4',
                       'star5', 'total_reviews', 'average_rating', 'sales_rank', 'release_date', 'department']
            headers += [''] * 4 + ['genre'] + [''] * 4 + ['category']
            write_row(headers)
        i = 0
        for row in asin_reader:
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
                if i == 500:
                    break
        if last_asin is not None:
            print('目前的output.csv與asin.csv不一致，請將output.csv刪除或更名並重新執行程式')


if '__main__' in __name__:
    # noinspection PyUnresolvedReferences
    try:
        main()
        # a = fetch("0316009156", "us")
        # print(a)
    except urllib.error.URLError:
        print("please check your network")
    except FileNotFoundError:
        print("asin.csv file not found")
    finally:
        try:
            row_count = 0
            with open('output.csv', 'r', encoding='utf-8') as output_file:
                reader = csv.reader(output_file)
                for output_row in reader:
                    row_count += 1
            if row_count == 1:
                os.remove('output.csv')
        except FileNotFoundError:
            pass
    os.system("pause")
