import csv
import time
import random
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import urllib.parse

# 目标城市列表 (共30个)
target_cities = [
    "郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳",
    "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "济源",
    "邢台", "邯郸", "长治", "晋城", "运城", "聊城", "菏泽",
    "淮北", "亳州", "宿州", "蚌埠", "阜阳"
]

# 目标年份范围 (2011-2020)
target_years = list(range(2011, 2021))

# 新闻列表页URL
start_url = "https://www.gov.cn/yaowen/liebiao/"

# 输出文件名
output_file = "gov_filtered_news.csv"

def setup_driver():
    """配置并启动 Chrome WebDriver"""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")      # 无头模式，正式运行时取消注释
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # 请将下方的路径修改为你的chromedriver.exe所在的目录
    chrome_driver_path = r"C:\path\to\your\chromedriver.exe"
    # chrome_driver_path = r"D:\LenovoSoftstore\mysoft\chromedriver_win32\chromedriver.exe"
    driver = webdriver.Chrome(executable_path=chrome_driver_path, options=chrome_options)
    return driver

def parse_news_from_page(driver):
    """解析当前页面的新闻列表，返回新闻列表"""
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.news_list h4 a"))
    )
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    news_list = []
    # 这里新闻列表的CSS选择器可能会变，请根据实际页面结构调整
    for news_item in soup.select('div.news_list h4 a'):
        title = news_item.get_text(strip=True)
        link = news_item.get('href', '')
        # 将相对路径补全为完整URL
        if link.startswith('/'):
            link = urllib.parse.urljoin(start_url, link)
        news_list.append({
            'title': title,
            'link': link,
        })
    return news_list

def extract_date_from_news_detail(driver, url):
    """进入新闻详情页，提取发布日期"""
    try:
        driver.get(url)
        # 等待日期元素加载，选择器可能需微调
        date_elem = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.pub_date, div.info, span.date"))
        )
        date_text = date_elem.get_attribute('data-time') or date_elem.text
        # 正则提取日期 "2024-12-18" 格式
        match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day)
    except Exception:
        # 解析失败则返回None
        return None
    return None

def should_collect_news(title, pub_date):
    """判断是否应采集该新闻（基于年份及城市）"""
    if pub_date is None:
        return False
    if pub_date.year not in target_years:
        return False
    for city in target_cities:
        if city in title:
            return True
    return False

def main():
    driver = setup_driver()
    driver.get(start_url)
    
    # 存储收集到的新闻
    collected_news = []
    page_num = 1

    try:
        while True:
            print(f"正在采集第 {page_num} 页...")
            # 1. 解析当前页新闻标题与链接
            current_news = parse_news_from_page(driver)
            if not current_news:
                print("当前页无新闻，停止翻页。")
                break
            
            # 2. 对当前页每条新闻进入详情页提取日期并判断
            for idx, news in enumerate(current_news, 1):
                print(f"  处理第 {page_num} 页的第 {idx} 条新闻: {news['title']}")
                # 进入详情页提取日期（该操作会跳转，需注意driver当前页面状态）
                pub_date = extract_date_from_news_detail(driver, news['link'])
                if should_collect_news(news['title'], pub_date):
                    collected_news.append({
                        'title': news['title'],
                        'link': news['link'],
                        'date': pub_date.strftime('%Y-%m-%d') if pub_date else '日期不详'
                    })
                    print(f"    ✔ 采集匹配新闻: {news['title']} （日期: {pub_date.strftime('%Y-%m-%d') if pub_date else '日期不详'}）")
                else:
                    print(f"    ✘ 不符合过滤条件，跳过")
                # 返回列表页（由于详情页覆盖了driver，需重新访问列表页并等待加载）
                driver.back()
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.news_list h4 a"))
                )
                # 随机延时，降低请求频率
                time.sleep(random.uniform(1, 3))

            # 3. 查找“下一页”按钮并点击
            try:
                next_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "下一页"))
                )
                if next_btn:
                    print("点击‘下一页’...")
                    next_btn.click()
                    page_num += 1
                    # 翻页后等待新数据加载
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.news_list h4 a"))
                    )
                    time.sleep(random.uniform(1, 3))
                else:
                    print("未找到‘下一页’按钮，爬取结束。")
                    break
            except Exception as e:
                print(f"无下一页或点击失败: {e}，爬取结束。")
                break

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        driver.quit()
        # 将结果写入CSV文件
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['title', 'link', 'date'])
            writer.writeheader()
            writer.writerows(collected_news)
        print(f"采集完成，共 {len(collected_news)} 条匹配新闻，已保存到 {output_file}")

if __name__ == "__main__":
    main()