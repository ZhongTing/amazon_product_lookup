import urllib.request
import csv
import bottlenose
import bs4
from bs4 import BeautifulSoup


def test():
    amazonUs = bottlenose.Amazon("AKIAIN7FKTAMCSG7VVOA", "DtH54N5NoOX5tGDKZ5N8283IyfKzuOQ6fbg3KhC8", "gary62107-20")
    amazonJp = bottlenose.Amazon("AKIAIN7FKTAMCSG7VVOA", "DtH54N5NoOX5tGDKZ5N8283IyfKzuOQ6fbg3KhC8", "gary62107-22",
                                 Region="JP")
    response = amazonUs.ItemLookup(ItemId="0060590327", ResponseGroup="Small")

    response = str(response)
    soup = BeautifulSoup(response, "lxml")
    url = soup.find('detailpageurl').get_text()
    response = urllib.request.urlopen(url).read()
    soup = BeautifulSoup(response, "lxml")


def get_amazon_by_region(region):
    access_key = "AKIAIN7FKTAMCSG7VVOA"
    secret = "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"
    if region == 'us':
        return bottlenose.Amazon(access_key, secret, "gary62107-20")
    elif region == 'jp':
        return bottlenose.Amazon(access_key, secret, "gary62107-22", Region="JP")
    else:
        return None


def fetch(asin, region):
    amazon = get_amazon_by_region(region)
    if amazon is None:
        return {"msg": "region code not valid"}
    response = amazon.ItemLookup(ItemId=asin, ResponseGroup="BrowseNodes,ItemAttributes,Offers,Reviews,SalesRank")
    soup = BeautifulSoup(response, "lxml")
    if soup.error is not None:
        return {"msg": soup.error.message.get_text()}

    review_response = urllib.request.urlopen(soup.iframeurl.text).read()
    review_soup = BeautifulSoup(review_response, "lxml")

    result = {}
    result["price"] = soup.formattedprice
    result["star1"] = -1
    result["star2"] = -1
    result["star3"] = -1
    result["star4"] = -1
    result["star5"] = -1
    result["reviews"] = -1
    result["average_rating"] = -1
    result["sales_rank"] = soup.salesrank
    result["category"] = ", ".join([node.find('name').text for node in soup.select("browsenodes > browsenode")])
    result["release_date"] = soup.releasedate
    result["url"] = soup.detailpageurl

    for key, value in result.items():
        if isinstance(value, bs4.element.Tag):
            result[key] = value.text
    return result


def to_list(arg_dict):
    result = []
    for key, value in arg_dict.items():
        result.append(value)
    return result


def get_last_asin():
    try:
        with open('output.csv', 'r') as file:
            last_row = None
            for row_in_last_output in csv.reader(file):
                last_row = row_in_last_output
            return None if last_row is None else last_row[0]
    except FileNotFoundError:
        return None


def main():
    last_asin = get_last_asin()
    with open('output.csv', 'a') as output_file:
        with open('asin.csv') as csv_file:
            try:
                reader = csv.reader(csv_file)
                writer = csv.writer(output_file)
                if last_asin is None:
                    writer.writerow(['asin', 'country', 'price', 'star1', 'star2', 'star3', 'star4', 'star5', 'reviews',
                                     'average_rating', 'sales_rank', 'category', 'release_date'])
                i = 0
                for row in reader:
                    print(row)
                    i += 1
                    if i == 1:
                        continue
                    if last_asin is not None:
                        if row[0] == last_asin:
                            last_asin = None
                        continue
                    else:
                        data_dict = fetch(row[0], row[1])
                        print(data_dict)
                        data_list = to_list(data_dict)
                        writer.writerow(row + data_list)
                        if i == 20:
                            break
            finally:
                output_file.close()


if __name__ == '__main__':
    main()
    # a = fetch("0060590327", "us")
    # print(a)
