import asyncio
import multiprocessing as mp
from multiprocessing import Manager, Queue
import os
import time
from typing import List, Optional

from qr_core import QRPool


def worker_process(
    worker_id: int,
    task_queue: Queue,
    result_queue: Queue,
    api_key: str,
    proxy: Optional[str],
    shared_captcha: dict
):
    asyncio.run(_worker_async(worker_id, task_queue, result_queue, api_key, proxy, shared_captcha))


async def _worker_async(
    worker_id: int,
    task_queue: Queue,
    result_queue: Queue,
    api_key: str,
    proxy: Optional[str],
    shared_captcha: dict
):
    from qr_core import Cache
    
    if shared_captcha:
        async with Cache.captcha_lock:
            for key, (token, expires) in shared_captcha.items():
                Cache.captcha_cache[key] = (token, expires)
    
    async with QRPool(api_key, max_concurrent=1, proxy=proxy) as pool:
        while True:
            try:
                task = task_queue.get_nowait()
            except:
                break
            
            if task is None:
                break
            
            result = await pool.generate(task['amount'])
            
            result_dict = {
                'task_id': task['task_id'],
                'worker_id': worker_id,
                'success': result.success,
                'transfer_id': result.transfer_id,
                'transfer_num': result.transfer_num,
                'qr_payload': result.qr_payload,
                'error': result.error,
                'duration': result.duration
            }
            
            result_queue.put(result_dict)
            
            async with Cache.captcha_lock:
                for key, (token, expires) in Cache.captcha_cache.items():
                    shared_captcha[key] = (token, expires)


class QRMultiProcessor:
    def __init__(
        self,
        api_key: str,
        num_workers: int = 3,
        proxy: Optional[str] = None
    ):
        self.api_key = api_key
        self.num_workers = num_workers
        self.proxy = proxy
    
    def generate_batch(self, amounts: List[int]) -> List[dict]:
        manager = Manager()
        task_queue = manager.Queue()
        result_queue = manager.Queue()
        shared_captcha = manager.dict()
        
        for i, amount in enumerate(amounts):
            task_queue.put({'task_id': i, 'amount': amount})
        
        for _ in range(self.num_workers):
            task_queue.put(None)
        
        processes = []
        for worker_id in range(self.num_workers):
            p = mp.Process(
                target=worker_process,
                args=(worker_id, task_queue, result_queue, self.api_key, self.proxy, shared_captcha)
            )
            p.start()
            processes.append(p)
        
        for p in processes:
            p.join()
        
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        results.sort(key=lambda x: x['task_id'])
        
        return results


async def create_qr_batch_multiprocess(
    amounts: List[int],
    num_workers: int = 3,
    api_key: Optional[str] = None,
    proxy: Optional[str] = None
) -> List[dict]:
    if api_key is None:
        api_key = os.getenv('RUCAPTCHA_API_KEY')
    
    if proxy is None:
        proxy = os.getenv('PROXY')
    
    processor = QRMultiProcessor(api_key, num_workers, proxy)
    return processor.generate_batch(amounts)