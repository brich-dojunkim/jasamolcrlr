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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
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
            name_elements = product_element.find_elements(By.CSS_SELECTOR, '.name a span')
            if name_elements and len(name_elements) > 0:
                product_name = name_elements[-1].text.strip()
            else:
                # 대체 방법으로 시도
                name_element = product_element.find_element(By.CSS_SELECTOR, '.name a')
                if name_element:
                    product_name = name_element.text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 상품 URL
        product_url = ""
        try:
            url_element = product_element.find_element(By.CSS_SELECTOR, '.name a')
            product_url = url_element.get_attribute('href')
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 이미지 URL
        image_url = ''
        try:
            # 첫 번째 이미지 시도
            img_elements = product_element.find_elements(By.CSS_SELECTOR, '.prdImg a img')
            if img_elements and len(img_elements) > 0:
                for img in img_elements:
                    temp_url = img.get_attribute('src')
                    if temp_url and 'medium' in temp_url:
                        image_url = temp_url
                        break
                    elif temp_url:
                        image_url = temp_url
                        # 썸네일이면 중간 크기 이미지로 대체
                        if "/tiny/" in image_url:
                            image_url = image_url.replace("/tiny/", "/medium/")
                        break
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 가격 정보 (판매가)
        price = None
        try:
            price_elements = product_element.find_elements(By.CSS_SELECTOR, '.spec li')
            for price_el in price_elements:
                price_text = price_el.text.strip()
                if "원" in price_text:
                    price = re.sub(r'[^\d]', '', price_text)
                    break
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 색상 정보
        colors = []
        try:
            color_chips = product_element.find_elements(By.CSS_SELECTOR, '.colorchip span')
            for color in color_chips:
                color_style = color.get_attribute('style')
                if color_style and 'background-color:' in color_style:
                    try:
                        color_value = re.search(r'background-color:(.*?)(;|$)', color_style).group(1).strip()
                        colors.append(color_value)
                    except (AttributeError, IndexError):
                        pass
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 품절 여부
        is_sold_out = False
        try:
            sold_out_elements = product_element.find_elements(By.CSS_SELECTOR, '.icon .promotion img')
            for sold_el in sold_out_elements:
                alt_text = sold_el.get_attribute('alt')
                if alt_text and '품절' in alt_text:
                    is_sold_out = True
                    break
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 좋아요 수
        like_count = 0
        try:
            like_elements = product_element.find_elements(By.CSS_SELECTOR, '.likePrdCount')
            if like_elements and len(like_elements) > 0:
                try:
                    like_count = int(like_elements[0].text.strip())
                except (ValueError, TypeError):
                    pass
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        
        # 제품 정보를 딕셔너리로 저장
        product_info = {
            '상품명': product_name,
            '상품URL': product_url,
            '이미지URL': image_url,
            '가격': price,
            '색상': ', '.join(colors),
            '품절여부': is_sold_out,
            '좋아요수': like_count
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
        time.sleep(5)  # 페이지 로딩 대기 시간 증가
        
        # 총 상품 개수 확인 (prdCount 클래스를 사용)
        try:
            total_text = driver.find_element(By.CSS_SELECTOR, '.prdCount').text.strip()
            total_items_match = re.search(r'(\d+)\s*PRODUCT', total_text)
            if total_items_match:
                total_items = int(total_items_match.group(1))
                print(f"[{category_name}] 총 상품 개수: {total_items}")
            else:
                total_items = 0
                print(f"[{category_name}] 총 상품 개수를 확인할 수 없습니다.")
        except (NoSuchElementException, ValueError) as e:
            print(f"[{category_name}] 총 상품 개수를 확인할 수 없습니다: {e}")
            total_items = 0
        
        # 페이지네이션 확인
        try:
            pagination = driver.find_elements(By.CSS_SELECTOR, '.ec-base-paginate ol li a')
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
            total_pages = (total_items + 39) // 40  # 페이지당 약 40개 상품 기준
        
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
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.prdList'))
                )
                time.sleep(2)  # 추가 대기 시간
                
                product_elements = driver.find_elements(By.CSS_SELECTOR, '.prdList li.item')
                
                if not product_elements:
                    print(f"[{category_name}] 페이지에서 상품을 찾을 수 없습니다. 다른 선택자로 시도합니다.")
                    product_elements = driver.find_elements(By.CSS_SELECTOR, '.xans-product-listnormal ul.prdList li')
                
                print(f"[{category_name}] 페이지에서 {len(product_elements)}개의 상품 항목 발견")
                
                # 각 상품 요소에서 정보 추출
                products_on_current_page = []
                for idx, product_element in enumerate(product_elements, 1):
                    print(f"[{category_name}] 상품 {idx}/{len(product_elements)} 처리 중...")
                    product_info = extract_product_info(product_element)
                    if product_info:
                        # 카테고리 정보 추가
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
                    
                    # 방법 1: URL 직접 변경 (가장 안정적인 방법)
                    try:
                        # URL에 페이지 파라미터 추가
                        base_url = url.split('&page=')[0] if '&page=' in url else url
                        if '?' in base_url:
                            next_page_url = f"{base_url}&page={current_page + 1}"
                        else:
                            next_page_url = f"{base_url}?page={current_page + 1}"
                        print(f"[{category_name}] 다음 페이지 URL: {next_page_url}")
                        driver.get(next_page_url)
                        next_page_success = True
                        time.sleep(5)  # 페이지 로딩 대기
                    except Exception as e:
                        print(f"[{category_name}] URL 변경 방식 실패: {e}")
                    
                    # 방법 2: NEXT 버튼 클릭 (URL 변경이 실패한 경우만)
                    if not next_page_success:
                        try:
                            next_buttons = driver.find_elements(By.CSS_SELECTOR, '.ec-base-paginate a')
                            for btn in next_buttons:
                                if btn.text.strip() == "NEXT":
                                    btn.click()
                                    next_page_success = True
                                    time.sleep(5)  # 페이지 로딩 대기
                                    break
                        except Exception as e:
                            print(f"[{category_name}] NEXT 버튼 클릭 방식 실패: {e}")
                    
                    # 방법 3: 페이지 번호 클릭 (URL 변경과 NEXT 버튼이 모두 실패한 경우)
                    if not next_page_success:
                        try:
                            page_links = driver.find_elements(By.CSS_SELECTOR, '.ec-base-paginate ol li a')
                            for link in page_links:
                                if link.text.strip() == str(current_page + 1):
                                    link.click()
                                    next_page_success = True
                                    time.sleep(5)  # 페이지 로딩 대기
                                    break
                        except Exception as e:
                            print(f"[{category_name}] 페이지 번호 클릭 방식 실패: {e}")
                
                current_page += 1
                
                # 서버 부담 감소를 위한 대기
                delay = random.uniform(3, 7)
                print(f"[{category_name}] {delay:.2f}초 대기 중...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"[{category_name}] 페이지 {current_page} 처리 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                break
    
    except Exception as e:
        print(f"[{category_name}] 크롤링 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()
    
    return all_products

def extract_category_urls(html_content):
    """HTML에서 카테고리 URL 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    category_links = []
    
    # 메인 카테고리 (ct01 클래스) 추출
    main_categories = soup.select('#all_category .ct01-wrap li.ct01')
    
    for main_cat in main_categories:
        main_cat_name = main_cat.find('a').text.strip()
        main_cat_url = main_cat.find('a').get('href')
        if not main_cat_url.startswith('http'):
            main_cat_url = f"https://closhoew.com{main_cat_url}"
        
        # 서브 카테고리 (ct02 클래스) 존재 여부 확인
        sub_categories = main_cat.select('dl.ct02-wrap dd.ct02')
        
        if sub_categories:
            # 서브 카테고리가 있는 경우
            for sub_cat in sub_categories:
                sub_cat_name = sub_cat.find('a').text.strip()
                sub_cat_url = sub_cat.find('a').get('href')
                if not sub_cat_url.startswith('http'):
                    sub_cat_url = f"https://closhoew.com{sub_cat_url}"
                
                # 3차 카테고리 (ct03 클래스) 존재 여부 확인
                third_categories = sub_cat.select('dl.ct03-wrap dd.ct03')
                
                if third_categories:
                    # 3차 카테고리가 있는 경우
                    for third_cat in third_categories:
                        third_cat_name = third_cat.find('a').text.strip()
                        third_cat_url = third_cat.find('a').get('href')
                        if not third_cat_url.startswith('http'):
                            third_cat_url = f"https://closhoew.com{third_cat_url}"
                        
                        # 카테고리 정보 저장 (메인 > 서브 > 3차)
                        category_links.append({
                            'main_category': main_cat_name,
                            'sub_category': f"{sub_cat_name} > {third_cat_name}",
                            'url': third_cat_url
                        })
                else:
                    # 3차 카테고리가 없는 경우 (메인 > 서브)
                    category_links.append({
                        'main_category': main_cat_name,
                        'sub_category': sub_cat_name,
                        'url': sub_cat_url
                    })
        else:
            # 서브 카테고리가 없는 경우 (메인만)
            category_links.append({
                'main_category': main_cat_name,
                'sub_category': '',
                'url': main_cat_url
            })
    
    return category_links

def main():
    try:
        # HTML 문자열에서 카테고리 URL 추출
        html_content = """
        <div id="all_category" class="xans-element- xans-layout xans-layout-category" style="display: block;"><div class="position">
                <ul class="ct01-wrap">
<li data-param="?cate_no=23" class="ct01 xans-record-"><a href="/product/list.html?cate_no=25">OUTER  </a><dl class="ct02-wrap"><dd data-param="?cate_no=48" class="ct02"><a href="/product/list.html?cate_no=48">자켓</a></dd><dd data-param="?cate_no=50" class="ct02"><a href="/product/list.html?cate_no=50">가디건</a></dd><dd data-param="?cate_no=54" class="ct02"><a href="/product/list.html?cate_no=54">트위드</a></dd><dd data-param="?cate_no=53" class="ct02"><a href="/product/list.html?cate_no=53">점퍼/집업</a></dd><dd data-param="?cate_no=55" class="ct02"><a href="/product/list.html?cate_no=55">야상</a></dd><dd data-param="?cate_no=103" class="ct02"><a href="/product/list.html?cate_no=103">베스트</a></dd><dd data-param="?cate_no=51" class="ct02"><a href="/product/list.html?cate_no=51">코트</a></dd><dd data-param="?cate_no=56" class="ct02"><a href="/product/list.html?cate_no=56">패딩</a></dd></dl></li>
<li data-param="?cate_no=26" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=26">TOP</a><dl class="ct02-wrap"><dd data-param="?cate_no=58" class="ct02 be"><a href="/product/list.html?cate_no=58">티셔츠</a><dl class="ct03-wrap"><dd data-param="?cate_no=59" class="ct03"><a href="/product/list.html?cate_no=59">긴팔</a></dd><dd data-param="?cate_no=76" class="ct03"><a href="/product/list.html?cate_no=76">반팔</a></dd><dd data-param="?cate_no=77" class="ct03"><a href="/product/list.html?cate_no=77">민소매</a></dd></dl></dd><dd data-param="?cate_no=61" class="ct02 be"><a href="/product/list.html?cate_no=61">블라우스/셔츠</a><dl class="ct03-wrap"><dd data-param="?cate_no=79" class="ct03"><a href="/product/list.html?cate_no=79">블라우스</a></dd><dd data-param="?cate_no=80" class="ct03"><a href="/product/list.html?cate_no=80">셔츠</a></dd></dl></dd><dd data-param="?cate_no=60" class="ct02"><a href="/product/list.html?cate_no=60">니트</a></dd><dd data-param="?cate_no=63" class="ct02 be"><a href="/product/list.html?cate_no=63">맨투맨/후디</a><dl class="ct03-wrap"><dd data-param="?cate_no=81" class="ct03"><a href="/product/list.html?cate_no=81">맨투맨</a></dd><dd data-param="?cate_no=82" class="ct03"><a href="/product/list.html?cate_no=82">후디</a></dd></dl></dd><dd data-param="?cate_no=95" class="ct02"><a href="/product/list.html?cate_no=95">뷔스티에</a></dd><dd data-param="?cate_no=94" class="ct02"><a href="/product/list.html?cate_no=94">베스트</a></dd></dl></li>
<li data-param="?cate_no=27" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=27">BOTTOM </a><dl class="ct02-wrap"><dd data-param="?cate_no=64" class="ct02"><a href="/product/list.html?cate_no=64">데님</a></dd><dd data-param="?cate_no=93" class="ct02"><a href="/product/list.html?cate_no=93">슬랙스</a></dd><dd data-param="?cate_no=78" class="ct02 be"><a href="/product/list.html?cate_no=78">스커트</a><dl class="ct03-wrap"><dd data-param="?cate_no=83" class="ct03"><a href="/product/list.html?cate_no=83">미니</a></dd><dd data-param="?cate_no=84" class="ct03"><a href="/product/list.html?cate_no=84">미디/롱</a></dd></dl></dd><dd data-param="?cate_no=66" class="ct02"><a href="/product/list.html?cate_no=66">숏팬츠</a></dd><dd data-param="?cate_no=65" class="ct02"><a href="/product/list.html?cate_no=65">롱팬츠</a></dd><dd data-param="?cate_no=101" class="ct02"><a href="/product/list.html?cate_no=101">조거팬츠</a></dd><dd data-param="?cate_no=100" class="ct02"><a href="/product/list.html?cate_no=100">레깅스</a></dd></dl></li>
<li data-param="?cate_no=28" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=28">DRESS   </a><dl class="ct02-wrap"><dd data-param="?cate_no=68" class="ct02"><a href="/product/list.html?cate_no=68">미니</a></dd><dd data-param="?cate_no=70" class="ct02"><a href="/product/list.html?cate_no=70">미디/롱</a></dd><dd data-param="?cate_no=71" class="ct02"><a href="/product/list.html?cate_no=71">점프수트</a></dd></dl></li>
<li data-param="?cate_no=42" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=42">SET ITEM</a><dl class="ct02-wrap"><dd data-param="?cate_no=75" class="ct02"><a href="/product/list.html?cate_no=75">상의 세트</a></dd><dd data-param="?cate_no=74" class="ct02"><a href="/product/list.html?cate_no=74">팬츠 세트</a></dd><dd data-param="?cate_no=85" class="ct02"><a href="/product/list.html?cate_no=85">스커트 세트</a></dd></dl></li>
<li data-param="?cate_no=43" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=43">SHOES</a><dl class="ct02-wrap"><dd data-param="?cate_no=86" class="ct02"><a href="/product/list.html?cate_no=86">슬리퍼/샌들</a></dd><dd data-param="?cate_no=88" class="ct02"><a href="/product/list.html?cate_no=88">부츠</a></dd><dd data-param="?cate_no=87" class="ct02"><a href="/product/list.html?cate_no=87">힐</a></dd></dl></li>
<li data-param="?cate_no=44" class="ct01 xans-record- be"><a href="/product/list.html?cate_no=44">ACC</a><dl class="ct02-wrap"><dd data-param="?cate_no=106" class="ct02"><a href="/product/list.html?cate_no=106">이너웨어</a></dd><dd data-param="?cate_no=90" class="ct02"><a href="/product/list.html?cate_no=90">가방</a></dd><dd data-param="?cate_no=89" class="ct02"><a href="/product/list.html?cate_no=89">모자</a></dd><dd data-param="?cate_no=92" class="ct02"><a href="/product/list.html?cate_no=92">선글라스</a></dd><dd data-param="?cate_no=105" class="ct02"><a href="/product/list.html?cate_no=105">벨트</a></dd><dd data-param="?cate_no=91" class="ct02"><a href="/product/list.html?cate_no=91">악세사리</a></dd><dd data-param="?cate_no=104" class="ct02"><a href="/product/list.html?cate_no=104">홈웨어</a></dd><dd data-param="?cate_no=96" class="ct02"><a href="/product/list.html?cate_no=96">장갑&amp;양말</a></dd><dd data-param="?cate_no=99" class="ct02"><a href="/product/list.html?cate_no=99">머플러</a></dd></dl></li>
                </ul>
            </div>
        </div>
        """
        
        # 추출된 카테고리 URL 정보를 CSV로 저장
        category_links = extract_category_urls(html_content)
        df_categories = pd.DataFrame(category_links)
        df_categories.to_csv('closhoew_categories.csv', index=False, encoding='utf-8-sig')
        print(f"카테고리 정보 CSV 파일 저장 완료: closhoew_categories.csv")
        
        print(f"총 {len(category_links)}개의 카테고리 URL을 추출했습니다.")
        
        # 테스트를 위해 일부 카테고리만 선택할 수 있습니다.
        # 전체 카테고리를 크롤링하려면 아래 줄을 주석 처리하세요.
        # category_links = category_links[:5]  # 처음 5개 카테고리만 크롤링
        
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
            
            # 진행 상황 CSV 파일로 중간 저장 (크롤링 중 오류 발생해도 일부 데이터 보존)
            if len(all_products_all_categories) > 0:
                tmp_df = pd.DataFrame(all_products_all_categories)
                tmp_csv = 'closhoew_products_partial.csv'
                tmp_df.to_csv(tmp_csv, index=False, encoding='utf-8-sig')
                print(f"현재까지 수집된 {len(all_products_all_categories)}개 상품을 {tmp_csv}에 저장했습니다.")
            
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
                if product['상품URL'] and product['상품URL'] not in product_urls and product['상품URL'].strip() != '':
                    product_urls.add(product['상품URL'])
                    unique_all_products.append(product)
            
            print(f"\n모든 카테고리 원본 상품 수: {len(all_products_all_categories)}, 중복 제거 후 상품 수: {len(unique_all_products)}")
            
            # 통합 데이터프레임 생성
            df_all = pd.DataFrame(unique_all_products)
            
            # CSV 파일로 저장
            all_csv_filename = 'closhoew_products_data.csv'
            df_all.to_csv(all_csv_filename, index=False, encoding='utf-8-sig')
            print(f"모든 카테고리 통합 CSV 파일 저장 완료: {all_csv_filename}")
            
            # Excel 파일로 저장
            all_excel_filename = 'closhoew_products_data.xlsx'
            df_all.to_excel(all_excel_filename, index=False)
            print(f"모든 카테고리 통합 Excel 파일 저장 완료: {all_excel_filename}")
        
        print(f"\n크롤링 완료! 총 {len(unique_all_products)}개의 상품 정보를 저장했습니다.")
    
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()