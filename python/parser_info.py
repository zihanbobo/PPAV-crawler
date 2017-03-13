#!/usr/bin/env python3

import re
import datetime
import json
from parser_link import ParserLink
from parser import parse_webpage, get_code_info
from mongodb import MongoOP

class ParserInfo:

    def __init__(self, mongo_uri):
        self.film_infos = []
        self.mongo = MongoOP(mongo_uri)
        self.tags_dict = None

    @classmethod
    def code_special_case(cls, code):
        if 'TOKYO-HOT' in code:
            return re.sub('TOKYO-HOT-', '', code)
        elif 'GACHINCO' in code:
            return re.sub('GACHINCO-', '', code)
        elif 'CARIB' in code and \
             'CARIBPR' not in code:
            code_re = '([0-9]+-[0-9]+)'
            code = re.search(code_re, code)
            if code is None:
                return
            else:
                return code.group()
        elif 'CARIBPR' in code or \
             'PACO' in code or \
             '10MU' in code or \
             '1PONDO' in code:
            code_re = '([0-9]+-[0-9]+)'
            code = re.search(code_re, code)
            if code is not None:
                code = code.group().replace('-', '_')
                return code
        else:
            return code

    def translate_tags(self, tag_arr):
        if self.tags_dict is None:
            with open('tags.json') as tags_fp:
                self.tags_dict = json.load(tags_fp)
        tag_arr = [self.tags_dict[key] if key in self.tags_dict else key \
                    for key in tag_arr]
        return tag_arr

    def get_film_info(self, url):
        page_film = parse_webpage(url)

        video_code_re = '(?<=watch-)(\\w+-){0,2}\\w*\\d+'
        video_code = re.search(video_code_re, url)
        if video_code is None or page_film is None:
            return None
        video_code = video_code.group().upper()
        search_video_code = self.code_special_case(video_code)

        view_count_re = '<div class=\"film_view_count\".*?>\\d*</div>'
        view_count_str = re.search(view_count_re, page_film).group()
        view_count_str = re.sub('<.*?>', '', view_count_str)

        model_re = '<.*>Models:.*?>.*?>'
        model = re.search(model_re, page_film).group()
        model = re.sub('<.*?>', '', model)
        model = re.sub('Models: ', '', model)

        title_re = '<title>(.*)</title>'
        title = re.search(title_re, page_film).group()
        title = re.sub('<.*?>', '', title)

        img_url_re = '<img itemprop=\"image\" src=\"(.*?)\" title=\"'
        img_url = re.search(img_url_re, page_film).group(1)

        tag_re = '<li>Genre:\\s*(.*?)</li>'
        tag = re.search(tag_re, page_film).group(1)
        tag_re = '<a.*?>(.*?)</a>'
        tag = re.findall(tag_re, tag)
        tag = self.translate_tags(tag)
        print(tag)

        if self.mongo.info_is_exists(url):
            info = {}
            info['from'] = 'xonline'
            info['url'] = url
            info['count'] = int(view_count_str)
            info['update_date'] = datetime.datetime.now()
            info['tags'] = tag
            return info
        else:
            if search_video_code is not None:   # filter some films don't have code number
                info_obj = self.get_code_info(search_video_code)
                if info_obj['model'] is not None:
                    model = info_obj['model']
                if info_obj['video_title'] is not None:
                    title = info_obj['video_title']

            info = {}
            info['from'] = 'xonline'
            info['code'] = video_code
            info['search_code'] = search_video_code
            info['url'] = url
            info['count'] = int(view_count_str)
            info['img_url'] = img_url
            info['models'] = model
            info['title'] = title
            info['update_date'] = datetime.datetime.now()
            info['tags'] = tag
            return info

    def parse_info_and_update(self, film_url_json_list, collect_name=None):
        for idx, url_json in enumerate(film_url_json_list):
            url = url_json['url']
            print(idx, url)
            date_info = self.mongo.get_url_update_date(url, collect_name)
            diff_days = 3   # the days difference between today and last update_date

            if date_info is not None \
                and (datetime.date.today() - date_info['update_date'].date()).days <= diff_days:
                print("update_date is {}, skip it".format(date_info['update_date']))
                continue

            info = self.get_film_info(url)

            if info:
                self.mongo.update_json_list([info], collect_name)
            else:
                self.mongo.delete_url(url, collect_name)
