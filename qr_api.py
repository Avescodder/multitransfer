import os
from typing import Dict, List, Optional
import dotenv

from qr_core import QRPool, QRResult, ProxyPool

dotenv.load_dotenv()


async def create_qr(
    amount: int,
    proxy: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Generate single QR code.
    
    Args:
        amount: Transfer amount in RUB
        proxy: Optional proxy URL
        api_key: RuCaptcha API key (defaults to env var)
    
    Returns:
        dict: {transfer_id, transfer_num, qr_payload, duration, attempts}
    
    Raises:
        ValueError: If API key not provided
        RuntimeError: If generation fails
    """
    if api_key is None:
        api_key = os.getenv('RUCAPTCHA_API_KEY')
    
    if not api_key:
        raise ValueError("RUCAPTCHA_API_KEY not set in environment")
    
    async with QRPool(api_key, max_concurrent=1, single_proxy=proxy) as pool:
        result = await pool.generate(amount)
        
        if result.success:
            return {
                "transfer_id": result.transfer_id,
                "transfer_num": result.transfer_num,
                "qr_payload": result.qr_payload,
                "duration": result.duration,
                "attempts": result.attempts
            }
        else:
            raise RuntimeError(f"QR generation failed: {result.error}")


async def create_qr_batch(
    amounts: List[int],
    max_concurrent: int = 2,
    proxy: Optional[str] = None,
    proxies: Optional[List[str]] = None,
    api_key: Optional[str] = None
) -> List[QRResult]:
    """
    Generate multiple QR codes concurrently.
    
    Args:
        amounts: List of amounts to generate QRs for
        max_concurrent: Max parallel operations (default: 2)
        proxy: Single proxy URL (ignored if proxies provided)
        proxies: List of proxy URLs for rotation
        api_key: RuCaptcha API key (defaults to env var)
    
    Returns:
        List[QRResult]: Results with success/error status
    
    Raises:
        ValueError: If API key not provided
    """
    if api_key is None:
        api_key = os.getenv('RUCAPTCHA_API_KEY')
    
    if not api_key:
        raise ValueError("RUCAPTCHA_API_KEY not set in environment")
    
    # Create proxy pool if multiple proxies provided
    proxy_pool = None
    if proxies:
        proxy_pool = ProxyPool(proxies)
    
    async with QRPool(
        api_key,
        max_concurrent=max_concurrent,
        proxy_pool=proxy_pool,
        single_proxy=proxy if not proxies else None
    ) as pool:
        return await pool.generate_batch(amounts)


async def create_qr_with_retry(
    amount: int,
    max_retries: int = 3,
    proxy: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict:
    """
    Generate QR with automatic retries on failure.
    
    Args:
        amount: Transfer amount in RUB
        max_retries: Maximum retry attempts
        proxy: Optional proxy URL
        api_key: RuCaptcha API key
    
    Returns:
        dict: QR generation result
    
    Raises:
        RuntimeError: If all retries fail
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await create_qr(amount, proxy, api_key)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                continue
    
    raise RuntimeError(f"Failed after {max_retries} attempts: {last_error}")