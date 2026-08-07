import os
import asyncio
import httpx
import urllib.parse

async def _download_for_identifier(client, semaphore, identifier, task_items, images_dir, progress, max_retries=3):
    """Обробляє всі URL для одного артикулу. task_items містить кортежі (url, subfolder)."""
    safe_name = "".join([c for c in str(identifier) if c.isalnum() or c in ['-', '_']]).rstrip()
    success_results = []
    failed_results = []
    
    # Визначаємо, чи потрібно додавати @індекс
    use_index = len(task_items) > 1
    current_idx = 1
    
    for url, subfolder in task_items:
        try:
            if not url or not identifier:
                failed_results.append(('skip', url, identifier, ""))
                continue

            url = url.strip()
            
            if not url.lower().startswith(('http://', 'https://')):
                failed_results.append(('invalid', url, identifier, "Invalid URL format"))
                continue

            parsed_url = urllib.parse.urlparse(url)
            ext = os.path.splitext(parsed_url.path)[1]
            if not ext:
                ext = ".jpg"
            
            # Формуємо ім'я файлу на основі успішних завантажень
            if use_index:
                filename = f"{safe_name}@{current_idx}{ext}"
            else:
                filename = f"{safe_name}{ext}"
                
            # Визначаємо цільову папку (головна або підпапка 'перевірити')
            target_dir = os.path.join(images_dir, subfolder) if subfolder else images_dir
            os.makedirs(target_dir, exist_ok=True)
            
            filepath = os.path.join(target_dir, filename)

            if os.path.exists(filepath):
                success_results.append(('exists', url, identifier, ""))
                current_idx += 1  # Збільшуємо індекс тільки якщо файл є
                continue

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/'
            }
            
            downloaded = False
            async with semaphore:
                for attempt in range(max_retries):
                    try:
                        async with client.stream('GET', url, headers=headers, timeout=15.0) as response:
                            if response.status_code == 200:
                                with open(filepath, 'wb') as f:
                                    async for chunk in response.aiter_bytes(chunk_size=8192):
                                        f.write(chunk)
                                success_results.append(('success', url, identifier, ""))
                                current_idx += 1  # Збільшуємо індекс тільки після успішного завантаження
                                downloaded = True
                                break
                            
                            if response.status_code in [403, 404]:
                                failed_results.append(('error', url, identifier, f"HTTP {response.status_code}"))
                                downloaded = True # Не намагаємось завантажити ще раз при 404/403
                                break
                                
                    except httpx.RequestError:
                        pass 
                        
                    if not downloaded and attempt < max_retries - 1:
                        await asyncio.sleep(1.5 * (attempt + 1))

                if not downloaded:
                    failed_results.append(('error', url, identifier, "Network/Timeout Error"))

        except Exception as e:
            failed_results.append(('error', url, identifier, f"Critical: {str(e)}"))
            
        finally:
            progress['count'] += 1
            if progress['count'] % 100 == 0:
                msg = f"Завантажено {progress['count']} / {progress['total']} зображень..."
                print(f"  ... processed {progress['count']} / {progress['total']} tasks.")
                if progress['callback']:
                    progress['callback'](msg)

    return success_results, failed_results

async def _download_all(image_tasks: list, images_dir: str, max_concurrent: int, status_callback=None):
    semaphore = asyncio.Semaphore(max_concurrent)
    limits = httpx.Limits(max_connections=max_concurrent, max_keepalive_connections=max_concurrent)
    
    total_tasks = len(image_tasks)
    progress = {'count': 0, 'total': total_tasks, 'callback': status_callback}
    
    success_count = skip_count = invalid_count = error_count = 0
    failed_downloads = []

    # Групуємо URL-адреси та ПІДПАПКИ за артикулами
    tasks_by_id = {}
    for item in image_tasks:
        url = item[0]
        identifier = item[1]
        
        # Читаємо 4-й елемент (підпапку), який передав парсер (якщо він є)
        subfolder = item[3] if len(item) > 3 else ""
        
        if identifier not in tasks_by_id:
            tasks_by_id[identifier] = []
        tasks_by_id[identifier].append((url, subfolder))

    async with httpx.AsyncClient(limits=limits) as client:
        tasks = []
        for identifier, task_items in tasks_by_id.items():
            tasks.append(_download_for_identifier(client, semaphore, identifier, task_items, images_dir, progress))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, BaseException):
                error_count += 1
                failed_downloads.append(("Unknown", "Unknown", f"Unhandled Pool Exception: {str(result)}"))
                continue
                
            success_results, failed_results = result
            
            success_count += len(success_results)
            
            for status, url, identifier, reason in failed_results:
                if status == 'skip':
                    skip_count += 1
                elif status == 'invalid':
                    invalid_count += 1
                    failed_downloads.append((identifier, url, reason))
                elif status == 'error':
                    error_count += 1
                    failed_downloads.append((identifier, url, reason))

    return success_count, skip_count, invalid_count, error_count, failed_downloads

def download_from_list(image_tasks: list, output_dir: str, max_concurrent: int = 50, status_callback=None):
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    images_dir = os.path.join(output_dir, "зображення")
    os.makedirs(images_dir, exist_ok=True)

    total_tasks = len(image_tasks)
    print(f"Module [image_downloader]: Initiating ASYNC download of {total_tasks} images (Max concurrent: {max_concurrent})...")
    
    success, skip, invalid, error, failed = asyncio.run(_download_all(image_tasks, images_dir, max_concurrent, status_callback))
    
    print(f"Module [image_downloader]: Complete. Success/Exists: {success}, Skipped: {skip}, Invalid Links: {invalid}, Errors: {error}")
    
    if failed:
        error_log_path = os.path.join(output_dir, "failed_images.log")
        print(f"\nModule [image_downloader]: WARNING - {len(failed)} images could not be downloaded.")
        print(f"Module [image_downloader]: Writing detailed failure log to -> {error_log_path}")
        
        with open(error_log_path, 'w', encoding='utf-8') as log_file:
            log_file.write(f"Total Failed Downloads: {len(failed)}\n")
            log_file.write("-" * 80 + "\n")
            log_file.write("Артикул".ljust(20) + " | " + "Reason".ljust(25) + " | URL\n")
            log_file.write("-" * 80 + "\n")
            for identifier, url, reason in failed:
                log_file.write(f"{str(identifier).ljust(20)} | {reason.ljust(25)} | {url}\n")