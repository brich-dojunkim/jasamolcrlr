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
        product_name = product_element.find_element(By.CSS_SELECTOR, '.prd-name a').text.strip()
        
        # 상품 URL
        product_url = product_element.find_element(By.CSS_SELECTOR, '.prd-name a').get_attribute('href')
        
        # 상품 설명
        product_desc = ''
        try:
            product_desc = product_element.find_element(By.CSS_SELECTOR, '.prd-subname').text.strip()
        except NoSuchElementException:
            pass
        
        # 이미지 URL
        image_url = ''
        try:
            image_url = product_element.find_element(By.CSS_SELECTOR, '.thumb img').get_attribute('src')
        except NoSuchElementException:
            pass
        
        # 가격 정보
        price_info = product_element.find_element(By.CSS_SELECTOR, '.prd-price')
        
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
            review_element = price_info.find_element(By.CSS_SELECTOR, '.crema-product-reviews-count')
            review_text = review_element.text
            review_match = re.search(r'리뷰:\s*(\d+)', review_text)
            if review_match:
                reviews = int(review_match.group(1))
        except NoSuchElementException:
            pass
        
        # 색상 정보
        colors = []
        try:
            color_chips = product_element.find_elements(By.CSS_SELECTOR, '.clChip span')
            for color in color_chips:
                style = color.get_attribute('style')
                if style and 'background' in style:
                    color_value = style.replace('background:', '').strip()
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
            '판매가': current_price,
            '할인율': discount_rate,
            '리뷰수': reviews,
            '색상': ', '.join(colors)
        }
        
        return product_info
    
    except Exception as e:
        print(f"상품 정보 추출 중 오류 발생: {e}")
        return None

def crawl_products(url, category_name, max_pages=None):
    """셀레늄을 사용하여 상품 정보 크롤링"""
    driver = setup_driver()
    all_products = []
    
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
                    product_elements = cont.find_elements(By.CSS_SELECTOR, 'dl.item-list')
                    all_products_on_page.extend(product_elements)
                
                print(f"[{category_name}] 페이지에서 {len(all_products_on_page)}개의 상품 항목 발견")
                
                # 각 상품 요소에서 정보 추출
                products_on_current_page = []
                for idx, product_element in enumerate(all_products_on_page, 1):
                    print(f"[{category_name}] 상품 {idx}/{len(all_products_on_page)} 처리 중...")
                    product_info = extract_product_info(product_element)
                    if product_info:
                        # 카테고리 정보 추가
                        product_info['카테고리'] = category_name
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
    
    # 모든 a 태그 찾기
    links = soup.select('div.list a')
    
    for link in links:
        href = link.get('href', '')
        if href and '/shop/shopbrand.html' in href:
            # 상대 URL을 절대 URL로 변환
            if href.startswith('/'):
                href = f"https://www.joamom.co.kr{href}"
            
            # 카테고리명 추출
            category_name = link.text.strip()
            
            # 중복 제거하며 카테고리 정보 저장
            category_links.append({
                'name': category_name,
                'url': href
            })
    
    return category_links

def main():
    try:
        # HTML 파일에서 카테고리 URL 추출 (이미 제공된 HTML 문자열)
        html_content = """
        <div class="list">
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=094">MADE</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=&amp;mcode=008">MADFIT</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062">TOP</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=063">BLOUSE</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065">PANTS</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=066">OPS/SKIRT</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067">OUTER</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=094&amp;type=&amp;mcode=007">ETC</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=062">TOP</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062&amp;type=&amp;mcode=001">라운드넥</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062&amp;type=&amp;mcode=002">브이넥</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062&amp;type=&amp;mcode=003">나시</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062&amp;type=&amp;mcode=004">폴라/터틀넥</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=062&amp;type=&amp;mcode=005">니트티</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=063">BLOUSE</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=063&amp;type=X">블라우스</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=063&amp;type=X&amp;mcode=005">남방</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=065">PANTS</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=&amp;mcode=008">MADFIT</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=&amp;mcode=001">일자핏</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=M&amp;mcode=003">배기핏</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=X&amp;mcode=002">와이드핏</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=M&amp;mcode=005">반바지</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=M&amp;mcode=004">부츠컷</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=M&amp;mcode=006">청바지</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=065&amp;type=M&amp;mcode=007">레깅스/트레이닝</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=067">OUTER</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067&amp;type=&amp;mcode=001">점퍼</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067&amp;type=&amp;mcode=002">자켓</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067&amp;type=&amp;mcode=003">조끼</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067&amp;type=&amp;mcode=004">코트</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=067&amp;type=&amp;mcode=005">가디건</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=071">UNDERWEAR</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=004">브라</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=005">팬티</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=006">홈웨어</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=001">보정속옷</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=002">내의</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=071&amp;type=&amp;mcode=003">기타</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=049">KNIT</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=049&amp;type=Y&amp;mcode=001">니트</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=049&amp;type=Y&amp;mcode=002">가디건</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=049&amp;type=Y&amp;mcode=003">조끼</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=049&amp;type=Y&amp;mcode=004">원피스/스커트</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=049&amp;type=Y&amp;mcode=005">팬츠</a></li>
                    </ul>
                    <ul>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=066">OPS/SKIRT</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=066&amp;type=&amp;mcode=001">원피스</a></li>
                        <li><a href="/shop/shopbrand.html?xcode=066&amp;type=&amp;mcode=002">스커트</a></li>
                        <li class="tit last"><a href="/shop/shopbrand.html?xcode=068">BAG&amp;SHOES</a></li>
                        <li class="tit"><a href="/shop/shopbrand.html?xcode=069">ACC</a></li>
                    </ul>
                </div>
        """
        
        category_links = extract_category_urls(html_content)
        print(f"총 {len(category_links)}개의 카테고리 URL을 추출했습니다.")
        
        # 결과 저장 디렉토리 생성
        os.makedirs('category_data', exist_ok=True)
        
        # 모든 카테고리의 상품 정보
        all_products_all_categories = []
        
        # 각 카테고리별로 크롤링
        for i, category in enumerate(category_links, 1):
            category_name = category['name']
            category_url = category['url']
            
            print(f"\n===== ({i}/{len(category_links)}) {category_name} 카테고리 크롤링 시작 =====")
            print(f"URL: {category_url}")
            
            # 최대 페이지 수 설정 (None으로 설정하면 모든 페이지)
            max_pages = None  # 테스트를 위해 각 카테고리당 최대 3페이지만 크롤링
            
            # 셀레늄으로 크롤링 실행
            category_products = crawl_products(category_url, category_name, max_pages)
            
            # 중복 상품 제거
            unique_products = []
            product_names = set()
            
            for product in category_products:
                if product['상품명'] not in product_names and product['상품명'].strip() != '':
                    product_names.add(product['상품명'])
                    unique_products.append(product)
            
            print(f"\n[{category_name}] 원본 상품 수: {len(category_products)}, 중복 제거 후 상품 수: {len(unique_products)}")
            
            if unique_products:
                # 카테고리별 데이터프레임 생성 및 저장
                df_category = pd.DataFrame(unique_products)
                
                # 파일명에 사용할 수 있는 카테고리명 생성
                safe_category_name = re.sub(r'[\\/*?:"<>|]', "", category_name)
                
                # CSV 파일로 저장
                csv_filename = f'category_data/{safe_category_name}.csv'
                df_category.to_csv(csv_filename, index=False, encoding='utf-8-sig')
                print(f"[{category_name}] CSV 파일 저장 완료: {csv_filename}")
                
                # 전체 상품 목록에 추가
                all_products_all_categories.extend(unique_products)
            
            # 서버 부담 감소를 위한 대기
            if i < len(category_links):
                delay = random.uniform(5, 10)
                print(f"다음 카테고리로 이동하기 전 {delay:.2f}초 대기 중...")
                time.sleep(delay)
        
        # 모든 카테고리의 상품을 하나의 데이터프레임으로 통합
        if all_products_all_categories:
            # 중복 제거 (모든 카테고리에서 발생할 수 있는 중복)
            unique_all_products = []
            all_product_names = set()
            
            for product in all_products_all_categories:
                if product['상품명'] not in all_product_names and product['상품명'].strip() != '':
                    all_product_names.add(product['상품명'])
                    unique_all_products.append(product)
            
            print(f"\n모든 카테고리 원본 상품 수: {len(all_products_all_categories)}, 중복 제거 후 상품 수: {len(unique_all_products)}")
            
            # 통합 데이터프레임 생성
            df_all = pd.DataFrame(unique_all_products)
            
            # CSV 파일로 저장
            all_csv_filename = 'all_products_data.csv'
            df_all.to_csv(all_csv_filename, index=False, encoding='utf-8-sig')
            print(f"모든 카테고리 통합 CSV 파일 저장 완료: {all_csv_filename}")
            
            # Excel 파일로 저장
            all_excel_filename = 'all_products_data.xlsx'
            df_all.to_excel(all_excel_filename, index=False)
            print(f"모든 카테고리 통합 Excel 파일 저장 완료: {all_excel_filename}")
        
        print(f"\n크롤링 완료! 총 {len(unique_all_products)}개의 상품 정보를 저장했습니다.")
    
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()