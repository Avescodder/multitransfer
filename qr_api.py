import os
from typing import Dict, List, Optional
import dotenv

from qr_core import QRPool, QRResult

dotenv.load_dotenv()


async def create_qr(amount: int, proxy: Optional[str] = None) -> Dict:
    """
    Single QR generation
    
    Returns:
        dict: {transfer_id, transfer_num, qr_payload}
    """
    api_key = os.getenv('RUCAPTCHA_API_KEY')
    if not api_key:
        raise ValueError("RUCAPTCHA_API_KEY not set")
    
    async with QRPool(api_key, max_concurrent=1, proxy=proxy) as pool:
        result = await pool.generate(amount)
        
        if result.success:
            return {
                "transfer_id": result.transfer_id,
                "transfer_num": result.transfer_num,
                "qr_payload": result.qr_payload,
            }
        else:
            raise RuntimeError(f"QR failed: {result.error}")


async def create_qr_batch(
    amounts: List[int],
    max_concurrent: int = 3,
    proxy: Optional[str] = None
) -> List[QRResult]:
    """
    Batch QR generation
    
    Args:
        amounts: List of amounts to generate QRs for
        max_concurrent: Max parallel tasks
        proxy: Optional proxy URL
    
    Returns:
        List[QRResult]: Results with success/error status
    """
    api_key = os.getenv('RUCAPTCHA_API_KEY')
    if not api_key:
        raise ValueError("RUCAPTCHA_API_KEY not set")
    
    async with QRPool(api_key, max_concurrent, proxy) as pool:
        return await pool.generate_batch(amounts)