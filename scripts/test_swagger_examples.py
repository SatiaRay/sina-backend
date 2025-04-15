import sys
import os
from pathlib import Path
import requests
import json

# اضافه کردن مسیر ریشه پروژه به sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# لود کردن متغیرهای محیطی از .env
from dotenv import load_dotenv
load_dotenv()

API_URL = os.getenv('APP_URL', 'http://localhost:8001')

def check_openapi_schema():
    """
    بررسی OpenAPI Schema و مثال‌های API
    
    این اسکریپت OpenAPI Schema را دریافت می‌کند و مثال‌های تعریف شده را بررسی می‌کند
    """
    url = f"{API_URL}/openapi.json"
    
    try:
        print(f"در حال دریافت OpenAPI Schema از {url}...")
        response = requests.get(url)
        
        if response.status_code == 200:
            schema = response.json()
            
            print("\n=== بررسی مدل‌های درخواست و مثال‌ها ===")
            
            # بررسی همه مسیرها و عملیات
            paths = schema.get('paths', {})
            for path, operations in paths.items():
                for method, operation in operations.items():
                    if method.lower() in ['post', 'put', 'patch']:
                        
                        request_body = operation.get('requestBody', {})
                        content = request_body.get('content', {}).get('application/json', {})
                        schema_ref = content.get('schema', {}).get('$ref', '')
                        
                        if schema_ref:
                            schema_name = schema_ref.split('/')[-1]
                            print(f"\n🔍 {method.upper()} {path} - مدل: {schema_name}")
                            
                            # بررسی مثال‌ها
                            example = content.get('example', {})
                            if example:
                                print(f"  ✅ مثال تعریف شده: {json.dumps(example, ensure_ascii=False)}")
                            else:
                                print(f"  ⚠️ بدون مثال مستقیم")
                                
                                # بررسی schema examples
                                schema_obj = find_schema(schema, schema_name)
                                if schema_obj and 'example' in schema_obj:
                                    print(f"  ✅ مثال در schema: {json.dumps(schema_obj['example'], ensure_ascii=False)}")
                                    
            # بررسی ویژه برای UpdateKnowledgeRequest
            print("\n=== بررسی ویژه مدل UpdateKnowledgeRequest ===")
            update_knowledge_schema = find_schema(schema, 'UpdateKnowledgeRequest')
            if update_knowledge_schema:
                print(f"تعریف مدل: {json.dumps(update_knowledge_schema, ensure_ascii=False, indent=2)}")
            else:
                print("⚠️ مدل UpdateKnowledgeRequest یافت نشد")
            
            return True
        else:
            print(f"خطا در دریافت schema: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"خطا: {str(e)}")
        return False

def find_schema(schema, name):
    """پیدا کردن تعریف schema با نام مشخص"""
    schemas = schema.get('components', {}).get('schemas', {})
    return schemas.get(name)

if __name__ == "__main__":
    check_openapi_schema() 