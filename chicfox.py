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
            product_name = product_element.find_element(By.CSS_SELECTOR, '.item_name a').text.strip()
        except NoSuchElementException:
            pass
        
        # 상품 URL
        product_url = ""
        try:
            product_url = product_element.find_element(By.CSS_SELECTOR, '.item_name a').get_attribute('href')
        except NoSuchElementException:
            pass
        
        # 상품 설명
        product_desc = ''
        try:
            product_desc = product_element.find_element(By.CSS_SELECTOR, '.item_option').text.strip()
        except NoSuchElementException:
            pass
        
        # 이미지 URL
        image_url = ''
        try:
            img_element = product_element.find_element(By.CSS_SELECTOR, '.item_img img')
            image_url = img_element.get_attribute('src')
            # 이미지가 지연 로딩되는 경우 data-frz-src 속성 확인
            if not image_url or image_url == "":
                image_url = img_element.get_attribute('data-frz-src')
        except NoSuchElementException:
            pass
        
        # 가격 정보
        price_info = product_element.find_element(By.CSS_SELECTOR, '.item_price')
        
        # 정가 (할인이 있는 경우)
        original_price = None
        try:
            strike_element = price_info.find_element(By.CSS_SELECTOR, '.strike')
            original_price_text = strike_element.text.strip()
            original_price = re.sub(r'[^\d]', '', original_price_text)
        except NoSuchElementException:
            pass
        
        # 판매가
        current_price = None
        try:
            price_element = price_info.find_element(By.CSS_SELECTOR, '.price')
            current_price_text = price_element.text.strip()
            current_price = re.sub(r'[^\d]', '', current_price_text)
        except NoSuchElementException:
            pass
        
        # 할인율
        discount_rate = None
        try:
            sale_element = price_info.find_element(By.CSS_SELECTOR, '.salePercent')
            discount_text = sale_element.text.strip()
            discount_match = re.search(r'(\d+(?:\.\d+)?)', discount_text)
            if discount_match:
                discount_rate = discount_match.group(1)
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
            color_chips = product_element.find_elements(By.CSS_SELECTOR, '.colorchips .chip')
            for color in color_chips:
                color_style = color.get_attribute('style')
                color_name = color.get_attribute('class').replace('chip', '').strip()
                if not color_name and 'background-color:' in color_style:
                    color_value = re.search(r'background-color:(.*)', color_style).group(1).strip()
                    colors.append(color_value)
                elif color_name:
                    colors.append(color_name)
        except NoSuchElementException:
            pass
        
        # 판매수량
        sales_count = 0
        try:
            stock_element = product_element.find_element(By.CSS_SELECTOR, '.item_stock')
            stock_text = stock_element.text.strip()
            sales_match = re.search(r'판매수량 : (\d+)', stock_text)
            if sales_match:
                sales_count = int(sales_match.group(1))
        except (NoSuchElementException, ValueError):
            pass
        
        # 제품 정보를 딕셔너리로 저장
        product_info = {
            '상품명': product_name,
            '상품URL': product_url,
            '상품설명': product_desc,
            '이미지URL': image_url,
            '정가': original_price,
            '판매가': current_price,
            '할인율': discount_rate,
            '리뷰수': reviews,
            '색상': ', '.join(colors),
            '판매수량': sales_count
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
    category_name = f"{main_category} > {sub_category}"
    
    try:
        # 첫 페이지 로드
        driver.get(url)
        time.sleep(3)  # 페이지 로딩 대기
        
        # 총 상품 개수 확인
        try:
            total_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.item-total strong'))
            )
            total_items = int(total_element.text)
            print(f"[{category_name}] 총 상품 개수: {total_items}")
        except (TimeoutException, ValueError) as e:
            print(f"[{category_name}] 총 상품 개수를 확인할 수 없습니다: {e}")
            total_items = 0
        
        # 페이지네이션 확인
        try:
            pagination = driver.find_elements(By.CSS_SELECTOR, '.paging a')
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
            total_pages = (total_items + 19) // 20  # 페이지당 약 20개 상품 기준
        
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
                item_conts = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.item-cont'))
                )
                
                # 각 컨테이너 내의 모든 상품 요소 찾기
                all_products_on_page = []
                for cont in item_conts:
                    product_elements = cont.find_elements(By.CSS_SELECTOR, '.item-list')
                    all_products_on_page.extend(product_elements)
                
                print(f"[{category_name}] 페이지에서 {len(all_products_on_page)}개의 상품 항목 발견")
                
                # 각 상품 요소에서 정보 추출
                products_on_current_page = []
                for idx, product_element in enumerate(all_products_on_page, 1):
                    print(f"[{category_name}] 상품 {idx}/{len(all_products_on_page)} 처리 중...")
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
                        pagination = driver.find_elements(By.CSS_SELECTOR, '.paging a')
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
    
    # 메인 카테고리 찾기
    menu_sections = soup.select('dl')
    
    for section in menu_sections:
        # 카테고리 제목 (dt 태그)
        dt = section.find('dt')
        if not dt:
            continue
            
        dt_link = dt.find('a')
        if not dt_link:
            continue
            
        main_category = dt_link.text.strip()
        main_url = dt_link.get('href', '')
        
        # 절대 URL로 변환
        if main_url.startswith('/'):
            main_url = f"https://www.chicfox.co.kr{main_url}"
            
        # 서브 카테고리 (dd 태그)
        dds = section.find_all('dd')
        for dd in dds:
            dd_link = dd.find('a')
            if not dd_link:
                continue
                
            sub_category = dd_link.text.strip()
            sub_url = dd_link.get('href', '')
            
            # 절대 URL로 변환
            if sub_url.startswith('/'):
                sub_url = f"https://www.chicfox.co.kr{sub_url}"
                
            # 카테고리 정보 저장 - 깊이별로 분리
            category_links.append({
                'main_category': main_category,
                'sub_category': sub_category,
                'url': sub_url
            })
    
    return category_links

def main():
    try:
        # HTML 문자열에서 카테고리 URL 추출
        html_content = """
        <div class="allMenuBx">
                    <div class="allMenuInner">
                        <div class="allMenuList lpNone">
                            <ul>
                                <li><a href="/shop/shopbrand.html?xcode=155&amp;type=P">BEST</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=157&amp;type=Y">NEW 5%</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=088&amp;type=Y" class="tmenuB">여우진</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=160&amp;type=Y" class="">스토리가든</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=086&amp;mcode=029&amp;type=Y" class="">봄신상 만나기</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=039&amp;type=P" class="">만원의 ♥행복</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=023&amp;type=O" class="">1+1 할인</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=086&amp;mcode=006&amp;type=Y" class="">리오더</a></li>
                                <li><a href="/shop/shopbrand.html?xcode=067&amp;type=Y" class="">HOT! 세일</a></li>
                            </ul>
                        </div>
                        <div class="allMenuList xline">
                            <dl class="topMenu">
                                <dt><a href="shop/shopbrand.html?xcode=001&amp;type=X">TOP</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=007">무지티</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=005">프린트티</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=004">후드&amp;맨투맨</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=002">나시</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=001">니트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=008">베스트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=006">셔츠</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=001&amp;type=M&amp;mcode=003">블라우스</a></dd>
                            </dl>
                            <dl class="bottomMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=113&amp;type=Y">KNIT/CARDIGAN</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=113&amp;type=N&amp;mcode=001">니트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=113&amp;type=N&amp;mcode=002">가디건</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=113&amp;type=N&amp;mcode=003">베스트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=113&amp;type=M&amp;mcode=004">집업</a></dd>
                            </dl>
                        </div>
                        <div class="allMenuList">
                            <dl class="topMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=010&amp;type=X">OUTER</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=010&amp;type=M&amp;mcode=001">자켓</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=010&amp;type=M&amp;mcode=002">점퍼/집업</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=010&amp;type=M&amp;mcode=003">가디건</a></dd>                                
                                <dd><a href="/shop/shopbrand.html?xcode=010&amp;type=M&amp;mcode=004">코트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=138&amp;type=P">바람막이</a></dd>
                            </dl>
                            <dl class="bottomMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=140&amp;type=Y">SHIRT/BLOUSE</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=140&amp;type=N&amp;mcode=001">셔츠</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=140&amp;type=N&amp;mcode=002">블라우스</a></dd>
                            </dl>
                        </div>
                        <div class="allMenuList">
                            <dl class="topMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=049&amp;type=X">PANTS</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=013">부츠컷</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=009">배기진</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=007">와이드팬츠</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=006">슬랙스</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=011">일자팬츠</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=005">반바지</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=049&amp;type=M&amp;mcode=002">트레이닝/레깅스</a></dd>
                            </dl>
                            <dl class="bottomMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=002&amp;type=X">DRESS&amp;SKIRT</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=002&amp;type=M&amp;mcode=001">원피스</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=002&amp;type=M&amp;mcode=002">스커트</a></dd>
                            </dl>
                        </div>
                        <div class="allMenuList">
                            <dl class="topMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=005&amp;type=X">ACC</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=002">모자</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=005">머플러&amp;스카프</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=006">쥬얼리</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=003">벨트</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=004">이너웨어</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=005&amp;type=M&amp;mcode=008">기타</a></dd>
                            </dl>
                            <dl class="bottomMenu">
                                <dt><a href="/shop/shopbrand.html?xcode=004&amp;type=X">SHOES/BAG</a></dt>
                                <dd><a href="/shop/shopbrand.html?xcode=004&amp;type=M&amp;mcode=001">SHOES</a></dd>
                                <dd><a href="/shop/shopbrand.html?xcode=004&amp;type=M&amp;mcode=002">BAG</a></dd>
                            </dl>
                        </div>
                    </div><!-- //inner -->
                </div>
        """
        
        # 추출된 카테고리 URL 정보를 CSV로 저장 (선택적)
        category_links = extract_category_urls(html_content)
        df_categories = pd.DataFrame(category_links)
        df_categories.to_csv('chicfox_categories.csv', index=False, encoding='utf-8-sig')
        print(f"카테고리 정보 CSV 파일 저장 완료: chicfox_categories.csv")
        
        print(f"총 {len(category_links)}개의 카테고리 URL을 추출했습니다.")
        
        # 모든 카테고리의 상품 정보
        all_products_all_categories = []
        
        # 각 카테고리별로 크롤링
        for i, category in enumerate(category_links, 1):
            main_category = category['main_category']
            sub_category = category['sub_category']
            category_url = category['url']
            category_name = f"{main_category} > {sub_category}"
            
            print(f"\n===== ({i}/{len(category_links)}) {category_name} 카테고리 크롤링 시작 =====")
            print(f"URL: {category_url}")
            
            # 최대 페이지 수 설정 (None으로 설정하면 모든 페이지)
            max_pages = None  # 테스트를 위해 각 카테고리당 최대 2페이지만 크롤링
            
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
            all_csv_filename = 'chicfox_products_data.csv'
            df_all.to_csv(all_csv_filename, index=False, encoding='utf-8-sig')
            print(f"모든 카테고리 통합 CSV 파일 저장 완료: {all_csv_filename}")
            
            # Excel 파일로 저장
            all_excel_filename = 'chicfox_products_data.xlsx'
            df_all.to_excel(all_excel_filename, index=False)
            print(f"모든 카테고리 통합 Excel 파일 저장 완료: {all_excel_filename}")
        
        print(f"\n크롤링 완료! 총 {len(unique_all_products)}개의 상품 정보를 저장했습니다.")
    
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()