import requests 
import time
from bs4 import BeautifulSoup

def scrape_top_level():

    # visits the main page (where SDPD data starts)
    # pulls the links of other top-level pages

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

    # Goes to the individual case links for SDPD
    # Downloads the files on those individual pages


    all_case_content_links = [] 
    all_case_content_text = []

    # /Users/dilcia_mercedes/Big_Local_News/2022_code/sandiego_scrape/

    for url in second_level_urls.keys():
        page = requests.get(url) 

        time.sleep(.5)
        soup = BeautifulSoup(page.text, 'html.parser')
        content = soup.find_all("div", class_="odd") # don't forget to add even...

        for item in content:
            text = item.text
            paragraph = item.find("p")
            print(paragraph.a['href'])
            all_case_content_links.append(paragraph.a['href'])
            all_case_content_text.append(text)
            print('_______________________')

    

    test_links = all_case_content_links[0:10]
    test_text = all_case_content_text[0:10]

    # for record in test_links: # swap `test_links` out for `all_case_content_links` full scrape
    # also swap out `test_text`
    for (record, record_text) in zip(test_links, test_text):
        
        print(record)
        record_text = "".join(record_text.split())
        # file_name = f'files/{record_text[1:]}' 
        file_name = f'files/{record_text}' 

        
        r = requests.get(record, stream = True)

        #download started
        with open(file_name, 'wb') as f:
            # chunk_size = 1024*1024
            for chunk in r.iter_content(chunk_size = 1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
    
        print ("%s downloaded!\n"%file_name)
        time.sleep(.5)
        print('_______________________')


    return

def scrape_each_top_page(top_level_urls, base_url):

    # Uses the links of the 6 top-level pages of SDPD and scrapes all links on each page
    # The links on those top-level pages lead to the pages of individual SDPD cases
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

    
    print(len(second_level_urls)) # comment out lines 109-120 when download is verified

    # print(second_level_urls)
    i = 50
    while i > 1:
        second_level_urls.popitem()
        i-=1

    print('----------------------------------------')
    print(len(second_level_urls))

    print(second_level_urls)

    download_case_files(base_url, second_level_urls) # comment back in
    return second_level_urls



    


scrape_top_level()