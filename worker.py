from dotenv import load_dotenv
load_dotenv()

import os
import sys
from redis import Redis
from rq import Worker, Queue

queue_name = sys.argv[1] if len(sys.argv) > 1 else 'default'

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))

redis_conn = Redis(host=redis_host, port=redis_port)

queue = Queue(queue_name, connection=redis_conn)
worker = Worker(queues=[queue], connection=redis_conn)
worker.work()
