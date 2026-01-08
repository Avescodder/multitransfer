"""
Мок YamlManage для получения BUILD_ID
"""
import httpx


class YamlManage:
    """
    Класс для получения динамических данных из сайта
    """
    
    _cache = {}
    
    @classmethod
    def get_path(cls, path: str) -> str:
        """
        Получает значение по пути
        
        Args:
            path: путь вида "api.link_details.sender_details"
        
        Returns:
            Значение (например BUILD_ID)
        """
        
        if path == "api.link_details.sender_details":
            return cls.get_build_id()
        
        return None
    
    @classmethod
    def get_build_id(cls) -> str:
        """
        Получает BUILD_ID с сайта multitransfer.ru
        
        BUILD_ID нужен для формирования URL:
        https://multitransfer.ru/_next/data/{BUILD_ID}/ru/transfer/...
        
        Returns:
            BUILD_ID строка
        """
        
        # Проверяем кеш
        if "build_id" in cls._cache:
            return cls._cache["build_id"]
        
        try:
            # Загружаем главную страницу
            response = httpx.get(
                "https://multitransfer.ru/",
                timeout=10.0,
                follow_redirects=True
            )
            
            # Ищем BUILD_ID в HTML
            html = response.text
            
            # BUILD_ID обычно в скрипте вида:
            # <script src="/_next/static/{BUILD_ID}/_buildManifest.js">
            import re
            match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', html)
            
            if match:
                build_id = match.group(1)
                cls._cache["build_id"] = build_id
                print(f"[YamlManage] BUILD_ID получен: {build_id}")
                return build_id
            
            # Если не нашли, пробуем другой паттерн
            # "buildId":"{BUILD_ID}"
            match = re.search(r'"buildId":"([^"]+)"', html)
            if match:
                build_id = match.group(1)
                cls._cache["build_id"] = build_id
                print(f"[YamlManage] BUILD_ID получен (v2): {build_id}")
                return build_id
            
            print("[YamlManage] ⚠️ BUILD_ID не найден, используем дефолтный")
            # Используем последний известный
            default_build_id = "L8H5E8MPmOkkA0naeeocl"
            cls._cache["build_id"] = default_build_id
            return default_build_id
            
        except Exception as e:
            print(f"[YamlManage] Ошибка получения BUILD_ID: {e}")
            # Используем дефолтный
            default_build_id = "L8H5E8MPmOkkA0naeeocl"
            cls._cache["build_id"] = default_build_id
            return default_build_id


# Для быстрого тестирования
if __name__ == "__main__":
    build_id = YamlManage.get_build_id()
    print(f"BUILD_ID: {build_id}")