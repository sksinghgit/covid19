#!/usr/bin/python3

# Ref: https://srome.github.io/Parsing-HTML-Tables-in-Python-with-BeautifulSoup-and-pandas/

from __future__ import absolute_import, division

import sys
import json
import os

from bs4 import BeautifulSoup, NavigableString
import pandas as pd
import requests
from tabulate import tabulate
from collections import OrderedDict
import logging
import time

logger = logging.getLogger('covid19.Scrapper')
TABLE_COLUMNS = ["Country", "Cases", "NCases", "Deaths",
                 "NDeaths", "Recovered", "Active", "Critical",
                 "CPM", "DPM", "Tests", "TPM", "Continents"]

CHART_TYPES = {'coronavirus-cases-linear' : 'Total Cases', # Total coronavirus cases
               'graph-cases-daily' : 'New Cases',        # Daily cases
               'graph-active-cases-total' : 'Active Cases',
               'coronavirus-deaths-linear' : 'Total Deaths', # Total deaths
               'graph-deaths-daily' : 'New Deaths'}        # Daily deaths


class CovidData(object):
    URL = 'https://www.worldometers.info/coronavirus/'
    OUT_FILE = 'worldometer_covid19.json'
    CP_FILE = "cp"

    def __init__(self):
        self.logger = logging.getLogger('covid19.Scrapper.CovidData')
        self.url = CovidData.URL
        self.live_column_names = []

    def __get_gmt_date(self):
        return time.strftime("%d/%m/%Y %Z", time.gmtime())

    def __is_reload_req(self):
        reload = True
        if os.path.isfile(CovidData.CP_FILE):
            with open(CovidData.CP_FILE) as fd:
                reload = (fd.read() != self.__get_gmt_date())
        if not os.path.isfile(CovidData.OUT_FILE):
            reload = True

        return reload

    def __touch_cp_file(self):
        with open(CovidData.CP_FILE, 'w') as fd:
            fd.write(self.__get_gmt_date())

    def __fetch_all_countries_data(self, out_file):
        response = requests.get(self.url)
        soup = BeautifulSoup(response.text, 'lxml')
        countries_url = OrderedDict()
        for a in soup.find_all('a', href=True):
            if a['href'].startswith('country'):
                countries_url[a.text] = os.path.join(self.url, a['href'])
        countries_data = OrderedDict()
        for country, url in countries_url.items():
            countries_data[country] = self.__parse_country_data(url)

        with open(out_file, 'w') as fd:
            json.dump(countries_data, fd)

    def __parse_country_data(self, country_url):
        self.logger.info("Fetching data from %s", country_url)
        soup = BeautifulSoup(requests.get(country_url).text, "lxml")
        all_scripts = soup.find_all('script')
        data = OrderedDict()
        for script in all_scripts:
            script = script.text
            for char_type in CHART_TYPES:
                if char_type in script:
                    chart_name = CHART_TYPES[char_type]
                    self.logger.info("Populating data for %s", chart_name)
                    sys.stdout.flush()
                    #self.logger.info("%s: %s", index, char_type)
                    chart_data = script.split('data: [', 1)[1].split(']', 1)[0]
                    chart_data = '[' + chart_data + ']' # create correct JSON data
                    chart_data = json.loads(chart_data)

                    # Extract dates
                    chart_date = script.split('categories: [', 1)[1].split(']', 1)[0]
                    chart_date = '[' + chart_date + ']' # create correct JSON data
                    chart_date = json.loads(chart_date)

                    for i in range(len(chart_date)):
                        if chart_date[i] not in data:
                            data[chart_date[i]] = dict()

                        data[chart_date[i]][chart_name] = chart_data[i]
                        data[chart_date[i]]['date'] = chart_date[i]
        ret_data = []
        for dt in data:
            ret_data.append(data[dt])

        return ret_data

    def __get_live_stats(self):
        response = requests.get(self.url)
        soup = BeautifulSoup(response.text, 'lxml')
        return [(table['id'], self.__parse_html_table(table))
                for table in soup.find_all('table')]

    def __parse_html_table(self, table):
        self.live_column_names = []

        # get <thead> and extract column names from it
        thead = table.find_all('thead')[0]
        th_tags = thead.find_all('th')

        for th in th_tags:
            col_name = []
            for item in th.contents:
                if isinstance(item, NavigableString):
                    col_name.append(item.strip(',+').strip())
                elif item.get_text().strip():
                    col_name.append(item.get_text().strip())
            self.live_column_names.append(' '.join(col_name))

        # get the first <tbody> and extract data
        tbody = table.find_all('tbody')[0]
        # list of lists from tr/td elements
        data = [
            [td.get_text().strip().replace(',', '').strip('+')
             for td in row.find_all('td')]
            for row in tbody.find_all('tr')]

        df = pd.DataFrame(data, columns=self.live_column_names)

        sorting_allowed = True
        # though we get column names from worldometers, we would like
        # our own compact names to help with display, sorting etc
        if len(df.columns) == len(TABLE_COLUMNS):
            df.columns = TABLE_COLUMNS
        else:
            self.logger.warning("Number of columns is not as expected, sorting will not work.")
            sorting_allowed = False
        # replace empty strings with 0 in all columns
        # (does not impact the 'Country' column as it has data)
        for col in df.columns:
            df[col] = df[col].replace('', 0)

        if sorting_allowed:
            # convert a few columns to 'int'
            for col in ["Cases", "NCases", "Deaths",
                        "NDeaths", "Recovered", "Active",
                        "Critical", "Tests"]:
                try:
                    df[col] = df[col].astype(int)
                except ValueError as ve:
                    self.logger.error("int(col) gave value error for %s, %s", col, str(ve))

            # convert a few columns to 'float'
            for col in ["CPM", "DPM", "TPM"]:
                try:
                    df[col] = df[col].astype(float)
                except ValueError as ve:
                    self.logger.error("float(col) gave value error for %s, %s", col, str(ve))

        return df, sorting_allowed

    def get_live_columns(self):
        if len(self.live_column_names) == 0:
            self.__get_live_stats()
        return TABLE_COLUMNS, self.live_column_names

    def get_todays_stats(self):
        table, _ = self.__get_live_stats()[0][1]
        table = table[table['Country'] != table['Continents']]
        return table.sort_values(by=['Cases'], ascending=False)

    def get_historical_data(self):
        if self.__is_reload_req():
            self.__fetch_all_countries_data(CovidData.OUT_FILE)
            self.__touch_cp_file()

        with open(CovidData.OUT_FILE) as fd:
            data = json.load(fd)

        return data


def display_stats(table):
    print(tabulate(table, headers=["#"] + list(table.columns),
                   tablefmt='psql'))


def main():
    hp = CovidData()
    #print(hp.get_todays_stats())
    print(time.strftime("%d/%m/%Y %I:%M:%S %p %Z", time.gmtime()))

if __name__ == "__main__":
    main()