import random
import socket
import traceback
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
        print("API 503 service unavailable, retry...")
        return True
    else:
        print("API response error")
        print(ex)


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


def open_url(url, cookies=None, error_retry=2):
    while True:
        # noinspection PyUnresolvedReferences
        try:
            headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                                     "Chrome/42.0.2311.90 Safari/537.36 "}
            if cookies is not None:
                headers['Cookie'] = cookies

            api_request = urllib.request.Request(url, headers=headers)
            resource = urllib.request.urlopen(api_request, timeout=5)
            cookies = resource.getheader('Set-Cookie')
            review_response = resource.read()
            review_soup = BeautifulSoup(review_response, "lxml")
            return review_soup, cookies
        except urllib.error.HTTPError as url_http_error:
            if url_http_error.code == 503:
                time.sleep(random.expovariate(0.1))
                print('url request 503, retry...')
            else:
                print(url_http_error)
        except (urllib.error.URLError, socket.timeout) as url_error:
            print('url request error or timeout, retrying')
            error_retry -= 1
            if error_retry < 0:
                raise url_error
            else:
                continue


def fetch(asin, region, cookie=None):
    amazon = get_amazon_by_region(region)
    if amazon is None:
        return {"error": "region code not valid"}, cookie
    response = amazon.ItemLookup(ItemId=asin, ResponseGroup="BrowseNodes,ItemAttributes,Offers,Reviews,SalesRank")
    soup = BeautifulSoup(response, "lxml")
    if soup.error is not None:
        return {"error": soup.error.message.get_text()}, cookie

    result = {
        "binding": soup.binding,
        "sales_rank": soup.salesrank,
        "release_date": soup.publicationdate,
        "price": soup.formattedprice if soup.listprice is None else soup.listprice.formattedprice,
        "sale_price": None if soup.price is None else soup.price.formattedprice
    }
    # result_reviews = fetch_reviews(soup.iframeurl.text)
    result_reviews, new_cookie = fetch_review_with_normal_url(asin, region, cookie)
    result.update(result_reviews)
    fill_browse_node(result, soup)

    for key, value in result.items():
        if isinstance(value, bs4.element.Tag):
            result[key] = value.text
    return result, new_cookie


def fetch_reviews(iframe_url):
    time.sleep(1)
    review_soup = open_url(iframe_url)
    review_avg_star_node = review_soup.find('span', class_='crAvgStars')
    if review_avg_star_node is not None:
        reviews_count = int(re.split("[件 ]", review_avg_star_node.find_all('a')[-1].text)[0].replace(',', ''))
        stars_ratio = review_soup.find_all('div', class_='histoCount')
        average_rating = get_average_rating(review_soup.find('span', class_='asinReviewsSummary').img.attrs['alt'])
    else:
        reviews_count = 0
        stars_ratio = ['0'] * 5
        average_rating = 0

    return {
        "star1": get_star_count(reviews_count, stars_ratio[4].text),
        "star2": get_star_count(reviews_count, stars_ratio[3].text),
        "star3": get_star_count(reviews_count, stars_ratio[2].text),
        "star4": get_star_count(reviews_count, stars_ratio[1].text),
        "star5": get_star_count(reviews_count, stars_ratio[0].text),
        "total_reviews": reviews_count,
        "average_rating": average_rating
    }


def fetch_review_with_normal_url(asin, region, cookie):
    domain = "com" if region == "us" else "co.jp"
    review_url = "https://www.amazon.{}/reviews/{}".format(domain, asin)
    review_soup, new_cookie = open_url(review_url, cookie)
    review_block = review_soup.find('div', class_='reviewNumericalSummary')
    if review_block is not None:
        reviews_count = int(review_block.find('span', class_='totalReviewCount').text.replace(',', ''))
        average_rating = get_average_rating(review_block.find('div', class_='averageStarRatingNumerical').span.text)
        stars_ratio = [row.find_all('td')[-1].text for row in review_block.find_all('tr', class_='a-histogram-row')]
    else:
        reviews_count = None
        average_rating = None
        stars_ratio = [''] * 5

    return {
               "star1": get_star_count(reviews_count, stars_ratio[4]),
               "star2": get_star_count(reviews_count, stars_ratio[3]),
               "star3": get_star_count(reviews_count, stars_ratio[2]),
               "star4": get_star_count(reviews_count, stars_ratio[1]),
               "star5": get_star_count(reviews_count, stars_ratio[0]),
               "total_reviews": reviews_count,
               "average_rating": average_rating
           }, new_cookie


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
        # if root_name_node.text not in ['Departments', 'Subjects', 'ジャンル別', "Styles"]:
        #     continue
        # else:
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


def get_average_rating(origin_text):
    try:
        average_rating = float(origin_text.split(' ')[0])
        return average_rating
    except ValueError:
        try:
            return float(re.split('[ち ]', origin_text)[1])
        except ValueError:
            return 0


def get_star_count(reviews_count, star_ratio_text):
    if reviews_count == 0:
        return 0
    elif reviews_count is None:
        return None
    elif star_ratio_text.find('%') == -1:
        return int(star_ratio_text)
    else:
        return round(int(star_ratio_text[0:-1]) / 100 * reviews_count)


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
        print("請確認{} 沒有被另外一個程序使用".format(filename))
        os.system("pause")
        write_row(data, filename)


def get_proxy_list():
    proxy_list = []
    proxy_list_url = "http://www.us-proxy.org"
    soup, cookies = open_url(proxy_list_url)
    for tr in soup.table.find_all('tr')[1:-1]:
        tds = tr.find_all('td')
        if tds[6].text == "yes":
            proxy_list.append("{}:{}".format(tds[0].text, tds[1].text))
    print("got {} proxies from {}".format(len(proxy_list), proxy_list_url))
    return proxy_list
    # return ['104.236.203.134:8080']


used_proxy_list = []


def change_proxy():
    proxy_candidate = get_proxy_list()
    if len(proxy_candidate) == 0:
        print("no available proxy")
        return
    try:
        proxy_ip = list(set(proxy_candidate).difference(set(used_proxy_list))).pop()
    except IndexError:
        print("proxy list has all been used")
        used_proxy_list.clear()
        proxy_ip = random.choice(proxy_candidate)
    proxy = urllib.request.ProxyHandler({'https': proxy_ip})
    opener = urllib.request.build_opener(proxy)
    urllib.request.install_opener(opener)
    print("using proxy {}".format(proxy_ip))
    used_proxy_list.append(proxy_ip)
    try:
        open_url("https://www.amazon.co.jp", error_retry=0)
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout):
        change_proxy()


def main():
    last_asin = get_last_asin()
    cookie = None
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
            if i <= 1:
                continue
            if last_asin is not None:
                if row[0] == last_asin:
                    last_asin = None
                continue
            else:
                print(row)
                data_dict, new_cookie = fetch(row[0], row[1], cookie)
                cookie = new_cookie
                print(data_dict)

                if "total_reviews" in data_dict.keys() and data_dict['total_reviews'] is None:
                    change_proxy()
                    cookie = None
                if 'error' in data_dict.keys():
                    write_row(row + [data_dict['error']])
                    write_row(row + [data_dict['error']], filename='error.csv')
                else:
                    data_list = to_list(data_dict)
                    write_row(row + data_list)
                data_limit = 3500
                if i >= data_limit:
                    print("試用版只能抓取{}筆資料，程序中止。".format(data_limit))
                    break
        if last_asin is not None:
            print('目前的output.csv與asin.csv不一致，請將output.csv刪除或更名並重新執行程式')


if '__main__' in __name__:
    # noinspection PyUnresolvedReferences
    while True:
        try:
            change_proxy()
            main()
            print("所有ASIN已經抓取完畢，程式結束")
            # a = fetch("B001Y7SITI", "us")
            # print(a)
            break
        except urllib.error.URLError as e:
            print(e)
            print("please check your network")
        except FileNotFoundError:
            print("asin.csv file not found")
            break
        except Exception as unknown_error:
            print("Unexpected error {}".format(unknown_error))
            print(traceback.format_exc())
        # delete output.csv if no data writen
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
    print("last used proxy is {}".format(used_proxy_list[-1]))
    os.system("pause")