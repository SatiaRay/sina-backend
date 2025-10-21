#!/usr/bin/env python
import os
import sys
from typing import Optional
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from database.vector import VectorStore

console = Console()

def print_header():
    """نمایش هدر برنامه"""
    title = Text("مدیریت پایگاه داده چت‌بات", style="bold magenta")
    console.print(Panel(title, border_style="blue"))

def confirm_action(message: str) -> bool:
    """دریافت تایید کاربر برای انجام عملیات"""
    return questionary.confirm(
        message,
        default=False
    ).ask()

def reset_database() -> None:
    """پاک کردن کل پایگاه داده"""
    try:
        if not confirm_action("آیا از پاک کردن کل پایگاه داده اطمینان دارید؟ این عملیات غیرقابل برگشت است!"):
            console.print("عملیات لغو شد.", style="yellow")
            return

        vector = VectorStore()
        vector.delete_all()
        
        # پاک کردن فایل‌های پشتیبان
        backup_dirs = ['data/crawled_data', 'data/plaintext_data']
        for dir_path in backup_dirs:
            if os.path.exists(dir_path):
                for file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        console.print(f"فایل پشتیبان حذف شد: {file_path}", style="yellow")

        console.print("پایگاه داده با موفقیت پاک شد!", style="green")
    except Exception as e:
        console.print(f"خطا در پاک کردن پایگاه داده: {str(e)}", style="red")

def main_menu() -> Optional[str]:
    """نمایش منوی اصلی"""
    choices = [
        "پاک کردن کل پایگاه داده",
        "خروج"
    ]
    
    return questionary.select(
        "لطفا یک گزینه را انتخاب کنید:",
        choices=choices
    ).ask()

def main():
    """تابع اصلی برنامه"""
    print_header()
    
    while True:
        choice = main_menu()
        
        if choice == "پاک کردن کل پایگاه داده":
            reset_database()
        elif choice == "خروج":
            console.print("خداحافظ!", style="cyan")
            sys.exit(0)

if __name__ == "__main__":
    main() 