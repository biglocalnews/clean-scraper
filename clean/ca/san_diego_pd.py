import requests 
import time
from bs4 import BeautifulSoup

def scrape_top_level():

    top_level_urls = ['https://www.sandiego.gov/police/data-transparency/mandated-disclosures/sb16-sb1421-ab748']
    url = 'https://www.sandiego.gov/police/data-transparency/mandated-disclosures/sb16-sb1421-ab748'
    # page = requests.get(url) 

    # soup = BeautifulSoup(page.text, 'html.parser')
    # page_list = soup.find("div", class_="item-list")
    # list_item = page_list.find_all("li")
    # list_item = list_item[1:]

    base_url = 'https://www.sandiego.gov'
    # for item in list_item:
        
    #     if item.text.isnumeric():
    #         full_url = base_url + item.a['href']
    #         top_level_urls.append(full_url)

    scrape_each_top_page(top_level_urls, base_url)
    return top_level_urls

def download_case_files(base_url, second_level_urls):

    all_case_content_links = []

        for url in second_level_urls.keys():
            page = requests.get(url) 

            time.sleep(.5)
            soup = BeautifulSoup(page.text, 'html.parser')
            content = soup.find_all("div", class_="odd") # don't forget to add even...

            for item in content:
                text = item.text
                paragraph = item.find("p")
                print(paragraph.a['href'])
                all_case_content_links.append(text)
                print('_______________________')

            



        return

def scrape_each_top_page(top_level_urls, base_url):

    second_level_urls = {}

    for top_url in top_level_urls:
        page = requests.get(top_url) 
        
        time.sleep(.5)
        soup = BeautifulSoup(page.text, 'html.parser')
        six_columns = soup.find_all("div", class_="six columns")
        for elem in six_columns:
            paragraph_with_link = elem.find("p")
            if paragraph_with_link == None:
                continue
            else:
                text = paragraph_with_link.text
                elem_a = paragraph_with_link.find("a")
                if elem_a == None:
                    continue
                else:
                    full_link = base_url + elem_a['href']
                    second_level_urls[full_link] = text

    download_case_files(base_url, second_level_urls)

    return second_level_urls

    


scrape_top_level()