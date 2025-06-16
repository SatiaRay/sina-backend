FROM python

RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN cp .env.example .env
COPY wait-for.py .
COPY wait-for-it.sh .
EXPOSE 8000