import requests
import pandas as pd
import concurrent.futures
import threading
import sys
from tqdm import tqdm
from datetime import datetime
import openpyxl

# 全局锁和共享资源
lock = threading.Lock()
seen_addresses = set()
all_addresses = {}
failed_pages = {}
request_session = requests.Session()

def fetch_block_data(page, limit, max_retries=5):
    """带重试机制的请求函数"""
    url = f"https://xp.tamsa.io/xphere/api/v1/proof?page={page}&limit={limit}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://xp.tamsa.io/main/blocks/proof?page={page}&count={limit}"
    }
    
    for attempt in range(max_retries):
        try:
            response = request_session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Page {page} attempt {attempt+1} failed with status code: {response.status_code}")
        except Exception as e:
            print(f"Page {page} attempt {attempt+1} failed with error: {str(e)}")
        
    print(f"Page {page} failed after {max_retries} attempts")
    return None

def process_page(page, limit):
    """处理单个页面"""
    global failed_pages
    data = fetch_block_data(page, limit)
    
    if not data:
        with lock:
            failed_pages[page] = True
        return
    
    current_page_addresses = []
    
    for block in data.get("rows", []):
        for field in ["miner", "validator"]:
            if addr := block.get(field):
                current_page_addresses.append(addr.lower())
    
    with lock:
        # 统计新地址
        unique_current = set(current_page_addresses)
        new_addresses = len(unique_current - seen_addresses)
        seen_addresses.update(unique_current)
        
        # 更新总计数（遍历原始列表保留重复项）
        for addr in current_page_addresses:
            all_addresses[addr] = all_addresses.get(addr, 0) + 1
    
    print(f"Page {page} processed, found {new_addresses} new addresses")

def fetch_address_balance(address):
    """获取地址余额（带重试）"""
    url = f"https://xp.tamsa.io/xphere/api/v1/address/{address}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://xp.tamsa.io/main/address/{address}"
    }
    
    for attempt in range(5):
        try:
            response = request_session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return int(data["row"]["balance"]) / 10**data["decimals"]
        except Exception as e:
            print(f"Balance fetch for {address} failed attempt {attempt+1}")
    
    print(f"Failed to fetch balance for {address} after 5 attempts")
    return None

def main():
    total_pages = 64
    limit_per_page = 1000
    workers = 16  # 根据网络情况调整线程数
    
    # 第一阶段：多线程抓取页面
    with tqdm(total=total_pages, desc="Processing pages") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_page, page, limit_per_page): page 
                      for page in range(1, total_pages + 1)}
            
            for future in concurrent.futures.as_completed(futures):
                pbar.update(1)
                if failed_pages:
                    executor.shutdown(wait=False)
                    print(f"Critical error: Failed to fetch {len(failed_pages)} pages")
                    sys.exit(1)
    
    # 第二阶段：多线程获取余额
    df = pd.DataFrame(
        [(addr, cnt) for addr, cnt in all_addresses.items()],
        columns=["矿工地址", "出块数量"]
    )
    df["应得代币"] = df["出块数量"] * 800
    
    print("Fetching balances with multi-threading...")
    addresses = df["矿工地址"].tolist()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        balances = list(tqdm(executor.map(fetch_address_balance, addresses), total=len(addresses)))
    
    df["实得代币"] = balances
    
    # 处理测试地址
    test_address = "0x05d4a19b4304b2de51ac2578aa0eec5de2301e62"
    test_address_lower = test_address.lower()
    
    if test_address_lower not in df["矿工地址"].values:
        print(f"Test address {test_address} not found in results. Adding it now...")
        balance = fetch_address_balance(test_address_lower)
        if balance is not None:
            new_row = {
                "矿工地址": test_address_lower,
                "出块数量": 0,
                "应得代币": 0,
                "实得代币": balance
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        print(f"Test address {test_address} found in results")
    
    # 最终排序
    df = df.sort_values(by="实得代币", ascending=False)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"xphere2.0_holders_{timestamp}.xlsx"
    
    # 保存并调整列宽
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
        worksheet = writer.sheets['Sheet1']
        
        # 自动调整列宽
        for column in worksheet.columns:
            max_length = 0
            column_name = column[0].column_letter  # 获取列字母
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2  # 调整系数
            worksheet.column_dimensions[column_name].width = adjusted_width
    
    print(f"Data saved to {filename}")
    
    # 验证示例地址
    test_data = df[df["矿工地址"] == test_address_lower]
    if not test_data.empty:
        print(f"Calculated Balance for {test_address}: {test_data['应得代币'].values[0]}")
        print(f"实得代币 for {test_address}: {test_data['实得代币'].values[0]}")
    else:
        print(f"Test address {test_address} not found in results after processing")

if __name__ == "__main__":
    main()
    