import os
from agents import Agent

class MayoralSubjectSelector(Agent):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MayoralSubjectSelector, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, '_initialized'):
            super().__init__(
                name="Mayorla Subject Selector",
                instructions="""
                وظیفه شما انتخاب نزدیک ترین موضوع به گزارش کاربر از فهرست موضوعات است که به شما ارائه می شود.
                
                Example
                ** User Request **
                این آشغال های سر کوچه ما رو کسی نیست حمع کنه ؟
                
                ** Found relevant subjects
                [
                    {
                        "subject_id": 10,
                        "description": "سوزاندن زباله توسط پاکبان"
                    },
                    {
                        "subject_id": 19,
                        "description": "تخلیه زباله جارو شده داخل جوی و باغچه توسط پاکبان"
                    },
                    {
                        "subject_id": 38,
                        "description": "سطل زباله فاقد پایه می باشد"
                    },
                    {
                        "subject_id": 44,
                        "description": "تفکیک زباله توسط مامورین حمل"
                    },
                    {
                        "subject_id": 45,
                        "description": "سوزاندن زباله توسط پیمانکار حمل زباله"
                    },
                    {
                        "subject_id": 101,
                        "description": "تخلیه زباله در زمین خالی توسط مامورین حمل"
                    },
                    {
                        "subject_id": 117,
                        "description": "تخلیه زباله و ضایعات در جوی آب توسط کسبه"
                    },
                    {
                        "subject_id": 127,
                        "description": "حمل زباله"
                    },
                    {
                        "subject_id": 132,
                        "description": "سطل زباله"
                    },
                    {
                        "subject_id": 245,
                        "description": "انباشت زباله در محل"
                    },
                    {
                        "subject_id": 247,
                        "description": "انباشت زباله در زمین خالی"
                    },
                    {
                        "subject_id": 249,
                        "description": "سوزاندن زباله توسط افراد ناشناس"
                    },
                    {
                        "subject_id": 255,
                        "description": "تخلیه زباله توسط مالک"
                    },
                    {
                        "subject_id": 267,
                        "description": "تفکیک زباله توسط افراد ناشناس در محل"
                    },
                    {
                        "subject_id": 338,
                        "description": "سوزاندن زباله و شاخ و برگ توسط کارگر پارک"
                    },
                    {
                        "subject_id": 602,
                        "description": "سطل زباله"
                    }
                ]
                
                **Assistant Response:**  
                {
                    "subject_id": 127,
                    "description": "حمل زباله"
                }
                """,
                model=os.getenv("GPT_TITLE_ANALYZER_MODEL")
            )
            self._initialized = True