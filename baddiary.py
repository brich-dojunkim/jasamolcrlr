import time
import random
import re
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import urllib.parse

def setup_driver():
    """셀레늄 웹드라이버 설정"""
    # 크롬 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드 (브라우저 창 표시 안 함)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
    
    # 크롬 드라이버 설정
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def extract_product_info(product_element):
    """상품 요소에서 정보 추출"""
    try:
        # 상품명
        product_name = ""
        try:
            product_name = product_element.find_element(By.CSS_SELECTOR, '.name a').text.strip()
        except NoSuchElementException:
            pass
        
        # 상품 URL
        product_url = ""
        try:
            product_url = product_element.find_element(By.CSS_SELECTOR, '.name a').get_attribute('href')
        except NoSuchElementException:
            pass
        
        # 상품 설명
        product_desc = ''
        try:
            product_desc = product_element.find_element(By.CSS_SELECTOR, '.xans-record- [rel="상품 요약설명"] span:last-child').text.strip()
        except NoSuchElementException:
            pass
        
        # 이미지 URL
        image_url = ''
        try:
            img_element = product_element.find_element(By.CSS_SELECTOR, '.thumbnail img')
            image_url = img_element.get_attribute('src')
            # 이미지가 지연 로딩되는 경우 확인
            if not image_url or image_url == "":
                image_url = img_element.get_attribute('data-src')
        except NoSuchElementException:
            pass
        
        # 정가 (할인이 있는 경우)
        original_price = None
        try:
            price_element = product_element.find_element(By.CSS_SELECTOR, '.xans-record- [rel="판매가"] span')
            original_price_text = price_element.text.strip()
            if "원" in original_price_text:
                original_price = re.sub(r'[^\d]', '', original_price_text)
        except NoSuchElementException:
            pass
        
        # 할인가 (할인이 있는 경우)
        discounted_price = None
        try:
            discount_element = product_element.find_element(By.CSS_SELECTOR, '.xans-record- [rel="할인판매가"] span')
            discount_text = discount_element.text.strip()
            discount_match = re.search(r'(\d+,?\d+)원', discount_text)
            if discount_match:
                discounted_price = re.sub(r'[^\d]', '', discount_match.group(1))
        except NoSuchElementException:
            # 할인이 없는 경우 원래 가격을 판매가로 설정
            if original_price:
                discounted_price = original_price
                original_price = None
        
        # 할인율
        discount_rate = None
        try:
            sale_element = product_element.find_element(By.CSS_SELECTOR, '.xans-record- [rel="할인판매가"] span span')
            discount_text = sale_element.text.strip()
            discount_match = re.search(r'(\d+(?:\.\d+)?)', discount_text)
            if discount_match:
                discount_rate = discount_match.group(1)
        except NoSuchElementException:
            pass
            
        # 또는 discountrate 클래스에서 할인율 추출
        if not discount_rate:
            try:
                discount_rate_element = product_element.find_element(By.CSS_SELECTOR, '.discountrate span.per')
                discount_rate = discount_rate_element.text.strip()
            except NoSuchElementException:
                pass
        
        # 리뷰 수
        reviews = 0
        try:
            review_element = product_element.find_element(By.CSS_SELECTOR, '.snap_review_count')
            review_text = review_element.text
            review_match = re.search(r'리뷰 : (\d+)', review_text)
            if review_match:
                reviews = int(review_match.group(1))
        except (NoSuchElementException, ValueError):
            pass
        
        # 색상 정보
        colors = []
        try:
            color_chips = product_element.find_elements(By.CSS_SELECTOR, '.colorChip span.chips')
            for color in color_chips:
                color_style = color.get_attribute('style')
                if 'background-color:' in color_style:
                    color_value = re.search(r'background-color:(.*)', color_style).group(1).strip()
                    colors.append(color_value)
        except NoSuchElementException:
            pass
        
        # 제품 정보를 딕셔너리로 저장
        product_info = {
            '상품명': product_name,
            '상품URL': product_url,
            '상품설명': product_desc,
            '이미지URL': image_url,
            '정가': original_price,
            '판매가': discounted_price if discounted_price else original_price,
            '할인율': discount_rate,
            '리뷰수': reviews,
            '색상': ', '.join(colors)
        }
        
        return product_info
    
    except Exception as e:
        print(f"상품 정보 추출 중 오류 발생: {e}")
        return None

def crawl_products(url, category_info, max_pages=None):
    """셀레늄을 사용하여 상품 정보 크롤링"""
    driver = setup_driver()
    all_products = []
    
    # 카테고리 정보 추출
    main_category = category_info['main_category']
    sub_category = category_info['sub_category']
    category_name = f"{main_category} > {sub_category}" if sub_category else main_category
    
    try:
        # 첫 페이지 로드
        driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기
        
        # 총 상품 개수 확인
        try:
            total_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.prdCount strong'))
            )
            total_items = int(total_element.text)
            print(f"[{category_name}] 총 상품 개수: {total_items}")
        except (TimeoutException, ValueError) as e:
            print(f"[{category_name}] 총 상품 개수를 확인할 수 없습니다: {e}")
            total_items = 0
        
        # 페이지네이션 확인
        try:
            pagination = driver.find_elements(By.CSS_SELECTOR, '.ec-base-paginate li a')
            max_page_found = 1
            
            for page_link in pagination:
                try:
                    page_num = int(page_link.text.strip())
                    max_page_found = max(max_page_found, page_num)
                except ValueError:
                    # 숫자가 아닌 페이지 링크 (예: 다음, 이전)
                    pass
            
            print(f"[{category_name}] 발견된 최대 페이지 수: {max_page_found}")
            total_pages = max_page_found
        except Exception as e:
            print(f"[{category_name}] 페이지네이션 확인 중 오류: {e}")
            # 페이지당 상품 수 기준으로 총 페이지 수 추정
            total_pages = (total_items + 47) // 48  # 페이지당 약 48개 상품 기준
        
        # 최대 페이지 수 제한
        if max_pages:
            total_pages = min(total_pages, max_pages)
        
        print(f"[{category_name}] 크롤링할 총 페이지 수: {total_pages}")
        
        # 모든 페이지 크롤링
        current_page = 1
        
        while current_page <= total_pages:
            print(f"[{category_name}] 현재 페이지: {current_page}/{total_pages}")
            
            # 현재 페이지의 상품 목록 가져오기
            try:
                # 상품 컨테이너들을 모두 찾음
                products = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.xans-element-.xans-product.xans-product-listnormal ul.prdList li.item'))
                )
                
                print(f"[{category_name}] 페이지에서 {len(products)}개의 상품 항목 발견")
                
                # 각 상품 요소에서 정보 추출
                products_on_current_page = []
                for idx, product_element in enumerate(products, 1):
                    print(f"[{category_name}] 상품 {idx}/{len(products)} 처리 중...")
                    product_info = extract_product_info(product_element)
                    if product_info:
                        # 카테고리 정보 추가 - 카테고리 뎁스 구분
                        product_info['카테고리_대분류'] = main_category
                        product_info['카테고리_소분류'] = sub_category
                        product_info['카테고리_전체'] = category_name
                        products_on_current_page.append(product_info)
                        print(f"[{category_name}] 상품 {idx} 정보 추출 성공: {product_info['상품명']}")
                
                print(f"[{category_name}] 페이지에서 성공적으로 추출한 상품 수: {len(products_on_current_page)}")
                all_products.extend(products_on_current_page)
                print(f"[{category_name}] 현재까지 수집된 총 상품 수: {len(all_products)}")
                
                # 다음 페이지로 이동
                if current_page < total_pages:
                    next_page_success = False
                    
                    # 방법 1: 페이지 번호 클릭
                    try:
                        # 페이지 링크 다시 찾기 (DOM이 변경되었을 수 있음)
                        pagination = driver.find_elements(By.CSS_SELECTOR, '.ec-base-paginate li a')
                        for page_link in pagination:
                            if page_link.text.strip() == str(current_page + 1):
                                page_link.click()
                                next_page_success = True
                                time.sleep(3)  # 페이지 로딩 대기
                                break
                    except Exception as e:
                        print(f"[{category_name}] 페이지 클릭 방식 실패: {e}")
                    
                    # 방법 2: URL 직접 변경
                    if not next_page_success:
                        try:
                            base_url = url.split('&page=')[0] if '&page=' in url else url
                            next_page_url = f"{base_url}&page={current_page + 1}"
                            print(f"[{category_name}] 다음 페이지 URL: {next_page_url}")
                            driver.get(next_page_url)
                            next_page_success = True
                            time.sleep(3)  # 페이지 로딩 대기
                        except Exception as e:
                            print(f"[{category_name}] URL 변경 방식 실패: {e}")
                
                current_page += 1
                
                # 서버 부담 감소를 위한 대기
                delay = random.uniform(2, 5)
                print(f"[{category_name}] {delay:.2f}초 대기 중...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"[{category_name}] 페이지 {current_page} 처리 중 오류 발생: {e}")
                break
    
    except Exception as e:
        print(f"[{category_name}] 크롤링 중 오류 발생: {e}")
    
    finally:
        driver.quit()
    
    return all_products

def extract_category_urls(html_content):
    """HTML에서 카테고리 URL 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    category_links = []
    
    # 드로어 메뉴에서 메인 카테고리와 서브 카테고리 추출
    drawer_category = soup.select('.drawercategory .drawerbox')
    
    for box in drawer_category:
        main_categories = box.select('li.-d1')
        
        for main_category in main_categories:
            main_link = main_category.select_one('a')
            if not main_link:
                continue
                
            main_category_name = main_link.text.strip()
            main_url = main_link.get('href', '')
            
            # 절대 URL로 변환
            if main_url.startswith('/'):
                main_url = f"https://baddiary.com{main_url}"
            
            # 서브카테고리가 있는지 확인
            has_sub = main_category.has_attr('class') and 'hasChild' in main_category['class']
            
            if has_sub:
                # 서브 카테고리 추출
                sub_categories = main_category.select('ul.-subcover1 li.-d2')
                for sub_category in sub_categories:
                    sub_link = sub_category.select_one('a')
                    if not sub_link:
                        continue
                        
                    sub_category_name = sub_link.text.strip()
                    sub_url = sub_link.get('href', '')
                    
                    # 절대 URL로 변환
                    if sub_url.startswith('/'):
                        sub_url = f"https://baddiary.com{sub_url}"
                        
                    # 카테고리 정보 저장
                    category_links.append({
                        'main_category': main_category_name,
                        'sub_category': sub_category_name,
                        'url': sub_url
                    })
            else:
                # 서브 카테고리가 없는 경우 메인 카테고리만 추가
                category_links.append({
                    'main_category': main_category_name,
                    'sub_category': '',
                    'url': main_url
                })
    
    return category_links

def main():
    try:
        # HTML 문자열에서 카테고리 URL 추출
        html_content = """
        <aside id="drawermenuwrap" class="drawermenuwrap2 d1popupwrap D1W" style="display: block;"><div class="drawermenu -frame -flex">
                    <!-- 관리자 연동 -->
                    <!--<div class="drawercategory"><ul id="drawercategorydata" class="-flex"></ul></div>-->
                    <!-- HTML 코딩 -->
                    <div class="drawercategory -flex"><ul class="drawerbox"><li cateno="36" class="-d1 d1ddm"><a href="/product/list.html?cate_no=36">BEST</a></li>
    <li cateno="72" class="-d1 d1ddm"><a href="/product/list.html?cate_no=72">NEW 5%</a></li>
    <li cateno="69" class="-d1 d1ddm"><a href="/product/list.html?cate_no=69">MADE</a></li>
    <li cateno="33" class="-d1 d1ddm"><a href="/product/list.html?cate_no=33">오늘출발🚚</a></li>
</ul><ul class="drawerbox"><li cateno="24" class="-d1 d1ddm hasChild">
        <a href="/product/list.html?cate_no=24">DRESS<div class="icon"></div></a>
        <ul class="-subcover1 submenu"><li cateno="173" class="-d2"><a href="/product/list.html?cate_no=173">프린트</a></li>
            <li cateno="175" class="-d2"><a href="/product/list.html?cate_no=175">솔리드(무지)</a></li>
            <li cateno="176" class="-d2"><a href="/product/list.html?cate_no=176">H라인</a></li>
            <li cateno="177" class="-d2"><a href="/product/list.html?cate_no=177">플레어&amp;A라인</a></li>
        </ul></li>
</ul><ul class="drawerbox"><li cateno="25" class="-d1 d1ddm hasChild">
        <a href="/product/list.html?cate_no=25">OUTER<div class="icon"></div></a>
        <ul class="-subcover1 submenu"><li cateno="177" class="-d2"><a href="/product/list.html?cate_no=51">가디건</a></li>
            <li cateno="52" class="-d2"><a href="/product/list.html?cate_no=52">자켓/코트</a></li>
            <li cateno="418" class="-d2"><a href="/product/list.html?cate_no=418">패딩</a></li>
        </ul></li>
</ul><ul class="drawerbox"><li cateno="42" class="-d1 d1ddm hasChild">
        <a href="/product/list.html?cate_no=42">TOP<div class="icon"></div></a>
        <ul class="-subcover1 submenu"><li cateno="46" class="-d2"><a href="/product/list.html?cate_no=46">블라우스</a></li>
            <li cateno="45" class="-d2"><a href="/product/list.html?cate_no=45">티/니트</a></li>
        </ul></li>
</ul><ul class="drawerbox"><li cateno="27" class="-d1 d1ddm hasChild">
        <a href="/product/list.html?cate_no=27">BOTTOM<div class="icon"></div></a>
        <ul class="-subcover1 submenu"><li cateno="48" class="-d2"><a href="/product/list.html?cate_no=48">팬츠</a></li>
            <li cateno="49" class="-d2"><a href="/product/list.html?cate_no=49">스커트</a></li>
        </ul></li>
</ul><ul class="drawerbox"><li cateno="28" class="-d1 d1ddm"><a href="/product/list.html?cate_no=28">ACC</a></li>
    <li cateno="227" class="-d1 d1ddm"><a href="/product/list.html?cate_no=227">출근룩</a></li>
    <li cateno="35" class="-d1 d1ddm"><a href="/product/list.html?cate_no=35">웨딩&amp;세레머니</a></li>
    <li cateno="152" class="-d1 d1ddm"><a href="/product/list.html?cate_no=152">베이직</a></li>
    <li cateno="320" class="-d1 d1ddm"><a href="/product/list.html?cate_no=320">셋업</a></li>
    <li cateno="445" class="-d1 d1ddm"><a href="/product/list.html?cate_no=445">여행룩✈️</a></li>
	<li cateno="31" class="-d1 d1ddm"><a href="/product/list.html?cate_no=43">77SIZE</a></li>
	<li cateno="31" class="-d1 d1ddm"><a href="/product/list.html?cate_no=31">아울렛</a></li>
</ul></div>
                </div>
            </aside>
        """
        
        # 추출된 카테고리 URL 정보를 CSV로 저장 (선택적)
        category_links = extract_category_urls(html_content)
        df_categories = pd.DataFrame(category_links)
        df_categories.to_csv('baddiary_categories.csv', index=False, encoding='utf-8-sig')
        print(f"카테고리 정보 CSV 파일 저장 완료: baddiary_categories.csv")
        
        print(f"총 {len(category_links)}개의 카테고리 URL을 추출했습니다.")
        
        # 모든 카테고리의 상품 정보
        all_products_all_categories = []
        
        # 각 카테고리별로 크롤링
        for i, category in enumerate(category_links, 1):
            main_category = category['main_category']
            sub_category = category['sub_category']
            category_url = category['url']
            category_name = f"{main_category} > {sub_category}" if sub_category else main_category
            
            print(f"\n===== ({i}/{len(category_links)}) {category_name} 카테고리 크롤링 시작 =====")
            print(f"URL: {category_url}")
            
            # 최대 페이지 수 설정 (None으로 설정하면 모든 페이지)
            max_pages = 2  # 테스트를 위해 각 카테고리당 최대 2페이지만 크롤링
            
            # 셀레늄으로 크롤링 실행
            category_products = crawl_products(category_url, category, max_pages)
            
            # 전체 상품 목록에 추가
            all_products_all_categories.extend(category_products)
            
            # 서버 부담 감소를 위한 대기
            if i < len(category_links):
                delay = random.uniform(5, 10)
                print(f"다음 카테고리로 이동하기 전 {delay:.2f}초 대기 중...")
                time.sleep(delay)
        
        # 모든 카테고리의 상품을 하나의 데이터프레임으로 통합
        if all_products_all_categories:
            # 중복 제거 (모든 카테고리에서 발생할 수 있는 중복)
            unique_all_products = []
            product_urls = set()  # URL 기준으로 중복 체크 (같은 상품명이지만 다른 카테고리에 있을 수 있음)
            
            for product in all_products_all_categories:
                if product['상품URL'] not in product_urls and product['상품URL'].strip() != '':
                    product_urls.add(product['상품URL'])
                    unique_all_products.append(product)
            
            print(f"\n모든 카테고리 원본 상품 수: {len(all_products_all_categories)}, 중복 제거 후 상품 수: {len(unique_all_products)}")
            
            # 통합 데이터프레임 생성
            df_all = pd.DataFrame(unique_all_products)
            
            # CSV 파일로 저장
            all_csv_filename = 'baddiary_products_data.csv'
            df_all.to_csv(all_csv_filename, index=False, encoding='utf-8-sig')
            print(f"모든 카테고리 통합 CSV 파일 저장 완료: {all_csv_filename}")
            
            # Excel 파일로 저장
            all_excel_filename = 'baddiary_products_data.xlsx'
            df_all.to_excel(all_excel_filename, index=False)
            print(f"모든 카테고리 통합 Excel 파일 저장 완료: {all_excel_filename}")
        
        print(f"\n크롤링 완료! 총 {len(unique_all_products)}개의 상품 정보를 저장했습니다.")
    
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()