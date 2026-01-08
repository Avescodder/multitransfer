import httpx
import re


class YamlManage:
    
    _cache = {}
    
    @classmethod
    def get_path(cls, path: str) -> str:
        if path == "api.link_details.sender_details":
            return cls.get_build_id()
        return None
    
    @classmethod
    def get_build_id(cls) -> str:
        if "build_id" in cls._cache:
            return cls._cache["build_id"]
        
        try:
            response = httpx.get(
                "https://multitransfer.ru/",
                timeout=10.0,
                follow_redirects=True
            )
            
            html = response.text
            
            match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', html)
            
            if match:
                build_id = match.group(1)
                cls._cache["build_id"] = build_id
                return build_id
            
            match = re.search(r'"buildId":"([^"]+)"', html)
            if match:
                build_id = match.group(1)
                cls._cache["build_id"] = build_id
                return build_id
            
            default_build_id = "L8H5E8MPmOkkA0naeeocl"
            cls._cache["build_id"] = default_build_id
            return default_build_id
            
        except Exception:
            default_build_id = "L8H5E8MPmOkkA0naeeocl"
            cls._cache["build_id"] = default_build_id
            return default_build_id


if __name__ == "__main__":
    build_id = YamlManage.get_build_id()
    print(f"BUILD_ID: {build_id}")