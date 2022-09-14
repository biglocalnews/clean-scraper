import requests 
import os
import time
import csv
from pathlib import Path
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
    error_links = []

    # all we need for the info is pages, folders, all_case_content_links, error_links

    all_case_content_links = [] 
    all_case_content_text = []
    file_path_names = []
    folders = []
    years = []

    folder = None

    for url in second_level_urls.keys():
        page = requests.get(url) 

        folder = second_level_urls[url]
        year = folder[6:10]
        
        if not os.path.exists(f'files/{year}/{folder}'):
            os.mkdir(f'files/{year}/{folder}')

        time.sleep(.5)
        soup = BeautifulSoup(page.text, 'html.parser')
        content = soup.find_all("div", class_="field-item even")
        
        for item in content:
            if item.find("div", class_="view-content") == None:
                pass
            else:
                view_content = item.find("div", class_="view-content")
                print('___')
                paragraph = view_content.find_all("p")
                for paragraph_item in paragraph:
                    text = paragraph_item.text
                    link = paragraph_item.a['href']
                    maybe_ab748 = link[32:38]
                    
      
                    all_case_content_links.append(link)
                    all_case_content_text.append(text)
                    folders.append(folder)
                    years.append(year)
                    print('')

                    record_text = "".join(text.split())
                    file_name = f'files/{year}/{folder}/{record_text}' 
                    path = Path(file_name)
                    file_path_names.append(file_name)

                    if path.is_file():
                        print(f'The file {file_name} exists')
                        error_links.append('Existing file')
                    elif 'AB 748' == maybe_ab748:
                        print("THIS IS AN AB748 LINK!!")
                        error_links.append('AB748 Link - no file downloaded')
                    else: 
                        try:
                            r = requests.get(link, stream = True)

                            #download started
                            with open(file_name, 'wb') as f:
                                for chunk in r.iter_content(chunk_size = 1024):
                                    if chunk:
                                        f.write(chunk)
                                        f.flush()
                        
                            print ("%s downloaded!\n"%file_name)
                            time.sleep(.5)
                            print('________________________________________________')
                            error_links.append('No error: new file downloaded')

                        except:
                            print(f'There was an issue downloading this file: {link}')
                            error_links.append(link)


    output_info(years, folders, all_case_content_links, error_links)
 
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

        view_content = soup.find_all("div", class_="view-content")
        headers = view_content[1].find_all("h2")

        for header in headers:

            header_folder = header.text
            header_folder = "".join(header_folder.split())

            if not os.path.exists(f'files/{header_folder}'):
                os.mkdir(f'files/{header_folder}')


    
    # print(len(second_level_urls)) # comment out lines 109-120 when download is verified

    i = 50
    while i > 4:
        second_level_urls.popitem()
        i-=1

    print('----------------------------------------')

    info_links = download_case_files(base_url, second_level_urls) # comment back in
    return 

def output_info(years, folders, all_case_content_links, error_links):

    output_data = [['YEAR','FOLDER','LINK','ERROR']]
    for year, folder, link, error in zip(years, folders, all_case_content_links, error_links):
        output_data.append([year, folder, link, error])


    with open("files/scrape_output.csv", "w") as f:
        wr = csv.writer(f)
        wr.writerows(output_data)
    
    print('Scrape output sent to csv file')



scrape_top_level()