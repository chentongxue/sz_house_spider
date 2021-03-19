# coding=utf-8
import re
import datetime
import requests


class Project(object):
    def __init__(self, serial_num, project_id, name, company, area, time):
        self.name = name
        self.company = company
        self.area = area
        self.time = datetime.datetime.strptime(time, '%Y-%m-%d')
        self.serial_num = int(serial_num)
        self.project_id = project_id

    def __repr__(self):
        return self.name.encode('utf-8')


class Branch(object):
    def __init__(self, branch_id, name):
        self.branch_id = branch_id
        self.name = name
        self.houses = []  # 预售期房


class House(object):
    def __init__(self, floor, number, unit_price, construction_area, indoor_area, share_area, use, house_id):
        self.floor = floor  # 楼层
        self.number = number  # 房号
        self.unit_price = unit_price  # 拟售价格(平米)
        self.construction_area = construction_area  # 建筑面积
        self.indoor_area = indoor_area  # 套内面积
        self.share_area = share_area  # 分摊面积
        self.use = use  # 用途
        self.house_id = house_id

    @property
    def total_price(self):
        return float(self.unit_price) * float(self.construction_area)


class Building(object):
    def __init__(self, building_id):
        self.building_id = building_id
        self.houses = []


class ProjectListSpider(object):
    def __init__(self):
        self.projects = []
        self.end_time = datetime.datetime(2020, 1, 1)
        self.init()

    def init(self):
        self.get_projects()

    def get_projects(self):
        url = 'http://zjj.sz.gov.cn/ris/bol/szfdc/index.aspx'
        response = requests.get(url)
        data = {
            'scriptManager2': 'updatepanel2|AspNetPager1',
            '__EVENTTARGET': 'AspNetPager1',
            '__VIEWSTATE': self.get_text_by_regex('<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="(.*?)" />', response.text),
            '__VIEWSTATEGENERATOR': self.get_text_by_regex('<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="(.*?)" />', response.text),
            '__EVENTVALIDATION': self.get_text_by_regex('<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="(.*?)" />', response.text),
            'ddlPageCount': 20,
            '__EVENTARGUMENT': 1,
            '__LASTFOCUS': '',
            '__VIEWSTATEENCRYPTED': '',
            'tep_name': '',
            'organ_name': '',
            'site_address': '',
        }

        end = False
        while 1:
            response = requests.post(url, data=data)
            projects = self.parse_project_trs(response.text)
            for project in projects:
                if project.time < self.end_time:
                    end = True
                    break

                self.projects.append(project)

            if end:
                break
            data['__EVENTARGUMENT'] += 1

    @staticmethod
    def get_text_by_regex(rule, text):
        regex = re.compile(rule)
        return regex.findall(text).pop()

    def parse_project_trs(self, html):
        result = re.findall(r'<tr.*?>(.*?)</tr>', html, re.S | re.M)
        projects = []
        for tr in result:
            project = self.parse_project_tr(tr)
            if not project:
                continue
            projects.append(project)
        return projects

    def parse_project_tr(self, tr):
        result = re.findall(r'<td>(.*?)</td>', tr, re.S | re.M)
        if result:
            detail_result = re.findall(r"<a href='projectdetail.aspx\?id=(\d+)' target='_self'>(.*?)</a>", result[2], re.S | re.M)
            detail = detail_result.pop()
            data = {
                'serial_num': result[0].strip(),
                'project_id': detail[0].strip(),
                'name': detail[1].strip(),
                'company': result[3].strip(),
                'area': result[4].strip(),
                'time': result[5].strip(),
            }
            return Project(**data)


class ProjectSpider(object):
    def __init__(self, project_id):
        self.project_id = project_id
        self.building_list = []

    def get_building_list(self):
        url = 'http://zjj.sz.gov.cn/ris/bol/szfdc/projectdetail.aspx?id=%s' % self.project_id
        response = requests.get(url)
        self.parse_building(response.text)

    def parse_building(self, html):
        # 屏蔽40年使用期限
        if re.findall(u'(\d+)年<br />', html)[0] != '70':
            return

        regex = re.compile("<a href='building.aspx\?id=(\d+)&presellid=\d+'.*?target='_self'>.*?</a>", re.S | re.M)
        for building_id in regex.findall(html):
            building = Building(building_id)

            branch_spider = BranchSpider(building_id, self.project_id)
            branch_spider.get_branch_list()
            for house_id in branch_spider.house_id_list:
                house_spider = HouseSpider(house_id)
                house = house_spider.get_house()
                if not house:
                    continue
                building.houses.append(house)
            self.building_list.append(building)


class BranchSpider(object):
    def __init__(self, building_id, project_id):
        self.building_id = building_id
        self.project_id = project_id
        self.house_id_list = []

    def get_branch_list(self):
        url = 'http://zjj.sz.gov.cn/ris/bol/szfdc/building.aspx?id=%s&presellid=%s' % (self.building_id, self.project_id)
        response = requests.get(url)
        self.parse_branch(response.text)

    def parse_branch(self, html):
        regex = re.compile("<a href='building.aspx\?id=\d+&presellid=\d+&Branch=.*?&.*?'.*?>\[(.*?)\]</a>")
        for branch_name in regex.findall(html):
            self.get_house_id_list(branch_name)

    def get_house_id_list(self, branch_name):
        url = 'http://zjj.sz.gov.cn/ris/bol/szfdc/building.aspx'
        data = {
            'id': self.building_id,
            'presellid': self.project_id,
            'Branch': branch_name,
            'isBlock': 'ys',
        }
        response = requests.get(url, data)
        self.parse_houses(response.text)

    def parse_houses(self, html):
        regex = re.compile(u"<a href='housedetail.aspx\?id=(\d+)'.*?>(.*?) ")
        for house_id, state in regex.findall(html):
            if state == u'期房待售':
                self.house_id_list.append(house_id)


class HouseSpider(object):
    def __init__(self, house_id):
        self.house_id = house_id

    def get_house(self):
        url = 'http://zjj.sz.gov.cn/ris/bol/szfdc/housedetail.aspx?id=%s' % self.house_id
        response = requests.get(url)
        data = {
            'floor': self.get_text_by_regex(u'<td align="center">.*?楼层.*?</td>.*?<td align="center">.*?(\d+)&nbsp;.*?</td>', response.text),
            'number': self.get_text_by_regex(u'<td align="center">.*?房号.*?</td>.*?<td align="center">(.*?)&nbsp;.*?</td>', response.text),
            'unit_price': self.get_text_by_regex(u'<td align="center">.*?拟售价格.*?</td>.*?<td colspan="3">(.*?)元/平方米\(按建筑面积计\).*?</td>', response.text),
            'construction_area': self.get_text_by_regex(u'预售查丈.*?<tr>.*?<td align="center">.*?建筑面积.*?</td>.*?<td>(.*?)平方米.*?</td>', response.text),
            'indoor_area': self.get_text_by_regex(u'<td align="center">.*?户内面积.*?</td>.*?<td>(.*?)平方米.*?</td>', response.text),
            'share_area': self.get_text_by_regex(u'<td align="center">.*?分摊面积.*?</td>.*?<td>(.*?)平方米.*?</td>', response.text),
            'use': self.get_text_by_regex(u'<td align="center">.*?用途.*?</td>.*?<td>(.*?)&nbsp;.*?</td>', response.text),
            'house_id': self.house_id,
        }
        if data['unit_price'] == '--':
            return
        return House(**data)

    def get_text_by_regex(self, rule, html):
        regex = re.compile(rule, re.S | re.M)
        try:
            return regex.findall(html)[0].strip()
        except:
            print 'ERROR!!', rule, 'house_id:', self.house_id
            return '--'


def main():
    area_list = [u'光明']  # u'光明', u'罗湖', u'龙华', u'福田',
    total_price = 4000000.0  # 房屋总价

    spider = ProjectListSpider()
    for project in spider.projects:
        if project.area not in area_list:  # u'光明', u'罗湖', u'龙华', u'福田',
            continue

        print u'楼盘名称: {} 地区: {}, 详情: {}'.format(
            project.name,
            project.area,
            'http://zjj.sz.gov.cn/ris/bol/szfdc/projectdetail.aspx?id=%s' % project.project_id
        )
        project_spider = ProjectSpider(project.project_id)
        project_spider.get_building_list()
        for building in project_spider.building_list:
            for house in building.houses:
                if house.total_price < total_price and house.use == u'住宅':
                    print u'建筑面积: {} 公摊: {} 楼层: {} 房号: {} 单价: {} 套内面积: {} 用途: {} 总价: {} 详情:{}'.format(
                        house.construction_area,
                        house.share_area,
                        house.floor,
                        house.number,
                        house.unit_price,
                        house.indoor_area,
                        house.use,
                        house.total_price,
                        'http://zjj.sz.gov.cn/ris/bol/szfdc/housedetail.aspx?id=%s' % house.house_id
                    )


if __name__ == '__main__':
    main()
